"""MCP Process Manager — spawns and manages VSP child processes per SAP system.

Each active SAP system gets its own VSP process communicating via stdio.
The manager handles lifecycle (spawn, health check, cleanup) and provides
a connection pool interface.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .config import settings

logger = logging.getLogger("gateway.mcp_manager")


@dataclass
class MCPConnection:
    """Represents a live connection to a VSP MCP server process."""

    system_id: str
    process: asyncio.subprocess.Process
    _request_id: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _pending: dict[int, asyncio.Future] = field(default_factory=dict, init=False)
    _reader_task: asyncio.Task | None = field(default=None, init=False)
    _stderr_task: asyncio.Task | None = field(default=None, init=False)
    _stderr_tail: deque[str] = field(default_factory=lambda: deque(maxlen=20), init=False)
    _initialized: bool = field(default=False, init=False)

    async def start(self) -> None:
        """Initialize the MCP connection (send initialize handshake)."""
        self._reader_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._stderr_loop())
        # MCP initialize handshake
        result = await self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "sap-copilot-gateway", "version": "0.1.0"},
        })
        logger.info("MCP initialized for system %s: %s", self.system_id, result.get("serverInfo", {}))
        # Send initialized notification
        await self.notify("notifications/initialized", {})
        self._initialized = True

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        timeout_sec: float | None = None,
    ) -> Any:
        """Send a JSON-RPC request and await the response."""
        async with self._lock:
            self._request_id += 1
            req_id = self._request_id

        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            msg["params"] = params

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        payload = json.dumps(msg) + "\n"
        self.process.stdin.write(payload.encode())  # type: ignore[union-attr]
        await self.process.stdin.drain()  # type: ignore[union-attr]

        effective_timeout = settings.mcp_request_timeout_sec if timeout_sec is None else timeout_sec

        try:
            return await asyncio.wait_for(future, timeout=effective_timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"MCP request {method} timed out for system {self.system_id}")

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        msg: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            msg["params"] = params

        payload = json.dumps(msg) + "\n"
        self.process.stdin.write(payload.encode())  # type: ignore[union-attr]
        await self.process.stdin.drain()  # type: ignore[union-attr]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call an MCP tool and return the result."""
        result = await self.request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        }, timeout_sec=settings.mcp_tool_call_timeout_sec)
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools from the MCP server."""
        result = await self.request("tools/list", {})
        return result.get("tools", [])

    async def _read_loop(self) -> None:
        """Read JSON-RPC responses from the MCP process stdout."""
        try:
            while True:
                line = await self.process.stdout.readline()  # type: ignore[union-attr]
                if not line:
                    logger.warning("MCP process stdout closed for system %s", self.system_id)
                    self._fail_pending_requests(self._build_process_exit_message())
                    break

                try:
                    msg = json.loads(line.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                req_id = msg.get("id")
                if req_id is not None and req_id in self._pending:
                    future = self._pending.pop(req_id)
                    if "error" in msg:
                        if not future.done():
                            future.set_exception(
                                MCPError(msg["error"].get("message", "Unknown MCP error"), msg["error"])
                            )
                    else:
                        if not future.done():
                            future.set_result(msg.get("result", {}))
                elif "method" in msg:
                    # Server-initiated notification — log for now
                    logger.debug("MCP notification: %s", msg.get("method"))
        except asyncio.CancelledError:
            return
        except asyncio.LimitOverrunError:
            logger.error(
                "MCP read loop buffer overflow for system %s — response line too large",
                self.system_id,
            )
            self._fail_pending_requests(
                f"MCP response too large for system {self.system_id}"
            )
        except Exception:
            logger.exception("Error in MCP read loop for system %s", self.system_id)

    async def _stderr_loop(self) -> None:
        """Read stderr lines so startup failures are visible and can be surfaced."""
        try:
            while True:
                line = await self.process.stderr.readline()  # type: ignore[union-attr]
                if not line:
                    break
                text = line.decode(errors="replace").rstrip()
                if text:
                    self._stderr_tail.append(text)
                    logger.debug("MCP stderr [%s]: %s", self.system_id, text)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Error in MCP stderr loop for system %s", self.system_id)

    def _build_process_exit_message(self) -> str:
        tail = " | ".join(self._stderr_tail)
        if tail:
            return f"MCP process exited for {self.system_id}. stderr: {tail}"
        return f"MCP process exited for {self.system_id} before initialization"

    def _fail_pending_requests(self, message: str) -> None:
        for req_id, future in list(self._pending.items()):
            self._pending.pop(req_id, None)
            if not future.done():
                future.set_exception(MCPError(message))

    async def close(self) -> None:
        """Terminate the MCP process gracefully."""
        if self._reader_task:
            self._reader_task.cancel()
        if self._stderr_task:
            self._stderr_task.cancel()
        try:
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            self.process.kill()
        logger.info("MCP process closed for system %s", self.system_id)

    @property
    def is_alive(self) -> bool:
        return self.process.returncode is None


class MCPError(Exception):
    """Error from an MCP server response."""

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.detail = detail or {}


@dataclass
class ConnectionParams:
    """Stores the parameters used to create an MCP connection, for reconnection."""

    url: str
    user: str
    password: str
    client: str = "100"
    language: str = "EN"
    insecure: bool = False
    read_only: bool = False
    proxy: str = ""
    timeout: float = 60.0


class MCPProcessManager:
    """Manages a pool of MCP connections, one per SAP system."""

    def __init__(self):
        self._connections: dict[str, MCPConnection] = {}
        self._params: dict[str, ConnectionParams] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        system_id: str,
        url: str,
        user: str,
        password: str,
        client: str = "100",
        language: str = "EN",
        insecure: bool = False,
        read_only: bool = False,
        proxy: str = "",
        timeout: float = 60.0,
    ) -> MCPConnection:
        """Spawn a new VSP MCP process for a SAP system."""
        async with self._lock:
            # Close existing connection if any
            if system_id in self._connections:
                await self._connections[system_id].close()

            # Store params for reconnection
            self._params[system_id] = ConnectionParams(
                url=url, user=user, password=password,
                client=client, language=language,
                insecure=insecure, read_only=read_only, proxy=proxy,
                timeout=timeout,
            )

            conn = await self._spawn(system_id)
            return conn

    async def _spawn(self, system_id: str) -> MCPConnection:
        """Internal: spawn a VSP subprocess using stored params.

        Caller must hold self._lock.
        """
        params = self._params[system_id]
        env = {**os.environ}

        effective_proxy = params.proxy or settings.http_proxy
        if effective_proxy:
            env["HTTP_PROXY"] = effective_proxy
            env["HTTPS_PROXY"] = effective_proxy

            # Build NO_PROXY: always exclude localhost and the SAP hostname.
            # The proxy is for external traffic (LLM APIs, etc.); SAP systems
            # on the internal network must NOT be routed through the proxy.
            no_proxy_parts = ["localhost", "127.0.0.1"]

            # Automatically exclude the SAP system hostname
            from urllib.parse import urlparse
            try:
                parsed = urlparse(params.url)
                if parsed.hostname:
                    no_proxy_parts.append(parsed.hostname)
            except Exception:
                pass

            # Add any extra entries from GATEWAY_NO_PROXY
            if settings.no_proxy:
                no_proxy_parts.extend(
                    p.strip() for p in settings.no_proxy.split(",") if p.strip()
                )
            no_proxy_str = ",".join(no_proxy_parts)
            env["NO_PROXY"] = no_proxy_str
            env["no_proxy"] = no_proxy_str

        # SAP HTTP timeout: use the larger of the per-connection timeout and
        # the gateway-wide sap_http_timeout_sec so the config file always acts
        # as a sensible floor.
        effective_sap_timeout = max(params.timeout, float(settings.sap_http_timeout_sec))
        env["SAP_TIMEOUT"] = str(effective_sap_timeout)

        cmd = [
            settings.vsp_python, "-m", "vsp",
            "--url", params.url,
            "--user", params.user,
            "--password", params.password,
            "--client", params.client,
            "--language", params.language,
            "--timeout", str(effective_sap_timeout),
            "--mode", "expert",
        ]

        if params.insecure:
            cmd.append("--insecure")
        if params.read_only:
            cmd.append("--read-only")

        logger.info("Spawning MCP process for system %s: %s", system_id, params.url)
        logger.info(
            "Subprocess env: HTTP_PROXY=%s NO_PROXY=%s SAP_TIMEOUT=%s",
            env.get("HTTP_PROXY", "unset"),
            env.get("NO_PROXY", "unset"),
            env.get("SAP_TIMEOUT", "unset"),
        )

        # Use a 10 MB stream buffer so large MCP responses (source code,
        # search results, etc.) don't trigger asyncio LimitOverrunError.
        _STREAM_LIMIT = 10 * 1024 * 1024  # 10 MB

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            limit=_STREAM_LIMIT,
        )

        conn = MCPConnection(system_id=system_id, process=process)
        await conn.start()

        self._connections[system_id] = conn
        return conn

    async def reconnect(self, system_id: str) -> MCPConnection | None:
        """Kill the existing process and spawn a fresh one using stored params.

        Returns the new connection, or None if no stored params exist.
        """
        async with self._lock:
            if system_id not in self._params:
                logger.warning("Cannot reconnect system %s: no stored params", system_id)
                return None

            old = self._connections.pop(system_id, None)
            if old:
                await old.close()

            logger.info("Reconnecting MCP process for system %s", system_id)
            return await self._spawn(system_id)

    def get(self, system_id: str) -> MCPConnection | None:
        """Get an existing MCP connection."""
        conn = self._connections.get(system_id)
        if conn and conn.is_alive:
            return conn
        return None

    def has_params(self, system_id: str) -> bool:
        """Check if stored connection params exist for reconnection."""
        return system_id in self._params

    async def disconnect(self, system_id: str) -> None:
        """Close and remove an MCP connection."""
        async with self._lock:
            conn = self._connections.pop(system_id, None)
            if conn:
                await conn.close()
            self._params.pop(system_id, None)

    async def disconnect_all(self) -> None:
        """Close all MCP connections."""
        async with self._lock:
            for conn in self._connections.values():
                await conn.close()
            self._connections.clear()
            self._params.clear()

    def list_connected(self) -> list[str]:
        """Return IDs of connected systems."""
        return [sid for sid, conn in self._connections.items() if conn.is_alive]


# Singleton instance
mcp_manager = MCPProcessManager()
