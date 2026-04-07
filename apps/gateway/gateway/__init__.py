"""SAP Copilot Gateway — FastAPI server bridging frontend to VSP MCP + LiteLLM."""

from __future__ import annotations

import asyncio
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routes import chat, systems, health, llm, workflows


if sys.platform == "win32" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Also explicitly create and install a ProactorEventLoop so uvicorn
    # inherits it even if it calls asyncio.get_event_loop() before run().
    try:
        _loop = asyncio.get_event_loop()
        if not isinstance(_loop, asyncio.ProactorEventLoop):
            _loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(_loop)
    except RuntimeError:
        _loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(_loop)

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = FastAPI(
    title="SAP Copilot Gateway",
    version="0.1.0",
    description="Bridges the SAP Copilot frontend to VSP MCP servers via LiteLLM",
)

# CORS — allow the Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, tags=["health"])
app.include_router(systems.router, prefix="/api/systems", tags=["systems"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(llm.router, prefix="/api/llm", tags=["llm"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["workflows"])
