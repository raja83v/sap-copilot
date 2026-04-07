"""Chat SSE streaming endpoint.

Frontend opens an SSE connection here. The gateway:
1. Receives the user message + conversation history
2. Classifies intent — if it's a multi-step SAP workflow, delegates to the
   LangGraph workflow engine; otherwise runs the simple LLM chat loop
3. Streams back events (content tokens, tool calls, errors, done, or
   workflow-specific events like agent_start, approval_required, etc.)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..mcp_manager import mcp_manager
from ..orchestrator import chat_stream
from ..workflows.router import classify_intent
from ..workflows.engine import start_workflow

logger = logging.getLogger("gateway.routes.chat")

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    system_id: str
    session_id: str = ""
    messages: list[ChatMessage]
    model: str = ""


@router.post("/stream")
async def stream_chat(req: ChatRequest):
    """Stream an AI chat response with tool calling via SSE.

    If the latest user message looks like a multi-step development task
    (e.g. "Create a report ZTEST"), the intent classifier routes it to
    the LangGraph workflow engine.  Otherwise the simple LLM chat loop
    handles it.
    """
    # ── Get or reconnect MCP connection ──
    conn = mcp_manager.get(req.system_id)
    if not conn:
        # Attempt auto-reconnect if we have stored params
        if mcp_manager.has_params(req.system_id):
            logger.info("MCP connection dead for system %s — attempting auto-reconnect", req.system_id)
            try:
                conn = await mcp_manager.reconnect(req.system_id)
            except Exception as e:
                logger.error("Auto-reconnect failed for system %s: %s", req.system_id, e)
                raise HTTPException(
                    status_code=503,
                    detail=f"SAP connection lost and reconnect failed: {e}",
                )
        if not conn:
            raise HTTPException(
                status_code=404,
                detail=f"System {req.system_id} not connected. Call POST /api/systems/connect first.",
            )

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # ── Intent classification ──
    last_user_msg = next(
        (m.content for m in reversed(req.messages) if m.role == "user"), ""
    )

    workflow_type = "simple_chat"
    if last_user_msg:
        try:
            workflow_type = await classify_intent(last_user_msg)
        except Exception as e:
            logger.warning("Intent classification failed, falling back to simple chat: %s", e)
            workflow_type = "simple_chat"

    # ── Workflow path ──
    if workflow_type != "simple_chat":
        logger.info(
            "Routing to workflow engine: type=%s, system=%s", workflow_type, req.system_id
        )

        async def workflow_generator():
            try:
                async for sse_msg in start_workflow(
                    workflow_type=workflow_type,  # type: ignore[arg-type]
                    user_request=last_user_msg,
                    system_id=req.system_id,
                    session_id=req.session_id,
                ):
                    yield sse_msg
            except Exception as e:
                logger.exception("Workflow stream error for system %s: %s", req.system_id, e)
                yield {
                    "event": "error",
                    "data": json.dumps({"message": f"Workflow error: {e}"}),
                }

        return EventSourceResponse(
            workflow_generator(),
            media_type="text/event-stream",
        )

    # ── Simple chat path ──
    async def event_generator():
        sent_done = False
        try:
            async for event in chat_stream(messages, req.model, conn, system_id=req.system_id):
                yield {
                    "event": event.type,
                    "data": json.dumps(event.data),
                }
                if event.type in ("done", "error"):
                    sent_done = True
        except Exception as e:
            logger.exception("Chat stream error for system %s: %s", req.system_id, e)
            yield {
                "event": "error",
                "data": json.dumps({"message": f"Stream error: {e}"}),
            }
            sent_done = True
        finally:
            # Guarantee a done event is always sent so the frontend finalizes
            if not sent_done:
                logger.warning("Chat stream ended without done/error event for system %s", req.system_id)
                yield {
                    "event": "done",
                    "data": json.dumps({"content": ""}),
                }

    return EventSourceResponse(event_generator())
