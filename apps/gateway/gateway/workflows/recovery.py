"""Workflow error recovery — retry, skip, and manual override.

Provides functions to recover from failed workflow steps without
restarting the entire workflow.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncIterator

from langgraph.types import Command

from .engine import _compiled_graphs, _sse, _convert_event

logger = logging.getLogger("gateway.workflows.recovery")


async def retry_step(
    *,
    workflow_id: str,
    step_id: str,
) -> AsyncIterator[dict[str, str]]:
    """Retry a failed step by resuming the workflow from the last checkpoint.

    The graph will re-execute the node that produced the failed step.
    """
    compiled = _compiled_graphs.get(workflow_id)
    if not compiled:
        yield _sse("error", {"message": f"Workflow {workflow_id} not found or expired"})
        return

    config = {"configurable": {"thread_id": workflow_id}}

    yield _sse("workflow_resumed", {
        "workflow_id": workflow_id,
        "action": "retry",
        "step_id": step_id,
    })

    try:
        # Get current state to find the failed step
        snapshot = await compiled.aget_state(config)
        if not snapshot or not snapshot.values:
            yield _sse("error", {
                "workflow_id": workflow_id,
                "message": "Cannot retrieve workflow state for retry",
            })
            return

        state = dict(snapshot.values)
        steps = state.get("steps", [])

        # Mark the failed step as retrying
        for step in steps:
            if step.get("id") == step_id and step.get("status") == "failed":
                step["status"] = "running"
                step["result"] = "Retrying..."
                break

        # Resume the graph — it will re-execute from the last checkpoint
        resume_value = Command(resume={"retry": True, "step_id": step_id})
        async for event in compiled.astream_events(
            resume_value, config=config, version="v2"
        ):
            sse_msg = _convert_event(event, workflow_id)
            if sse_msg:
                yield sse_msg

    except Exception as e:
        logger.error("Retry step %s in workflow %s error: %s", step_id, workflow_id, e)
        yield _sse("error", {
            "workflow_id": workflow_id,
            "message": f"Retry failed: {e}",
            "step_id": step_id,
        })
        return

    # Check if graph paused
    try:
        snapshot = await compiled.aget_state(config)
        if snapshot.next:
            yield _sse("workflow_paused", {
                "workflow_id": workflow_id,
                "reason": "user_input_required",
            })
        else:
            yield _sse("workflow_complete", {"workflow_id": workflow_id})
    except Exception:
        yield _sse("workflow_complete", {"workflow_id": workflow_id})


async def skip_step(
    *,
    workflow_id: str,
    step_id: str,
    reason: str = "",
) -> AsyncIterator[dict[str, str]]:
    """Skip a failed or pending step and advance the workflow.

    Marks the step as 'skipped' and resumes the graph with a skip signal.
    """
    compiled = _compiled_graphs.get(workflow_id)
    if not compiled:
        yield _sse("error", {"message": f"Workflow {workflow_id} not found or expired"})
        return

    config = {"configurable": {"thread_id": workflow_id}}

    yield _sse("step_skipped", {
        "workflow_id": workflow_id,
        "step_id": step_id,
        "reason": reason,
    })

    try:
        # Resume with skip signal
        resume_value = Command(resume={
            "skip": True,
            "step_id": step_id,
            "reason": reason,
        })
        async for event in compiled.astream_events(
            resume_value, config=config, version="v2"
        ):
            sse_msg = _convert_event(event, workflow_id)
            if sse_msg:
                yield sse_msg

    except Exception as e:
        logger.error("Skip step %s in workflow %s error: %s", step_id, workflow_id, e)
        yield _sse("error", {
            "workflow_id": workflow_id,
            "message": f"Skip failed: {e}",
            "step_id": step_id,
        })
        return

    # Check if graph paused
    try:
        snapshot = await compiled.aget_state(config)
        if snapshot.next:
            yield _sse("workflow_paused", {
                "workflow_id": workflow_id,
                "reason": "user_input_required",
            })
        else:
            yield _sse("workflow_complete", {"workflow_id": workflow_id})
    except Exception:
        yield _sse("workflow_complete", {"workflow_id": workflow_id})


async def get_workflow_history(workflow_id: str) -> dict[str, Any] | None:
    """Get the full audit trail for a workflow.

    Returns all steps, approvals, tool calls, and state transitions.
    """
    compiled = _compiled_graphs.get(workflow_id)
    if not compiled:
        return None

    config = {"configurable": {"thread_id": workflow_id}}
    try:
        snapshot = await compiled.aget_state(config)
        if not snapshot or not snapshot.values:
            return None

        state = dict(snapshot.values)
        return {
            "workflow_id": workflow_id,
            "workflow_type": state.get("workflow_type", ""),
            "phase": state.get("phase", ""),
            "user_request": state.get("user_request", ""),
            "plan": state.get("plan"),
            "steps": state.get("steps", []),
            "approvals": state.get("approvals", []),
            "clarifications": state.get("clarifications", []),
            "artifacts": list(state.get("artifacts", {}).keys()),
            "created_objects": state.get("created_objects", []),
            "review_findings": state.get("review_findings", []),
            "test_results": state.get("test_results", {}),
            "analysis_summary": state.get("analysis_summary"),
            "documentation": state.get("documentation"),
            "migration_log": state.get("migration_log", []),
            "error": state.get("error"),
            "fix_attempts": state.get("fix_attempts", 0),
            "metadata": state.get("metadata", {}),
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
        }
    except Exception as e:
        logger.error("Get workflow history %s error: %s", workflow_id, e)
        return None
