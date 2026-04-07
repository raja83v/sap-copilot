"""Health check endpoints."""

from fastapi import APIRouter

from ..mcp_manager import mcp_manager

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "connected_systems": mcp_manager.list_connected(),
    }
