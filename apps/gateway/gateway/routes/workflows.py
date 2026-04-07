"""Workflow REST API routes.

Endpoints:
- POST /api/workflows/start          Start a new multi-agent workflow
- POST /api/workflows/resume         Resume a paused workflow (approval response)
- POST /api/workflows/answer         Submit clarification answers
- GET  /api/workflows/types          List all available workflow types
- GET  /api/workflows/graph/{type}   Get graph structure for visualization
- GET  /api/workflows/{id}           Get workflow state
- GET  /api/workflows/{id}/history   Get full audit trail
- POST /api/workflows/{id}/cancel    Cancel a running workflow
- POST /api/workflows/{id}/retry     Retry a failed step
- POST /api/workflows/{id}/skip      Skip a step
- POST /api/workflows/classify       Classify intent (for UI previews)
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..workflows.engine import (
    cancel_workflow,
    get_workflow_state,
    resume_workflow,
    resume_with_answers,
    start_workflow,
)
from ..workflows.graph_metadata import get_all_workflow_types, get_graph_metadata
from ..workflows.recovery import get_workflow_history, retry_step, skip_step
from ..workflows.router import classify_intent

logger = logging.getLogger("gateway.routes.workflows")

router = APIRouter()


# ──────────────────────────────────────────────────────────────────────
# Request/Response models
# ──────────────────────────────────────────────────────────────────────

class StartWorkflowRequest(BaseModel):
    system_id: str
    session_id: str
    workflow_type: str
    user_request: str


class ResumeWorkflowRequest(BaseModel):
    workflow_id: str
    approved: bool
    feedback: str = ""


class AnswerClarificationRequest(BaseModel):
    workflow_id: str
    answers: list[dict[str, str]]  # [{"id": "q1", "answer": "..."}]


class RetryStepRequest(BaseModel):
    step_id: str


class SkipStepRequest(BaseModel):
    step_id: str
    reason: str = ""


class ClassifyRequest(BaseModel):
    message: str


# ──────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────

@router.post("/start")
async def start(req: StartWorkflowRequest):
    """Start a new workflow and stream agent execution events via SSE."""
    async def event_generator():
        async for sse_msg in start_workflow(
            workflow_type=req.workflow_type,  # type: ignore[arg-type]
            user_request=req.user_request,
            system_id=req.system_id,
            session_id=req.session_id,
        ):
            # sse_msg is a pre-formatted SSE string
            yield sse_msg

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.post("/resume")
async def resume(req: ResumeWorkflowRequest):
    """Resume a paused workflow after user approval/rejection."""
    async def event_generator():
        async for sse_msg in resume_workflow(
            workflow_id=req.workflow_id,
            approved=req.approved,
            feedback=req.feedback,
        ):
            yield sse_msg

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.post("/classify")
async def classify(req: ClassifyRequest):
    """Classify a user message into a workflow type or simple_chat."""
    result = await classify_intent(req.message)
    return {"type": result}


@router.post("/answer")
async def answer_clarification(req: AnswerClarificationRequest):
    """Submit clarification answers to resume a paused workflow."""
    async def event_generator():
        async for sse_msg in resume_with_answers(
            workflow_id=req.workflow_id,
            answers=req.answers,
        ):
            yield sse_msg

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# ── Static path routes MUST come before /{workflow_id} catch-all ──

@router.get("/types")
async def list_workflow_types():
    """List all available workflow types with descriptions and metadata."""
    return {"types": get_all_workflow_types()}


@router.get("/graph/{workflow_type}")
async def get_graph(workflow_type: str):
    """Get the graph structure for a workflow type (for DAG visualization)."""
    meta = get_graph_metadata(workflow_type)
    if meta is None:
        raise HTTPException(404, f"Unknown workflow type: {workflow_type}")
    return meta


# ── Dynamic path routes (catch-all) ──

@router.get("/{workflow_id}")
async def get_state(workflow_id: str):
    """Get the current state of a workflow."""
    state = await get_workflow_state(workflow_id)
    if state is None:
        raise HTTPException(404, "Workflow not found or expired")
    # Serialize langchain messages to dicts
    serialized = {}
    for k, v in state.items():
        if k == "messages":
            serialized[k] = [
                {"role": _msg_role(m), "content": getattr(m, "content", str(m))}
                for m in v
            ]
        else:
            try:
                json.dumps(v)
                serialized[k] = v
            except (TypeError, ValueError):
                serialized[k] = str(v)
    return serialized


@router.get("/{workflow_id}/history")
async def get_history(workflow_id: str):
    """Get the full audit trail for a workflow."""
    history = await get_workflow_history(workflow_id)
    if history is None:
        raise HTTPException(404, "Workflow not found or expired")
    return history


@router.post("/{workflow_id}/cancel")
async def cancel(workflow_id: str):
    """Cancel a running or paused workflow."""
    removed = cancel_workflow(workflow_id)
    if not removed:
        raise HTTPException(404, "Workflow not found or already finished")
    return {"status": "cancelled", "workflow_id": workflow_id}


@router.post("/{workflow_id}/retry")
async def retry(workflow_id: str, req: RetryStepRequest):
    """Retry a failed step in a workflow."""
    async def event_generator():
        async for sse_msg in retry_step(
            workflow_id=workflow_id,
            step_id=req.step_id,
        ):
            yield sse_msg

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.post("/{workflow_id}/skip")
async def skip(workflow_id: str, req: SkipStepRequest):
    """Skip a step in a workflow."""
    async def event_generator():
        async for sse_msg in skip_step(
            workflow_id=workflow_id,
            step_id=req.step_id,
            reason=req.reason,
        ):
            yield sse_msg

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
    )


def _msg_role(msg) -> str:
    """Extract role string from a LangChain message."""
    type_map = {"human": "user", "ai": "assistant", "tool": "tool", "system": "system"}
    return type_map.get(msg.type, msg.type) if hasattr(msg, "type") else "unknown"
