"""SAP system connection management endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..mcp_manager import mcp_manager

logger = logging.getLogger("gateway.routes.systems")

router = APIRouter()


class ConnectRequest(BaseModel):
    system_id: str
    url: str
    user: str
    password: str
    client: str = "100"
    language: str = "EN"
    insecure: bool = False
    read_only: bool = False
    proxy: str = ""
    timeout: float = 60.0


class ConnectResponse(BaseModel):
    system_id: str
    status: str
    tools_count: int


@router.post("/test")
async def test_connection(req: ConnectRequest):
    """Test connectivity to a SAP system without persisting the connection."""
    test_id = f"__test_{req.system_id}"
    try:
        async def _run_test_connection():
            conn = await mcp_manager.connect(
                system_id=test_id,
                url=req.url,
                user=req.user,
                password=req.password,
                client=req.client,
                language=req.language,
                insecure=req.insecure,
                read_only=True,
                proxy=req.proxy,
                timeout=req.timeout,
            )
            return await conn.list_tools()

        tools = await asyncio.wait_for(
            _run_test_connection(),
            timeout=float(settings.test_connection_timeout_sec),
        )
        await mcp_manager.disconnect(test_id)
        return {"status": "success", "tools_count": len(tools)}
    except asyncio.TimeoutError:
        await mcp_manager.disconnect(test_id)
        logger.warning("Test connection timed out for %s", req.url)
        raise HTTPException(
            status_code=504,
            detail=(
                "Connection test timed out. Verify SAP URL/proxy and try again. "
                "If needed, increase GATEWAY_TEST_CONNECTION_TIMEOUT_SEC."
            ),
        )
    except Exception as e:
        await mcp_manager.disconnect(test_id)
        logger.exception("Test connection failed for %s", req.url)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect", response_model=ConnectResponse)
async def connect_system(req: ConnectRequest):
    """Connect to a SAP system by spawning a VSP MCP process."""
    try:
        conn = await mcp_manager.connect(
            system_id=req.system_id,
            url=req.url,
            user=req.user,
            password=req.password,
            client=req.client,
            language=req.language,
            insecure=req.insecure,
            read_only=req.read_only,
            proxy=req.proxy,
            timeout=req.timeout,
        )
        tools = await conn.list_tools()
        return ConnectResponse(
            system_id=req.system_id,
            status="connected",
            tools_count=len(tools),
        )
    except Exception as e:
        logger.exception("Failed to connect system %s", req.system_id)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{system_id}/disconnect")
async def disconnect_system(system_id: str):
    """Disconnect from a SAP system."""
    await mcp_manager.disconnect(system_id)
    return {"system_id": system_id, "status": "disconnected"}


@router.get("/")
async def list_systems():
    """List connected systems."""
    return {"connected": mcp_manager.list_connected()}


@router.get("/{system_id}/tools")
async def list_tools(system_id: str):
    """List available MCP tools for a connected system."""
    conn = mcp_manager.get(system_id)
    if not conn:
        raise HTTPException(status_code=404, detail=f"System {system_id} not connected")
    tools = await conn.list_tools()
    return {"system_id": system_id, "tools": tools}
