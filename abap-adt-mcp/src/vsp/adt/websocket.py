"""WebSocket client for ZADT_VSP APC (ABAP Push Channel) handler.

Provides stateful communication for debugging, RFC calls, Git operations,
report execution, and ABAP help.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from vsp.config import Config

logger = logging.getLogger("vsp.adt.websocket")


@dataclass
class WSMessage:
    """A WebSocket message to/from ZADT_VSP."""
    id: str = ""
    domain: str = ""
    action: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str = ""

    def to_json(self) -> str:
        """Serialize to JSON for sending."""
        return json.dumps({
            "id": self.id,
            "domain": self.domain,
            "action": self.action,
            "params": self.params,
        })

    @classmethod
    def from_json(cls, data: str) -> WSMessage:
        """Deserialize from JSON received from server."""
        obj = json.loads(data)
        return cls(
            id=obj.get("id", ""),
            domain=obj.get("domain", ""),
            action=obj.get("action", ""),
            params=obj.get("params", {}),
            result=obj.get("result"),
            error=obj.get("error", ""),
        )


class WebSocketClient:
    """WebSocket client for ZADT_VSP APC handler.

    Lazy-connects on first use. Supports request/response correlation
    via message IDs.

    Usage:
        async with WebSocketClient(config) as ws:
            result = await ws.send("debug", "set_breakpoint", {"uri": uri, "line": 10})
    """

    def __init__(self, config: Config):
        self.config = config
        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._connected = False
        self._pending: dict[str, asyncio.Future[WSMessage]] = {}
        self._receive_task: Optional[asyncio.Task[None]] = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> WebSocketClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    async def connect(self) -> None:
        """Establish WebSocket connection to ZADT_VSP."""
        if self._connected:
            return

        async with self._lock:
            if self._connected:
                return

            try:
                import websockets

                # Build WebSocket URL from SAP URL
                base = self.config.base_url.replace("http://", "ws://").replace("https://", "wss://")
                ws_url = f"{base}/sap/bc/apc/sap/zadt_vsp"

                # Add auth params
                params = f"?sap-client={self.config.client}&sap-language={self.config.language}"
                ws_url += params

                # Build extra headers for auth
                extra_headers: dict[str, str] = {}
                if self.config.uses_basic_auth:
                    import base64
                    credentials = base64.b64encode(
                        f"{self.config.username}:{self.config.password}".encode()
                    ).decode()
                    extra_headers["Authorization"] = f"Basic {credentials}"

                self._ws = await websockets.connect(
                    ws_url,
                    additional_headers=extra_headers,
                    ssl=None if not self.config.insecure else _create_insecure_ssl_context(),
                )
                self._connected = True

                # Start receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())

                logger.info("WebSocket connected to ZADT_VSP")

            except ImportError:
                raise RuntimeError("websockets package required. Install with: pip install websockets")
            except Exception as e:
                logger.error("WebSocket connection failed: %s", e)
                raise

    async def close(self) -> None:
        """Close the WebSocket connection."""
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        # Cancel pending futures
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    async def send(
        self,
        domain: str,
        action: str,
        params: Optional[dict[str, Any]] = None,
        *,
        timeout: float = 60.0,
    ) -> Any:
        """Send a request and wait for the response.

        Args:
            domain: Message domain (debug, rfc, git, report, help, tadir).
            action: Action within the domain.
            params: Action parameters.
            timeout: Response timeout in seconds.

        Returns:
            Response result.
        """
        if not self._connected:
            await self.connect()

        msg_id = str(uuid.uuid4())
        msg = WSMessage(id=msg_id, domain=domain, action=action, params=params or {})

        # Create future for response
        future: asyncio.Future[WSMessage] = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        try:
            # Send
            await self._ws.send(msg.to_json())
            logger.debug("WS send: %s/%s (%s)", domain, action, msg_id[:8])

            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)

            if response.error:
                raise RuntimeError(f"ZADT_VSP error: {response.error}")

            return response.result

        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise TimeoutError(f"WebSocket request timed out after {timeout}s: {domain}/{action}")
        except Exception:
            self._pending.pop(msg_id, None)
            raise

    async def _receive_loop(self) -> None:
        """Background loop receiving WebSocket messages."""
        try:
            async for data in self._ws:
                try:
                    msg = WSMessage.from_json(data if isinstance(data, str) else data.decode())

                    # Match to pending request
                    future = self._pending.pop(msg.id, None)
                    if future and not future.done():
                        future.set_result(msg)
                    else:
                        logger.debug("WS received unmatched message: %s", msg.id[:8])

                except json.JSONDecodeError:
                    logger.warning("WS received non-JSON message")
                except Exception as e:
                    logger.warning("WS receive error: %s", e)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("WS receive loop ended: %s", e)
            self._connected = False


def _create_insecure_ssl_context() -> Any:
    """Create an SSL context that skips verification."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
