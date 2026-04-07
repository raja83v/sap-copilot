"""LiteLLM proxy configuration and model discovery endpoints.

LiteLLM runs as a separate proxy server. This module:
- Stores the LiteLLM base URL + API key (configurable at runtime)
- Proxies GET /v1/models to the LiteLLM proxy
- Provides a /configure endpoint to update connection settings
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings

logger = logging.getLogger("gateway.routes.llm")

router = APIRouter()

# Runtime-mutable LiteLLM connection settings (seeded from env/config)
_litellm_base_url: str = settings.litellm_base_url
_litellm_api_key: str = settings.litellm_api_key


def get_litellm_base_url() -> str:
    return _litellm_base_url


def get_litellm_api_key() -> str:
    return _litellm_api_key


class ConfigureRequest(BaseModel):
    base_url: str
    api_key: str


@router.post("/configure")
async def configure_litellm(req: ConfigureRequest):
    """Update LiteLLM proxy connection settings at runtime."""
    global _litellm_base_url, _litellm_api_key
    _litellm_base_url = req.base_url.rstrip("/")
    _litellm_api_key = req.api_key
    logger.info("LiteLLM proxy configured: %s", _litellm_base_url)
    return {"status": "ok", "base_url": _litellm_base_url}


@router.get("/config")
async def get_config():
    """Return current LiteLLM proxy connection settings (key masked)."""
    masked_key = ""
    if _litellm_api_key:
        masked_key = _litellm_api_key[:8] + "•" * 8
    return {"base_url": _litellm_base_url, "api_key_masked": masked_key}


@router.get("/models")
async def list_models():
    """Fetch available models from the LiteLLM proxy via GET /v1/models."""
    if not _litellm_base_url:
        raise HTTPException(status_code=400, detail="LiteLLM base URL not configured")

    headers: dict[str, str] = {}
    if _litellm_api_key:
        headers["Authorization"] = f"Bearer {_litellm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=15, trust_env=True) as client:
            resp = await client.get(f"{_litellm_base_url}/v1/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail=f"Cannot reach LiteLLM proxy at {_litellm_base_url}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LiteLLM proxy error: {e}")

    # LiteLLM returns { "data": [ { "id": "model-name", ... } ], "object": "list" }
    raw_models = data.get("data", [])
    models = [
        {"id": m["id"], "name": m["id"], "owned_by": m.get("owned_by", "")}
        for m in raw_models
        if isinstance(m, dict) and "id" in m
    ]
    return {"models": models}


@router.get("/health")
async def litellm_health():
    """Check if the LiteLLM proxy is reachable."""
    if not _litellm_base_url:
        return {"status": "not_configured"}

    headers: dict[str, str] = {}
    if _litellm_api_key:
        headers["Authorization"] = f"Bearer {_litellm_api_key}"

    try:
        async with httpx.AsyncClient(timeout=5, trust_env=True) as client:
            resp = await client.get(f"{_litellm_base_url}/health", headers=headers)
            return {"status": "ok" if resp.is_success else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "unreachable", "detail": str(e)}
