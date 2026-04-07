"""LangGraph workflow graph definitions.

Builds a ``StateGraph[WorkflowState]`` per workflow type with:
- Agent nodes (planner → clarifier → coder → reviewer → tester → activator)
- Conditional edges (e.g. review_pass → tester, else → coder)
- Approval gates using ``langgraph.types.interrupt()``
- Fix-attempt loop limits (max 2 coder→reviewer rounds)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from ..mcp_manager import MCPConnection, mcp_manager
from .agents import (
    activator_node,
    analyzer_node,
    clarifier_node,
    coder_node,
    documenter_node,
    migrator_node,
    planner_node,
    reviewer_node,
    tester_node,
)
from .state import ApprovalRequest, WorkflowState, WorkflowType

logger = logging.getLogger("gateway.workflows.graphs")

MAX_FIX_ATTEMPTS = 2


# ──────────────────────────────────────────────────────────────────────
# Wrapper nodes — adapt agent functions to LangGraph node signature
# ──────────────────────────────────────────────────────────────────────
# LangGraph nodes receive (state) and we need to pass mcp_conn + system_id.
# We solve this by binding extra args at graph-build time via closures.


def _make_agent_node(agent_fn, mcp_conn: MCPConnection, system_id: str):
    """Wrap an agent function as a LangGraph node ``(state) -> state_update``.

    Instead of using the captured ``mcp_conn`` directly, looks up the
    *current* connection from mcp_manager each time the node runs.
    This prevents stale-connection bugs when a concurrent reconnect
    replaces the MCP subprocess.
    """
    async def node(state: WorkflowState) -> dict:
        current_conn = mcp_manager.get(system_id)
        if not current_conn or not current_conn.is_alive:
            logger.warning(
                "MCP connection stale for %s in %s — attempting reconnect",
                system_id, agent_fn.__name__,
            )
            if mcp_manager.has_params(system_id):
                try:
                    current_conn = await mcp_manager.reconnect(system_id)
                except Exception as exc:
                    logger.error("Reconnect failed for %s: %s", system_id, exc)
            if not current_conn or not current_conn.is_alive:
                raise RuntimeError(
                    f"MCP connection lost for system {system_id} and reconnect failed"
                )
        return await agent_fn(state, current_conn, system_id)
    node.__name__ = agent_fn.__name__
    return node


# ──────────────────────────────────────────────────────────────────────
# Approval gate nodes
# ──────────────────────────────────────────────────────────────────────

def _make_approval_gate(phase: str, details_fn):
    """Return a node function that pauses the graph for user approval.

    Uses ``langgraph.types.interrupt()`` which suspends execution until
    the caller resumes with a response.
    """
    async def approval_gate(state: WorkflowState) -> dict:
        details = details_fn(state)
        approval_id = str(uuid.uuid4())[:8]
        approval = ApprovalRequest(
            id=approval_id,
            phase=phase,
            status="pending",
            details=details,
            requested_at=time.time(),
        )
        approvals = list(state.get("approvals", []))
        approvals.append(approval)

        # Interrupt — the graph will suspend here.
        # The caller must resume with {"approved": True/False, "feedback": "..."}
        response = interrupt({
            "approval_id": approval_id,
            "phase": phase,
            "details": details,
        })

        # Process the response
        approved = response.get("approved", False)
        feedback = response.get("feedback", "")
        approval["status"] = "approved" if approved else "rejected"
        approval["responded_at"] = time.time()
        approval["feedback"] = feedback

        return {
            "approvals": approvals,
            "current_approval": None,
            "phase": state.get("phase", phase),
            "updated_at": time.time(),
        }

    approval_gate.__name__ = f"approve_{phase}"
    return approval_gate


# ──────────────────────────────────────────────────────────────────────
# Clarification gate — pauses graph for user questions
# ──────────────────────────────────────────────────────────────────────

def _make_clarification_gate():
    """Return a node that pauses the graph to ask the user clarifying questions.

    Uses ``interrupt()`` to suspend execution. The caller resumes with
    ``{"answers": [{"id": "q1", "answer": "..."}]}`` once the user responds.
    """
    async def clarification_gate(state: WorkflowState) -> dict:
        questions = state.get("clarifications", [])
        pending = [q for q in questions if not q.get("answer")]
        if not pending:
            return {"needs_clarification": False}

        response = interrupt({
            "type": "clarification",
            "questions": pending,
        })

        # Process answers
        answers = response.get("answers", [])
        updated_clarifications = list(state.get("clarifications", []))
        for ans in answers:
            for q in updated_clarifications:
                if q.get("id") == ans.get("id"):
                    q["answer"] = ans.get("answer", "")
                    q["answered_at"] = time.time()

        return {
            "clarifications": updated_clarifications,
            "needs_clarification": False,
            "updated_at": time.time(),
        }

    clarification_gate.__name__ = "clarification_gate"
    return clarification_gate


# ──────────────────────────────────────────────────────────────────────
# Conditional edge functions
# ──────────────────────────────────────────────────────────────────────

def _after_planner(state: WorkflowState) -> str:
    """Route after planner: clarify if needed, else go to plan approval."""
    if state.get("needs_clarification"):
        return "clarifier"
    return "approve_plan"


def _after_clarifier(state: WorkflowState) -> str:
    """Route after clarifier: ask user or go back to planner."""
    pending = [q for q in state.get("clarifications", []) if not q.get("answer")]
    if pending:
        return "clarification_gate"
    return "planner"


def _after_plan_approval(state: WorkflowState) -> str:
    """Route after plan approval gate."""
    last_approval = (state.get("approvals") or [{}])[-1]
    if last_approval.get("status") == "rejected":
        return "planner"  # Re-plan with feedback
    return "coder"


def _after_reviewer(state: WorkflowState) -> str:
    """Route after reviewer: pass → approve_code, fail → coder (with limit)."""
    if state.get("review_pass"):
        return "approve_code"
    fix_attempts = state.get("fix_attempts", 0)
    if fix_attempts >= MAX_FIX_ATTEMPTS:
        return "approve_code"  # Let user decide after max attempts
    return "coder"


def _after_code_approval(state: WorkflowState) -> str:
    """Route after code approval gate."""
    last_approval = (state.get("approvals") or [{}])[-1]
    if last_approval.get("status") == "rejected":
        return "coder"  # Fix with feedback
    return "tester"


def _after_tester(state: WorkflowState) -> str:
    """Route after tester: pass → activator, fail → reviewer."""
    if state.get("tests_pass"):
        return "approve_activation"
    return "reviewer"


def _after_activation_approval(state: WorkflowState) -> str:
    """Route after activation approval gate."""
    last_approval = (state.get("approvals") or [{}])[-1]
    if last_approval.get("status") == "rejected":
        return END
    return "activator"


def _after_analyzer(state: WorkflowState) -> str:
    """Route after analyzer: go to reviewer or documenter."""
    wf_type = state.get("workflow_type", "")
    if wf_type == "documentation":
        return "documenter"
    return "reviewer"


def _after_migrator(state: WorkflowState) -> str:
    """Route after migrator: go to reviewer."""
    return "reviewer"


# ──────────────────────────────────────────────────────────────────────
# Increment fix_attempts when looping coder → reviewer
# ──────────────────────────────────────────────────────────────────────

async def _increment_fix_attempts(state: WorkflowState) -> dict:
    return {"fix_attempts": state.get("fix_attempts", 0) + 1}


# ──────────────────────────────────────────────────────────────────────
# Graph builders
# ──────────────────────────────────────────────────────────────────────

def build_full_workflow_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build the standard multi-agent workflow graph.

    Flow (clarifier-first design):
        clarifier → clarification_gate (user answers) → planner → approve_plan
        → coder → reviewer → [loop max 2] → approve_code
        → activator → END
    """
    graph = StateGraph(WorkflowState)

    # Agent nodes
    graph.add_node("clarifier", _make_agent_node(clarifier_node, mcp_conn, system_id))
    graph.add_node("clarification_gate", _make_clarification_gate())
    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("coder", _make_agent_node(coder_node, mcp_conn, system_id))
    graph.add_node("increment_fix", _increment_fix_attempts)
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))
    graph.add_node("activator", _make_agent_node(activator_node, mcp_conn, system_id))

    # Approval gates
    graph.add_node("approve_plan", _make_approval_gate(
        "planning",
        lambda s: f"## Proposed Plan\n\n{s.get('plan', 'No plan generated')}",
    ))
    graph.add_node("approve_code", _make_approval_gate(
        "reviewing",
        lambda s: (
            f"## Code Review Results\n\n"
            f"**Review pass:** {s.get('review_pass', False)}\n\n"
            f"**Findings:** {len(s.get('review_findings', []))}\n\n"
            f"**Fix attempts:** {s.get('fix_attempts', 0)}/{MAX_FIX_ATTEMPTS}\n\n"
            f"**Objects:** {', '.join(s.get('created_objects', []))}"
        ),
    ))
    graph.add_node("approve_activation", _make_approval_gate(
        "activating",
        lambda s: (
            f"## Ready to Activate\n\n"
            f"**Objects:** {', '.join(s.get('created_objects', []))}\n\n"
            f"Approve to activate all objects and add to transport."
        ),
    ))

    # Entry point — START with clarifier
    graph.set_entry_point("clarifier")

    # Flow: clarifier → clarification_gate → planner → approve_plan → coder → reviewer → approve_code → activator
    graph.add_edge("clarifier", "clarification_gate")
    graph.add_edge("clarification_gate", "planner")
    graph.add_edge("planner", "approve_plan")
    graph.add_conditional_edges("approve_plan", _after_plan_approval,
                                {"planner": "planner", "coder": "coder"})
    graph.add_edge("coder", "reviewer")
    graph.add_conditional_edges("reviewer", _after_reviewer,
                                {"approve_code": "approve_code", "coder": "increment_fix"})
    graph.add_edge("increment_fix", "coder")
    graph.add_conditional_edges("approve_code", _after_code_approval,
                                {"coder": "coder", "tester": "approve_activation"})
    graph.add_conditional_edges("approve_activation", _after_activation_approval,
                                {"activator": "activator", END: END})
    graph.add_edge("activator", END)

    return graph


def build_review_only_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a review-only graph: planner → reviewer → approve → [coder → reviewer] → END."""
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))
    graph.add_node("coder", _make_agent_node(coder_node, mcp_conn, system_id))
    graph.add_node("increment_fix", _increment_fix_attempts)
    graph.add_node("approve_review", _make_approval_gate(
        "reviewing",
        lambda s: f"## Review Findings\n\n{s.get('review_findings', [])}",
    ))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "reviewer")
    graph.add_conditional_edges("reviewer", _after_reviewer,
                                {"approve_code": "approve_review", "coder": "increment_fix"})
    graph.add_edge("increment_fix", "coder")
    graph.add_edge("coder", "reviewer")
    graph.add_edge("approve_review", END)

    return graph


def build_transport_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a transport management graph: planner → approve → activator → END."""
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("activator", _make_agent_node(activator_node, mcp_conn, system_id))
    graph.add_node("approve_plan", _make_approval_gate(
        "planning",
        lambda s: f"## Transport Plan\n\n{s.get('plan', 'No plan')}",
    ))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "approve_plan")
    graph.add_conditional_edges("approve_plan", _after_plan_approval,
                                {"planner": "planner", "coder": "activator"})
    graph.add_edge("activator", END)

    return graph


def build_debug_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a debug/diagnose graph: planner → tester → reviewer → END."""
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("tester", _make_agent_node(tester_node, mcp_conn, system_id))
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "tester")
    graph.add_edge("tester", "reviewer")
    graph.add_edge("reviewer", END)

    return graph


def build_simplified_workflow_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a simplified graph: planner → approve → coder → reviewer → activate → END.

    Used for simpler creation tasks (data elements, etc.) that don't need testing.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("clarifier", _make_agent_node(clarifier_node, mcp_conn, system_id))
    graph.add_node("clarification_gate", _make_clarification_gate())
    graph.add_node("coder", _make_agent_node(coder_node, mcp_conn, system_id))
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))
    graph.add_node("increment_fix", _increment_fix_attempts)
    graph.add_node("activator", _make_agent_node(activator_node, mcp_conn, system_id))

    graph.add_node("approve_plan", _make_approval_gate(
        "planning",
        lambda s: f"## Proposed Plan\n\n{s.get('plan', 'No plan generated')}",
    ))
    graph.add_node("approve_activation", _make_approval_gate(
        "activating",
        lambda s: (
            f"## Ready to Activate\n\n"
            f"**Review pass:** {s.get('review_pass', False)}\n\n"
            f"**Objects:** {', '.join(s.get('created_objects', []))}"
        ),
    ))

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", _after_planner,
                                {"clarifier": "clarifier", "approve_plan": "approve_plan"})
    graph.add_conditional_edges("clarifier", _after_clarifier,
                                {"clarification_gate": "clarification_gate", "planner": "planner"})
    graph.add_edge("clarification_gate", "planner")
    graph.add_conditional_edges("approve_plan", _after_plan_approval,
                                {"planner": "planner", "coder": "coder"})
    graph.add_edge("coder", "reviewer")
    graph.add_conditional_edges("reviewer", _after_reviewer,
                                {"approve_code": "approve_activation", "coder": "increment_fix"})
    graph.add_edge("increment_fix", "coder")
    graph.add_conditional_edges("approve_activation", _after_activation_approval,
                                {"activator": "activator", END: END})
    graph.add_edge("activator", END)

    return graph


def build_analysis_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build an analysis graph: planner → analyzer → approve_analysis → END.

    Used for performance analysis, dependency mapping, etc.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("analyzer", _make_agent_node(analyzer_node, mcp_conn, system_id))
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))
    graph.add_node("approve_plan", _make_approval_gate(
        "planning",
        lambda s: f"## Analysis Plan\n\n{s.get('plan', 'No plan')}",
    ))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "approve_plan")
    graph.add_conditional_edges("approve_plan", _after_plan_approval,
                                {"planner": "planner", "coder": "analyzer"})
    graph.add_edge("analyzer", "reviewer")
    graph.add_edge("reviewer", END)

    return graph


def build_dump_analysis_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a dump analysis graph: planner → analyzer → reviewer → [coder fix] → END.

    Used for investigating runtime dumps and suggesting/applying fixes.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("analyzer", _make_agent_node(analyzer_node, mcp_conn, system_id))
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))
    graph.add_node("coder", _make_agent_node(coder_node, mcp_conn, system_id))
    graph.add_node("approve_fix", _make_approval_gate(
        "reviewing",
        lambda s: (
            f"## Dump Analysis & Fix Proposal\n\n"
            f"**Analysis:** {(s.get('analysis_summary') or 'N/A')[:500]}\n\n"
            f"**Review pass:** {s.get('review_pass', False)}"
        ),
    ))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "analyzer")
    graph.add_edge("analyzer", "reviewer")
    graph.add_edge("reviewer", "approve_fix")

    def _after_fix_approval(state: WorkflowState) -> str:
        last_approval = (state.get("approvals") or [{}])[-1]
        if last_approval.get("status") == "rejected":
            return END
        return "coder"

    graph.add_conditional_edges("approve_fix", _after_fix_approval,
                                {"coder": "coder", END: END})
    graph.add_edge("coder", END)

    return graph


def build_documentation_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a documentation graph: planner → analyzer → documenter → END.

    Used for generating technical documentation for ABAP objects.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("analyzer", _make_agent_node(analyzer_node, mcp_conn, system_id))
    graph.add_node("documenter", _make_agent_node(documenter_node, mcp_conn, system_id))
    graph.add_node("approve_plan", _make_approval_gate(
        "planning",
        lambda s: f"## Documentation Plan\n\n{s.get('plan', 'No plan')}",
    ))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "approve_plan")
    graph.add_conditional_edges("approve_plan", _after_plan_approval,
                                {"planner": "planner", "coder": "analyzer"})
    graph.add_conditional_edges("analyzer", _after_analyzer,
                                {"documenter": "documenter", "reviewer": "documenter"})
    graph.add_edge("documenter", END)

    return graph


def build_migration_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a migration graph: planner → approve → migrator → reviewer → END.

    Used for migrating objects between packages.
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("migrator", _make_agent_node(migrator_node, mcp_conn, system_id))
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))
    graph.add_node("approve_plan", _make_approval_gate(
        "planning",
        lambda s: f"## Migration Plan\n\n{s.get('plan', 'No plan')}",
    ))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "approve_plan")
    graph.add_conditional_edges("approve_plan", _after_plan_approval,
                                {"planner": "planner", "coder": "migrator"})
    graph.add_conditional_edges("migrator", _after_migrator,
                                {"reviewer": "reviewer"})
    graph.add_edge("reviewer", END)

    return graph


def build_rap_workflow_graph(
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build a RAP Business Object graph — extended full workflow with analyzer.

    Flow: planner → approve → analyzer → coder → reviewer → tester → activate → END
    """
    graph = StateGraph(WorkflowState)

    graph.add_node("planner", _make_agent_node(planner_node, mcp_conn, system_id))
    graph.add_node("clarifier", _make_agent_node(clarifier_node, mcp_conn, system_id))
    graph.add_node("clarification_gate", _make_clarification_gate())
    graph.add_node("analyzer", _make_agent_node(analyzer_node, mcp_conn, system_id))
    graph.add_node("coder", _make_agent_node(coder_node, mcp_conn, system_id))
    graph.add_node("increment_fix", _increment_fix_attempts)
    graph.add_node("reviewer", _make_agent_node(reviewer_node, mcp_conn, system_id))
    graph.add_node("tester", _make_agent_node(tester_node, mcp_conn, system_id))
    graph.add_node("activator", _make_agent_node(activator_node, mcp_conn, system_id))

    graph.add_node("approve_plan", _make_approval_gate(
        "planning",
        lambda s: f"## RAP BO Plan\n\n{s.get('plan', 'No plan generated')}",
    ))
    graph.add_node("approve_code", _make_approval_gate(
        "reviewing",
        lambda s: (
            f"## Code Review\n\n"
            f"**Review pass:** {s.get('review_pass', False)}\n\n"
            f"**Findings:** {len(s.get('review_findings', []))}"
        ),
    ))
    graph.add_node("approve_activation", _make_approval_gate(
        "activating",
        lambda s: (
            f"## Ready to Activate\n\n"
            f"**Tests pass:** {s.get('tests_pass', False)}\n\n"
            f"**Objects:** {', '.join(s.get('created_objects', []))}"
        ),
    ))

    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", _after_planner,
                                {"clarifier": "clarifier", "approve_plan": "approve_plan"})
    graph.add_conditional_edges("clarifier", _after_clarifier,
                                {"clarification_gate": "clarification_gate", "planner": "planner"})
    graph.add_edge("clarification_gate", "planner")
    graph.add_conditional_edges("approve_plan", _after_plan_approval,
                                {"planner": "planner", "coder": "analyzer"})
    graph.add_edge("analyzer", "coder")
    graph.add_edge("coder", "reviewer")
    graph.add_conditional_edges("reviewer", _after_reviewer,
                                {"approve_code": "approve_code", "coder": "increment_fix"})
    graph.add_edge("increment_fix", "coder")
    graph.add_conditional_edges("approve_code", _after_code_approval,
                                {"coder": "coder", "tester": "tester"})
    graph.add_conditional_edges("tester", _after_tester,
                                {"approve_activation": "approve_activation", "reviewer": "reviewer"})
    graph.add_conditional_edges("approve_activation", _after_activation_approval,
                                {"activator": "activator", END: END})
    graph.add_edge("activator", END)

    return graph


# ──────────────────────────────────────────────────────────────────────
# Registry: workflow type → graph builder
# ──────────────────────────────────────────────────────────────────────

WORKFLOW_GRAPH_BUILDERS: dict[WorkflowType, Any] = {
    # Full workflow (plan → clarify → code → review → test → activate)
    "create_report": build_full_workflow_graph,
    "create_class": build_full_workflow_graph,
    "create_cds_view": build_full_workflow_graph,
    "create_function_module": build_full_workflow_graph,
    "create_table": build_full_workflow_graph,
    "create_interface": build_full_workflow_graph,
    "create_ui5_app": build_full_workflow_graph,
    "enhance_object": build_full_workflow_graph,
    "refactor_object": build_full_workflow_graph,
    "test_creation": build_full_workflow_graph,
    "amdp_creation": build_full_workflow_graph,
    # Simplified (plan → code → review → activate, no test)
    "create_data_element": build_simplified_workflow_graph,
    # RAP (plan → analyze → code → review → test → activate)
    "create_rap_bo": build_rap_workflow_graph,
    # Review-only
    "code_review": build_review_only_graph,
    # Transport / activation
    "transport_management": build_transport_graph,
    "mass_activation": build_transport_graph,
    "git_operations": build_transport_graph,
    # Debug / diagnose
    "debug_diagnose": build_debug_graph,
    # Analysis
    "performance_analysis": build_analysis_graph,
    "dump_analysis": build_dump_analysis_graph,
    # Documentation
    "documentation": build_documentation_graph,
    # Migration
    "migration": build_migration_graph,
}


def build_workflow_graph(
    workflow_type: WorkflowType,
    mcp_conn: MCPConnection,
    system_id: str,
) -> StateGraph:
    """Build the appropriate LangGraph graph for the given workflow type."""
    builder_fn = WORKFLOW_GRAPH_BUILDERS.get(workflow_type, build_full_workflow_graph)
    return builder_fn(mcp_conn, system_id)
