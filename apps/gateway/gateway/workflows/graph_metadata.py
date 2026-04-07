"""Graph metadata export for UI visualization.

Provides the graph structure (nodes + edges) for each workflow type so the
frontend can render a DAG visualizer showing the agent pipeline.
"""

from __future__ import annotations

from typing import Any

from .state import WorkflowType

# ──────────────────────────────────────────────────────────────────────
# Node metadata
# ──────────────────────────────────────────────────────────────────────

NODE_METADATA: dict[str, dict[str, Any]] = {
    "planner": {
        "type": "agent",
        "label": "Planner",
        "icon": "📋",
        "description": "Analyses the request and produces a step-by-step plan",
    },
    "clarifier": {
        "type": "agent",
        "label": "Clarifier",
        "icon": "❓",
        "description": "Asks targeted questions to resolve ambiguity",
    },
    "clarification_gate": {
        "type": "gate",
        "label": "User Input",
        "icon": "💬",
        "description": "Pauses for user to answer clarifying questions",
    },
    "coder": {
        "type": "agent",
        "label": "Coder",
        "icon": "💻",
        "description": "Implements ABAP objects according to the approved plan",
    },
    "reviewer": {
        "type": "agent",
        "label": "Reviewer",
        "icon": "🔍",
        "description": "Reviews code quality, runs ATC checks",
    },
    "tester": {
        "type": "agent",
        "label": "Tester",
        "icon": "🧪",
        "description": "Runs unit tests and checks for runtime issues",
    },
    "activator": {
        "type": "agent",
        "label": "Activator",
        "icon": "🚀",
        "description": "Activates objects and manages transport requests",
    },
    "analyzer": {
        "type": "agent",
        "label": "Analyzer",
        "icon": "📊",
        "description": "Deep code analysis, performance profiling, dependency mapping",
    },
    "documenter": {
        "type": "agent",
        "label": "Documenter",
        "icon": "📝",
        "description": "Generates technical documentation",
    },
    "migrator": {
        "type": "agent",
        "label": "Migrator",
        "icon": "📦",
        "description": "Handles object migration between packages",
    },
    "approve_plan": {
        "type": "approval",
        "label": "Approve Plan",
        "icon": "✋",
        "description": "User reviews and approves the proposed plan",
    },
    "approve_code": {
        "type": "approval",
        "label": "Approve Code",
        "icon": "✋",
        "description": "User reviews code and review findings",
    },
    "approve_activation": {
        "type": "approval",
        "label": "Approve Activation",
        "icon": "✋",
        "description": "User approves object activation",
    },
    "approve_review": {
        "type": "approval",
        "label": "Approve Review",
        "icon": "✋",
        "description": "User reviews the findings",
    },
    "approve_fix": {
        "type": "approval",
        "label": "Approve Fix",
        "icon": "✋",
        "description": "User approves the proposed fix",
    },
    "increment_fix": {
        "type": "internal",
        "label": "Retry Counter",
        "icon": "🔄",
        "description": "Increments the fix attempt counter",
    },
}


# ──────────────────────────────────────────────────────────────────────
# Graph definitions per workflow type
# ──────────────────────────────────────────────────────────────────────

def _full_workflow_graph() -> dict[str, Any]:
    """Standard full workflow graph structure."""
    return {
        "nodes": [
            "planner", "clarifier", "clarification_gate",
            "approve_plan", "coder", "reviewer", "increment_fix",
            "approve_code", "tester", "approve_activation", "activator",
        ],
        "edges": [
            {"from": "planner", "to": "clarifier", "condition": "needs_clarification"},
            {"from": "planner", "to": "approve_plan", "condition": "plan_ready"},
            {"from": "clarifier", "to": "clarification_gate", "condition": "has_questions"},
            {"from": "clarifier", "to": "planner", "condition": "answered"},
            {"from": "clarification_gate", "to": "planner"},
            {"from": "approve_plan", "to": "planner", "condition": "rejected"},
            {"from": "approve_plan", "to": "coder", "condition": "approved"},
            {"from": "coder", "to": "reviewer"},
            {"from": "reviewer", "to": "approve_code", "condition": "pass"},
            {"from": "reviewer", "to": "increment_fix", "condition": "fail"},
            {"from": "increment_fix", "to": "coder"},
            {"from": "approve_code", "to": "coder", "condition": "rejected"},
            {"from": "approve_code", "to": "tester", "condition": "approved"},
            {"from": "tester", "to": "approve_activation", "condition": "pass"},
            {"from": "tester", "to": "reviewer", "condition": "fail"},
            {"from": "approve_activation", "to": "activator", "condition": "approved"},
            {"from": "approve_activation", "to": "END", "condition": "rejected"},
            {"from": "activator", "to": "END"},
        ],
        "entry": "planner",
    }


def _simplified_workflow_graph() -> dict[str, Any]:
    """Simplified workflow (no test step)."""
    return {
        "nodes": [
            "planner", "clarifier", "clarification_gate",
            "approve_plan", "coder", "reviewer", "increment_fix",
            "approve_activation", "activator",
        ],
        "edges": [
            {"from": "planner", "to": "clarifier", "condition": "needs_clarification"},
            {"from": "planner", "to": "approve_plan", "condition": "plan_ready"},
            {"from": "clarifier", "to": "clarification_gate", "condition": "has_questions"},
            {"from": "clarifier", "to": "planner", "condition": "answered"},
            {"from": "clarification_gate", "to": "planner"},
            {"from": "approve_plan", "to": "planner", "condition": "rejected"},
            {"from": "approve_plan", "to": "coder", "condition": "approved"},
            {"from": "coder", "to": "reviewer"},
            {"from": "reviewer", "to": "approve_activation", "condition": "pass"},
            {"from": "reviewer", "to": "increment_fix", "condition": "fail"},
            {"from": "increment_fix", "to": "coder"},
            {"from": "approve_activation", "to": "activator", "condition": "approved"},
            {"from": "approve_activation", "to": "END", "condition": "rejected"},
            {"from": "activator", "to": "END"},
        ],
        "entry": "planner",
    }


def _review_only_graph() -> dict[str, Any]:
    """Review-only graph."""
    return {
        "nodes": [
            "planner", "reviewer", "coder", "increment_fix", "approve_review",
        ],
        "edges": [
            {"from": "planner", "to": "reviewer"},
            {"from": "reviewer", "to": "approve_review", "condition": "pass"},
            {"from": "reviewer", "to": "increment_fix", "condition": "fail"},
            {"from": "increment_fix", "to": "coder"},
            {"from": "coder", "to": "reviewer"},
            {"from": "approve_review", "to": "END"},
        ],
        "entry": "planner",
    }


def _transport_graph() -> dict[str, Any]:
    """Transport management graph."""
    return {
        "nodes": ["planner", "approve_plan", "activator"],
        "edges": [
            {"from": "planner", "to": "approve_plan"},
            {"from": "approve_plan", "to": "planner", "condition": "rejected"},
            {"from": "approve_plan", "to": "activator", "condition": "approved"},
            {"from": "activator", "to": "END"},
        ],
        "entry": "planner",
    }


def _debug_graph() -> dict[str, Any]:
    """Debug/diagnose graph."""
    return {
        "nodes": ["planner", "tester", "reviewer"],
        "edges": [
            {"from": "planner", "to": "tester"},
            {"from": "tester", "to": "reviewer"},
            {"from": "reviewer", "to": "END"},
        ],
        "entry": "planner",
    }


def _analysis_graph() -> dict[str, Any]:
    """Analysis graph."""
    return {
        "nodes": ["planner", "approve_plan", "analyzer", "reviewer"],
        "edges": [
            {"from": "planner", "to": "approve_plan"},
            {"from": "approve_plan", "to": "planner", "condition": "rejected"},
            {"from": "approve_plan", "to": "analyzer", "condition": "approved"},
            {"from": "analyzer", "to": "reviewer"},
            {"from": "reviewer", "to": "END"},
        ],
        "entry": "planner",
    }


def _dump_analysis_graph() -> dict[str, Any]:
    """Dump analysis graph."""
    return {
        "nodes": ["planner", "analyzer", "reviewer", "approve_fix", "coder"],
        "edges": [
            {"from": "planner", "to": "analyzer"},
            {"from": "analyzer", "to": "reviewer"},
            {"from": "reviewer", "to": "approve_fix"},
            {"from": "approve_fix", "to": "coder", "condition": "approved"},
            {"from": "approve_fix", "to": "END", "condition": "rejected"},
            {"from": "coder", "to": "END"},
        ],
        "entry": "planner",
    }


def _documentation_graph() -> dict[str, Any]:
    """Documentation graph."""
    return {
        "nodes": ["planner", "approve_plan", "analyzer", "documenter"],
        "edges": [
            {"from": "planner", "to": "approve_plan"},
            {"from": "approve_plan", "to": "planner", "condition": "rejected"},
            {"from": "approve_plan", "to": "analyzer", "condition": "approved"},
            {"from": "analyzer", "to": "documenter"},
            {"from": "documenter", "to": "END"},
        ],
        "entry": "planner",
    }


def _migration_graph() -> dict[str, Any]:
    """Migration graph."""
    return {
        "nodes": ["planner", "approve_plan", "migrator", "reviewer"],
        "edges": [
            {"from": "planner", "to": "approve_plan"},
            {"from": "approve_plan", "to": "planner", "condition": "rejected"},
            {"from": "approve_plan", "to": "migrator", "condition": "approved"},
            {"from": "migrator", "to": "reviewer"},
            {"from": "reviewer", "to": "END"},
        ],
        "entry": "planner",
    }


def _rap_workflow_graph() -> dict[str, Any]:
    """RAP Business Object graph."""
    return {
        "nodes": [
            "planner", "clarifier", "clarification_gate",
            "approve_plan", "analyzer", "coder", "reviewer", "increment_fix",
            "approve_code", "tester", "approve_activation", "activator",
        ],
        "edges": [
            {"from": "planner", "to": "clarifier", "condition": "needs_clarification"},
            {"from": "planner", "to": "approve_plan", "condition": "plan_ready"},
            {"from": "clarifier", "to": "clarification_gate", "condition": "has_questions"},
            {"from": "clarifier", "to": "planner", "condition": "answered"},
            {"from": "clarification_gate", "to": "planner"},
            {"from": "approve_plan", "to": "planner", "condition": "rejected"},
            {"from": "approve_plan", "to": "analyzer", "condition": "approved"},
            {"from": "analyzer", "to": "coder"},
            {"from": "coder", "to": "reviewer"},
            {"from": "reviewer", "to": "approve_code", "condition": "pass"},
            {"from": "reviewer", "to": "increment_fix", "condition": "fail"},
            {"from": "increment_fix", "to": "coder"},
            {"from": "approve_code", "to": "coder", "condition": "rejected"},
            {"from": "approve_code", "to": "tester", "condition": "approved"},
            {"from": "tester", "to": "approve_activation", "condition": "pass"},
            {"from": "tester", "to": "reviewer", "condition": "fail"},
            {"from": "approve_activation", "to": "activator", "condition": "approved"},
            {"from": "approve_activation", "to": "END", "condition": "rejected"},
            {"from": "activator", "to": "END"},
        ],
        "entry": "planner",
    }


# ──────────────────────────────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────────────────────────────

_GRAPH_METADATA: dict[str, Any] = {
    # Full workflow
    "create_report": _full_workflow_graph,
    "create_class": _full_workflow_graph,
    "create_cds_view": _full_workflow_graph,
    "create_function_module": _full_workflow_graph,
    "create_table": _full_workflow_graph,
    "create_interface": _full_workflow_graph,
    "create_ui5_app": _full_workflow_graph,
    "enhance_object": _full_workflow_graph,
    "refactor_object": _full_workflow_graph,
    "test_creation": _full_workflow_graph,
    "amdp_creation": _full_workflow_graph,
    # Simplified
    "create_data_element": _simplified_workflow_graph,
    # RAP
    "create_rap_bo": _rap_workflow_graph,
    # Review-only
    "code_review": _review_only_graph,
    # Transport
    "transport_management": _transport_graph,
    "mass_activation": _transport_graph,
    "git_operations": _transport_graph,
    # Debug
    "debug_diagnose": _debug_graph,
    # Analysis
    "performance_analysis": _analysis_graph,
    "dump_analysis": _dump_analysis_graph,
    # Documentation
    "documentation": _documentation_graph,
    # Migration
    "migration": _migration_graph,
}


def get_graph_metadata(workflow_type: str) -> dict[str, Any] | None:
    """Get the graph structure for a workflow type.

    Returns a dict with ``nodes`` (list of node IDs), ``edges`` (list of
    {from, to, condition?}), and ``entry`` (entry node ID).
    Each node ID can be looked up in ``NODE_METADATA`` for display info.
    """
    builder = _GRAPH_METADATA.get(workflow_type)
    if not builder:
        return None
    graph = builder()
    # Enrich nodes with metadata
    enriched_nodes = []
    for node_id in graph["nodes"]:
        meta = NODE_METADATA.get(node_id, {
            "type": "unknown",
            "label": node_id,
            "icon": "⚙️",
            "description": "",
        })
        enriched_nodes.append({"id": node_id, **meta})
    graph["nodes"] = enriched_nodes
    return graph


def get_all_workflow_types() -> list[dict[str, Any]]:
    """Return all available workflow types with descriptions and categories."""
    from .router import _WORKFLOW_DESCRIPTIONS

    categories = {
        "create_report": "creation",
        "create_class": "creation",
        "create_cds_view": "creation",
        "create_function_module": "creation",
        "create_table": "creation",
        "create_data_element": "creation",
        "create_interface": "creation",
        "create_rap_bo": "creation",
        "create_ui5_app": "creation",
        "enhance_object": "creation",
        "test_creation": "creation",
        "amdp_creation": "creation",
        "code_review": "review",
        "refactor_object": "review",
        "transport_management": "management",
        "mass_activation": "management",
        "git_operations": "management",
        "migration": "management",
        "debug_diagnose": "analysis",
        "performance_analysis": "analysis",
        "dump_analysis": "analysis",
        "documentation": "documentation",
    }

    icons = {
        "create_report": "📄",
        "create_class": "🏗️",
        "create_cds_view": "📊",
        "create_function_module": "⚡",
        "create_table": "🗃️",
        "create_data_element": "🔤",
        "create_interface": "🔌",
        "create_rap_bo": "🏢",
        "create_ui5_app": "🌐",
        "enhance_object": "➕",
        "test_creation": "🧪",
        "amdp_creation": "💾",
        "code_review": "🔍",
        "refactor_object": "♻️",
        "transport_management": "🚚",
        "mass_activation": "⚡",
        "git_operations": "📦",
        "migration": "📦",
        "debug_diagnose": "🪲",
        "performance_analysis": "📈",
        "dump_analysis": "💥",
        "documentation": "📝",
    }

    result = []
    for wf_type, description in _WORKFLOW_DESCRIPTIONS.items():
        graph_meta = get_graph_metadata(wf_type)
        agent_count = len([
            n for n in (graph_meta or {}).get("nodes", [])
            if isinstance(n, dict) and n.get("type") == "agent"
        ])
        result.append({
            "type": wf_type,
            "description": description,
            "category": categories.get(wf_type, "other"),
            "icon": icons.get(wf_type, "⚙️"),
            "agent_count": agent_count,
            "has_approval_gates": any(
                isinstance(n, dict) and n.get("type") == "approval"
                for n in (graph_meta or {}).get("nodes", [])
            ),
        })
    return result
