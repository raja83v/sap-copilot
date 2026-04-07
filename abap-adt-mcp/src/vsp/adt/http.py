"""HTTP transport layer for ADT communication.

Handles CSRF token management, session handling, cookie authentication,
and automatic retry on token expiry / session timeout.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from urllib.parse import urlencode, urljoin

import httpx

from vsp.config import Config, SessionType

logger = logging.getLogger("vsp.adt.http")

# Header constants
HEADER_CSRF_TOKEN = "X-CSRF-Token"
HEADER_SESSION_TYPE = "X-sap-adt-sessiontype"
HEADER_ACCEPT = "Accept"
HEADER_CONTENT_TYPE = "Content-Type"

# CSRF fetch endpoint
CSRF_FETCH_URL = "/sap/bc/adt/core/discovery"

# Session error indicator
SESSION_ERROR_INDICATOR = "ICMENOSESSION"


class ADTHTTPError(Exception):
    """Error from ADT HTTP communication."""

    def __init__(self, status_code: int, message: str, response: Optional[httpx.Response] = None):
        self.status_code = status_code
        self.response = response
        super().__init__(f"HTTP {status_code}: {message}")


class Transport:
    """HTTP transport for SAP ADT communication.

    Manages CSRF tokens, session IDs, authentication, and automatic retry
    on token expiry and session timeout.

    Usage:
        async with Transport(config) as transport:
            resp = await transport.get("/sap/bc/adt/programs/programs/ZTEST/source/main")
    """

    def __init__(self, config: Config):
        self.config = config
        self._csrf_token: str = ""
        self._csrf_lock = asyncio.Lock()
        self._session_id: str = ""
        self._session_lock = asyncio.Lock()
        self._client: Optional[httpx.AsyncClient] = None
        self._cookies: dict[str, str] = {}
        # Manual cookie tracking: SAP often sets 'secure' cookies even on HTTP,
        # which causes standard cookie jars to refuse sending them back.
        # We track all response cookies manually to ensure they're always sent.
        self._session_cookies: dict[str, str] = {}

        # Load cookies if configured
        if config.cookie_file:
            from vsp.adt.cookies import parse_cookie_file
            self._cookies = parse_cookie_file(config.cookie_file)
        elif config.cookie_string:
            from vsp.adt.cookies import parse_cookie_string
            self._cookies = parse_cookie_string(config.cookie_string)

    async def __aenter__(self) -> Transport:
        """Initialize the async HTTP client."""
        # Use a generous connection pool with keepalive to survive idle periods
        # between MCP tool calls (which can be minutes apart).
        pool_limits = httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
            keepalive_expiry=300,  # 5 minutes keepalive
        )
        self._client = httpx.AsyncClient(
            verify=not self.config.insecure,
            timeout=httpx.Timeout(self.config.timeout, connect=30.0),
            follow_redirects=True,
            limits=pool_limits,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close the async HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not initialized."""
        if self._client is None:
            raise RuntimeError("Transport not initialized. Use 'async with Transport(config) as t:'")
        return self._client

    # -------------------------------------------------------------------------
    # Public HTTP methods
    # -------------------------------------------------------------------------

    async def get(
        self,
        path: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
        accept: str = "application/xml",
    ) -> httpx.Response:
        """Send GET request."""
        return await self.request("GET", path, headers=headers, params=params, accept=accept)

    async def post(
        self,
        path: str,
        *,
        content: Optional[str | bytes] = None,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
        content_type: str = "application/xml",
        accept: str = "application/xml",
    ) -> httpx.Response:
        """Send POST request."""
        return await self.request(
            "POST", path, content=content, headers=headers, params=params,
            content_type=content_type, accept=accept,
        )

    async def put(
        self,
        path: str,
        *,
        content: Optional[str | bytes] = None,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
        content_type: str = "text/plain",
        accept: str = "application/xml",
    ) -> httpx.Response:
        """Send PUT request."""
        return await self.request(
            "PUT", path, content=content, headers=headers, params=params,
            content_type=content_type, accept=accept,
        )

    async def delete(
        self,
        path: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Send DELETE request."""
        return await self.request("DELETE", path, headers=headers, params=params)

    async def head(
        self,
        path: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Send HEAD request."""
        return await self.request("HEAD", path, headers=headers, params=params)

    async def options(
        self,
        path: str,
        *,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
    ) -> httpx.Response:
        """Send OPTIONS request."""
        return await self.request("OPTIONS", path, headers=headers, params=params)

    # -------------------------------------------------------------------------
    # Core request method with CSRF + session handling
    # -------------------------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        content: Optional[str | bytes] = None,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, str]] = None,
        content_type: Optional[str] = None,
        accept: str = "application/xml",
    ) -> httpx.Response:
        """Execute an HTTP request with CSRF token and session management.

        - Automatically fetches CSRF token for write methods (POST/PUT/DELETE/PATCH).
        - On 403: re-fetches CSRF token and retries once.
        - On 400 with ICMENOSESSION: clears session/token, re-fetches, retries once.
        """
        # Build URL
        url = self._build_url(path, params)

        # Ensure CSRF token for write operations
        is_write = method.upper() in ("POST", "PUT", "DELETE", "PATCH")
        if is_write and not self._csrf_token:
            await self._fetch_csrf_token()

        # Build request headers
        req_headers = self._build_headers(is_write, accept, content_type, headers)

        # Execute with retry logic
        resp = await self._execute(method, url, content, req_headers)

        # Handle 403 - CSRF token expired
        if resp.status_code == 403 and is_write:
            logger.debug("CSRF token expired, refreshing...")
            await self._fetch_csrf_token()
            req_headers = self._build_headers(is_write, accept, content_type, headers)
            resp = await self._execute(method, url, content, req_headers)

        # Handle 400 - Session timeout
        if resp.status_code == 400 and SESSION_ERROR_INDICATOR in resp.text:
            logger.debug("Session expired, re-establishing...")
            async with self._csrf_lock:
                self._csrf_token = ""
            async with self._session_lock:
                self._session_id = ""
            if is_write:
                await self._fetch_csrf_token()
            req_headers = self._build_headers(is_write, accept, content_type, headers)
            resp = await self._execute(method, url, content, req_headers)

        # Update session info from response
        await self._update_session(resp)

        # Raise for non-success status codes
        if resp.status_code >= 400:
            raise ADTHTTPError(resp.status_code, resp.text[:500], resp)

        return resp

    # -------------------------------------------------------------------------
    # Session type switching
    # -------------------------------------------------------------------------

    async def set_session_type(self, session_type: SessionType) -> None:
        """Switch the ADT session type."""
        self.config.session_type = session_type

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _build_url(self, path: str, params: Optional[dict[str, str]] = None) -> str:
        """Build full URL with base, path, and default query params."""
        base = self.config.base_url.rstrip("/")

        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path

        url = base + path

        # Add default query params
        default_params = {
            "sap-client": self.config.client,
            "sap-language": self.config.language,
        }
        if params:
            default_params.update(params)

        # Build query string
        if default_params:
            separator = "&" if "?" in url else "?"
            url = url + separator + urlencode(default_params)

        return url

    def _build_headers(
        self,
        is_write: bool,
        accept: str = "application/xml",
        content_type: Optional[str] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, str]:
        """Build request headers."""
        h: dict[str, str] = {
            HEADER_ACCEPT: accept,
        }

        if content_type:
            h[HEADER_CONTENT_TYPE] = content_type

        # Session type
        if self.config.session_type != SessionType.KEEP:
            h[HEADER_SESSION_TYPE] = self.config.session_type.value

        # CSRF token for write operations
        if is_write and self._csrf_token:
            h[HEADER_CSRF_TOKEN] = self._csrf_token

        # Merge extra headers
        if extra_headers:
            h.update(extra_headers)

        return h

    async def _execute(
        self,
        method: str,
        url: str,
        content: Optional[str | bytes],
        headers: dict[str, str],
        _retry_count: int = 0,
    ) -> httpx.Response:
        """Execute the actual HTTP request.

        Automatically retries once on connection errors (e.g. stale pooled
        connections dropped by firewalls/proxies after idle periods).
        """
        MAX_RETRIES = 2

        # Build kwargs
        kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
        }

        # Set authentication
        if self.config.uses_basic_auth:
            kwargs["auth"] = (self.config.username, self.config.password)

        # Inject all cookies (config + session) via Cookie header.
        # We do NOT use httpx's `cookies` kwarg because httpx drops
        # cookies marked 'secure' on plain-HTTP connections and also
        # conflicts when both `cookies` kwarg and a Cookie header are present.
        cookie_header = self._build_cookie_header()
        if cookie_header:
            existing = headers.get("Cookie", "")
            headers["Cookie"] = f"{existing}; {cookie_header}" if existing else cookie_header
            logger.debug(
                "Sending %d cookies (%d from config, %d from session) for %s %s",
                len(self._cookies) + len(self._session_cookies),
                len(self._cookies), len(self._session_cookies),
                method, url,
            )

        # Set content
        if content is not None:
            kwargs["content"] = content

        if self.config.verbose:
            logger.info("%s %s", method, url)

        try:
            resp = await self.client.request(**kwargs)
            self._collect_cookies(resp)
            return resp
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError) as e:
            if _retry_count < MAX_RETRIES:
                logger.warning(
                    "Connection error on %s %s (attempt %d/%d): %s — retrying",
                    method, url, _retry_count + 1, MAX_RETRIES, e,
                )
                # Brief pause before retry to let connections reset
                await asyncio.sleep(1.0)
                return await self._execute(method, url, content, headers, _retry_count + 1)
            raise

    def _collect_cookies(self, resp: httpx.Response) -> None:
        """Extract ALL cookies from Set-Cookie headers, ignoring secure flag.

        SAP sets the ``secure`` flag on session cookies (SAP_SESSIONID,
        MYSAPSSO2, sap-contextid, …) even when the connection is plain HTTP.
        httpx's cookie jar honours the flag and refuses to store/send them,
        so we manually parse every ``Set-Cookie`` header and keep the values
        in ``_session_cookies`` which are injected via the ``Cookie`` header
        on every subsequent request.
        """
        for header_val in resp.headers.get_list("set-cookie"):
            try:
                name_val = header_val.split(";")[0]
                name, val = name_val.split("=", 1)
                name = name.strip()
                val = val.strip()
                self._session_cookies[name] = val
                logger.debug("Collected cookie: %s (len=%d)", name, len(val))
            except ValueError:
                logger.debug("Skipping malformed Set-Cookie: %s", header_val[:80])

    def _build_cookie_header(self) -> str:
        """Merge config cookies and session cookies into a single Cookie header value.

        Session cookies (from Set-Cookie responses) take precedence over
        config cookies (from cookie file / cookie string) when names collide.
        """
        all_cookies: dict[str, str] = {}
        if self._cookies:
            all_cookies.update(self._cookies)
        if self._session_cookies:
            all_cookies.update(self._session_cookies)
        if not all_cookies:
            return ""
        return "; ".join(f"{k}={v}" for k, v in all_cookies.items())

    async def _fetch_csrf_token(self) -> None:
        """Fetch a fresh CSRF token from the ADT discovery endpoint.

        Tries HEAD first, falls back to GET if HEAD fails (some systems
        return 400 on HEAD but succeed with GET).
        """
        async with self._csrf_lock:
            url = self._build_url(CSRF_FETCH_URL)
            headers: dict[str, str] = {
                HEADER_CSRF_TOKEN: "fetch",
                HEADER_ACCEPT: "application/atomsvc+xml, application/xml, */*",
            }

            # Inject all cookies (config + session) via Cookie header.
            # We do NOT use httpx's `cookies` kwarg because httpx drops
            # cookies marked 'secure' on plain-HTTP connections.
            cookie_header = self._build_cookie_header()
            if cookie_header:
                headers["Cookie"] = cookie_header

            kwargs: dict[str, Any] = {
                "url": url,
                "headers": headers,
            }
            if self.config.uses_basic_auth:
                kwargs["auth"] = (self.config.username, self.config.password)

            logger.debug(
                "Fetching CSRF token (cookies: %d config, %d session)",
                len(self._cookies), len(self._session_cookies),
            )

            # Try HEAD first
            resp = await self.client.request(method="HEAD", **kwargs)
            self._collect_cookies(resp)

            # Check if HEAD already returned a valid token (some systems
            # return 400 on HEAD but still include the CSRF token header).
            token = resp.headers.get(HEADER_CSRF_TOKEN, "")
            if (not token or token.lower() == "required") and resp.status_code >= 400:
                logger.debug("HEAD CSRF fetch returned %d without token, retrying with GET", resp.status_code)
                # Rebuild cookie header – HEAD response may have added new cookies
                cookie_header = self._build_cookie_header()
                if cookie_header:
                    headers["Cookie"] = cookie_header
                resp = await self.client.request(method="GET", **kwargs)
                self._collect_cookies(resp)
                token = resp.headers.get(HEADER_CSRF_TOKEN, "")
            if token and token.lower() != "required":
                self._csrf_token = token
                logger.debug("CSRF token acquired (status=%d)", resp.status_code)
            else:
                logger.warning("Failed to acquire CSRF token (status=%d)", resp.status_code)

    async def _update_session(self, resp: httpx.Response) -> None:
        """Extract and store session information from response."""
        # Update CSRF token if present in response
        token = resp.headers.get(HEADER_CSRF_TOKEN, "")
        if token and token.lower() not in ("required", ""):
            async with self._csrf_lock:
                self._csrf_token = token

        # Extract session ID from cookies.
        # First check _session_cookies (manually collected, works even when
        # SAP marks cookies as 'secure' on HTTP connections).
        # Fall back to httpx's cookie jar for non-secure cookies.
        for cookie_name in ("sap-contextid", "SAP_SESSIONID"):
            if cookie_name in self._session_cookies:
                async with self._session_lock:
                    self._session_id = self._session_cookies[cookie_name]
                return
        for cookie_name in ("sap-contextid", "SAP_SESSIONID"):
            for cookie in resp.cookies.jar:
                if cookie.name == cookie_name:
                    async with self._session_lock:
                        self._session_id = cookie.value
                    return
