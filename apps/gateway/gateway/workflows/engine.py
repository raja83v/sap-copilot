"""Workflow execution engine — runs LangGraph graphs and streams events.

This module owns the running workflow instances, provides start/resume/cancel
operations, and converts graph execution into SSE events.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from ..mcp_manager import mcp_manager
from .checkpoint import checkpoint_saver
from .graphs import build_workflow_graph
from .router import classify_intent
from .state import WorkflowType, new_workflow_state

logger = logging.getLogger("gateway.workflows.engine")


# ──────────────────────────────────────────────────────────────────────
# SSE Event helper — returns dict for EventSourceResponse
# ──────────────────────────────────────────────────────────────────────

def _sse(event_type: str, data: dict[str, Any]) -> dict[str, str]:
    """Return an SSE event dict compatible with sse_starlette EventSourceResponse."""
    return {"event": event_type, "data": json.dumps(data)}


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

async def _workflow_summary(compiled: Any, config: dict[str, Any]) -> dict[str, Any]:
    """Extract a small summary from the final workflow state."""
    try:
        snapshot = await compiled.aget_state(config)
        vals = dict(snapshot.values) if snapshot.values else {}
        return {
            "created_objects": vals.get("created_objects", []),
            "plan": (vals.get("plan") or "")[:500],
            "metadata": vals.get("metadata", {}),
            "review_pass": vals.get("review_pass"),
            "tests_pass": vals.get("tests_pass"),
        }
    except Exception:
        return {}


# ──────────────────────────────────────────────────────────────────────
# Track compiled graphs by workflow_id so we can resume them
# ──────────────────────────────────────────────────────────────────────

_compiled_graphs: dict[str, Any] = {}


async def start_workflow(
    *,
    workflow_type: WorkflowType,
    user_request: str,
    system_id: str,
    session_id: str,
) -> AsyncIterator[dict[str, str]]:
    """Start a new workflow and stream SSE events as agents execute."""
    mcp_conn = mcp_manager.get(system_id)
    if not mcp_conn:
        # Attempt auto-reconnect if we have stored params
        if mcp_manager.has_params(system_id):
            logger.info("MCP connection lost for %s at workflow start — reconnecting", system_id)
            try:
                mcp_conn = await mcp_manager.reconnect(system_id)
            except Exception as e:
                logger.error("Reconnect failed for %s: %s", system_id, e)
        if not mcp_conn:
            yield _sse("error", {"message": f"System {system_id} is not connected"})
            return

    # Build state
    state = new_workflow_state(
        workflow_type=workflow_type,
        system_id=system_id,
        session_id=session_id,
        user_request=user_request,
    )
    state["messages"] = [HumanMessage(content=user_request)]
    workflow_id = state["workflow_id"]

    # Build and compile graph
    graph_builder = build_workflow_graph(workflow_type, mcp_conn, system_id)
    compiled = graph_builder.compile(checkpointer=checkpoint_saver)
    _compiled_graphs[workflow_id] = compiled

    config = {"configurable": {"thread_id": workflow_id}}

    yield _sse("workflow_start", {
        "workflow_id": workflow_id,
        "type": workflow_type,
        "user_request": user_request,
    })

    try:
        async for event in compiled.astream_events(state, config=config, version="v2"):
            sse_msg = _convert_event(event, workflow_id)
            if sse_msg:
                yield sse_msg
    except Exception as e:
        # Check if this is an interrupt (approval or clarification needed)
        if "interrupt" in str(type(e).__name__).lower() or "GraphInterrupt" in str(type(e)):
            async for msg in _handle_interrupt(compiled, config, workflow_id):
                yield msg
            return

        logger.error("Workflow %s error: %s", workflow_id, e)
        yield _sse("error", {"workflow_id": workflow_id, "message": str(e)})
        return

    # Check if graph paused for interrupt
    async for msg in _handle_interrupt(compiled, config, workflow_id):
        yield msg
        return

    summary = await _workflow_summary(compiled, config)
    yield _sse("workflow_complete", {"workflow_id": workflow_id, **summary})


async def resume_workflow(
    *,
    workflow_id: str,
    approved: bool,
    feedback: str = "",
) -> AsyncIterator[dict[str, str]]:
    """Resume a paused workflow after user approval/rejection."""
    compiled = _compiled_graphs.get(workflow_id)
    if not compiled:
        logger.error("resume_workflow: workflow %s NOT FOUND in _compiled_graphs (keys: %s)",
                      workflow_id, list(_compiled_graphs.keys()))
        yield _sse("error", {"message": f"Workflow {workflow_id} not found or expired"})
        return

    logger.info("resume_workflow: %s approved=%s feedback=%r", workflow_id, approved, feedback[:100])
    config = {"configurable": {"thread_id": workflow_id}}

    yield _sse("workflow_resumed", {
        "workflow_id": workflow_id,
        "approved": approved,
        "feedback": feedback,
    })

    event_count = 0
    sse_count = 0
    try:
        # Resume with the approval response using Command
        resume_value = Command(resume={"approved": approved, "feedback": feedback})
        async for event in compiled.astream_events(
            resume_value, config=config, version="v2"
        ):
            event_count += 1
            sse_msg = _convert_event(event, workflow_id)
            if sse_msg:
                sse_count += 1
                yield sse_msg
    except Exception as e:
        logger.error("resume_workflow exception after %d events (%d SSE): %s: %s",
                      event_count, sse_count, type(e).__name__, e)
        if "interrupt" in str(type(e).__name__).lower() or "GraphInterrupt" in str(type(e)):
            async for msg in _handle_interrupt(compiled, config, workflow_id):
                yield msg
            return
        yield _sse("error", {"workflow_id": workflow_id, "message": str(e)})
        return

    logger.info("resume_workflow: %s finished — %d events, %d SSE messages", workflow_id, event_count, sse_count)

    # Check if graph paused again
    async for msg in _handle_interrupt(compiled, config, workflow_id):
        yield msg
        return

    summary = await _workflow_summary(compiled, config)
    yield _sse("workflow_complete", {"workflow_id": workflow_id, **summary})


async def get_workflow_state(workflow_id: str) -> dict[str, Any] | None:
    """Get the current state of a running/paused workflow."""
    compiled = _compiled_graphs.get(workflow_id)
    if not compiled:
        return None
    config = {"configurable": {"thread_id": workflow_id}}
    try:
        snapshot = await compiled.aget_state(config)
        return dict(snapshot.values) if snapshot.values else None
    except Exception:
        return None


def cancel_workflow(workflow_id: str) -> bool:
    """Cancel a workflow by removing it from the active set."""
    return _compiled_graphs.pop(workflow_id, None) is not None


async def resume_with_answers(
    *,
    workflow_id: str,
    answers: list[dict[str, str]],
) -> AsyncIterator[dict[str, str]]:
    """Resume a paused workflow after user provides clarification answers."""
    compiled = _compiled_graphs.get(workflow_id)
    if not compiled:
        yield _sse("error", {"message": f"Workflow {workflow_id} not found or expired"})
        return

    config = {"configurable": {"thread_id": workflow_id}}

    yield _sse("workflow_resumed", {
        "workflow_id": workflow_id,
        "answers_count": len(answers),
    })

    try:
        resume_value = Command(resume={"answers": answers})
        async for event in compiled.astream_events(
            resume_value, config=config, version="v2"
        ):
            sse_msg = _convert_event(event, workflow_id)
            if sse_msg:
                yield sse_msg
    except Exception as e:
        if "interrupt" in str(type(e).__name__).lower() or "GraphInterrupt" in str(type(e)):
            async for msg in _handle_interrupt(compiled, config, workflow_id):
                yield msg
            return
        logger.error("Resume with answers workflow %s error: %s", workflow_id, e)
        yield _sse("error", {"workflow_id": workflow_id, "message": str(e)})
        return

    # Check if graph paused again
    async for msg in _handle_interrupt(compiled, config, workflow_id):
        yield msg
        return

    summary = await _workflow_summary(compiled, config)
    yield _sse("workflow_complete", {"workflow_id": workflow_id, **summary})


# ──────────────────────────────────────────────────────────────────────
# Interrupt handling helper
# ──────────────────────────────────────────────────────────────────────

async def _handle_interrupt(
    compiled: Any,
    config: dict[str, Any],
    workflow_id: str,
) -> AsyncIterator[dict[str, str]]:
    """Check for pending interrupts and yield appropriate SSE events.

    Handles both approval gates and clarification gates.
    """
    try:
        snapshot = await compiled.aget_state(config)
    except Exception:
        return

    if not snapshot.next:
        return

    for task in snapshot.tasks:
        if not hasattr(task, "interrupts") or not task.interrupts:
            continue
        for intr in task.interrupts:
            value = intr.value if hasattr(intr, "value") else {}
            interrupt_type = value.get("type", "approval") if isinstance(value, dict) else "approval"

            if interrupt_type == "clarification":
                # Clarification gate — send questions to UI
                yield _sse("clarification_required", {
                    "workflow_id": workflow_id,
                    "questions": value.get("questions", []),
                })
            else:
                # Approval gate — send approval request to UI
                yield _sse("approval_required", {
                    "workflow_id": workflow_id,
                    "data": value,
                })

    yield _sse("workflow_paused", {
        "workflow_id": workflow_id,
        "reason": "user_input_required",
    })


# ──────────────────────────────────────────────────────────────────────
# Event conversion
# ──────────────────────────────────────────────────────────────────────

# Known agent node names — used to detect agent events regardless of
# whether LangGraph reports the graph key or the function __name__.
_AGENT_NAMES = frozenset({
    "clarifier", "planner", "coder", "reviewer", "tester",
    "activator", "analyzer", "documenter", "migrator",
})


def _is_agent_event(node_name: str) -> str | None:
    """Return the bare agent name if *node_name* refers to an agent node, else None."""
    # Match either "coder_node" (function __name__) or "coder" (graph key)
    if node_name.endswith("_node"):
        bare = node_name[:-5]
        if bare in _AGENT_NAMES:
            return bare
    if node_name in _AGENT_NAMES:
        return node_name
    return None


def _convert_event(event: dict[str, Any], workflow_id: str) -> dict[str, str] | None:
    """Convert a LangGraph stream event to an SSE string."""
    kind = event.get("event", "")
    node_name = event.get("name", "")

    # ── DEBUG: log every event so gateway logs reveal the stream ──
    if kind in ("on_chain_start", "on_chain_end"):
        logger.debug("LG event: %s  node=%s", kind, node_name)

    # Agent node started
    agent = _is_agent_event(node_name)
    if kind == "on_chain_start" and agent:
        logger.info("▶ agent_start: %s", agent)
        return _sse("agent_start", {
            "workflow_id": workflow_id,
            "agent": agent,
        })

    # Agent node completed
    if kind == "on_chain_end" and agent:
        output = event.get("data", {}).get("output", {})
        # Extract step info if available
        steps = output.get("steps", []) if isinstance(output, dict) else []
        last_step = steps[-1] if steps else None
        logger.info("■ agent_end: %s  phase=%s", agent, output.get("phase", "") if isinstance(output, dict) else "")
        return _sse("agent_end", {
            "workflow_id": workflow_id,
            "agent": agent,
            "phase": output.get("phase", "") if isinstance(output, dict) else "",
            "step": {
                "id": last_step.get("id", "") if last_step else "",
                "status": last_step.get("status", "") if last_step else "",
                "result": (last_step.get("result", "") or "")[:300] if last_step else "",
                "tool_call_count": len(last_step.get("tool_calls", [])) if last_step else 0,
            } if last_step else None,
        })

    # LLM streaming token
    if kind == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        if chunk and hasattr(chunk, "content") and chunk.content:
            return _sse("content", {
                "workflow_id": workflow_id,
                "text": chunk.content,
                "agent": event.get("metadata", {}).get("langgraph_node", ""),
            })

    # Tool call started
    if kind == "on_tool_start":
        return _sse("tool_start", {
            "workflow_id": workflow_id,
            "name": node_name,
            "input": str(event.get("data", {}).get("input", ""))[:500],
        })

    # Tool call ended
    if kind == "on_tool_end":
        return _sse("tool_end", {
            "workflow_id": workflow_id,
            "name": node_name,
            "output": str(event.get("data", {}).get("output", ""))[:500],
        })

    return None
