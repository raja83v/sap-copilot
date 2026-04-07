"""Workflow state schema shared across all LangGraph agent graphs.

WorkflowState is the TypedDict that flows through every node in the graph.
It carries the conversation, plan, artifacts, review findings, test results,
approval requests, and metadata needed by each agent.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

# ---------------------------------------------------------------------------
# Enums / Literals
# ---------------------------------------------------------------------------

WorkflowType = Literal[
    "create_report",
    "create_class",
    "create_cds_view",
    "create_function_module",
    "create_table",
    "create_data_element",
    "create_interface",
    "create_rap_bo",
    "create_ui5_app",
    "enhance_object",
    "code_review",
    "transport_management",
    "debug_diagnose",
    "refactor_object",
    "performance_analysis",
    "dump_analysis",
    "mass_activation",
    "git_operations",
    "documentation",
    "migration",
    "test_creation",
    "amdp_creation",
]

WorkflowPhase = Literal[
    "planning",
    "clarifying",
    "coding",
    "reviewing",
    "testing",
    "analyzing",
    "documenting",
    "migrating",
    "activating",
    "completed",
    "failed",
    "paused",       # waiting for user approval / response
]

AgentRole = Literal[
    "planner",
    "clarifier",
    "coder",
    "reviewer",
    "tester",
    "activator",
    "analyzer",
    "documenter",
    "migrator",
]

ApprovalStatus = Literal["pending", "approved", "rejected"]

StepStatus = Literal["running", "completed", "failed", "skipped"]

# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------

class ApprovalRequest(TypedDict, total=False):
    id: str
    phase: str
    status: ApprovalStatus
    details: str           # markdown summary of what's being approved
    requested_at: float
    responded_at: float | None
    feedback: str          # user feedback on rejection


class WorkflowStep(TypedDict, total=False):
    id: str
    agent: AgentRole
    action: str            # human-readable description of what happened
    status: StepStatus
    started_at: float
    completed_at: float | None
    result: str | None     # summary of step outcome
    tool_calls: list[dict[str, Any]]  # recorded tool invocations


class ClarificationQA(TypedDict, total=False):
    id: str
    question: str
    question_type: str         # "text" | "select" | "confirm"
    options: list[str] | None  # for select-type questions
    default: str | None
    required: bool
    answer: str | None
    answered_at: float | None


# ---------------------------------------------------------------------------
# Main workflow state passed through the LangGraph graph
# ---------------------------------------------------------------------------

class WorkflowState(TypedDict, total=False):
    """Shared state flowing through every node in a workflow graph.

    Fields annotated with ``Annotated[..., add_messages]`` use LangGraph's
    message-merging reducer so each node can simply return new messages
    and they are appended automatically.
    """

    # ── Identity ──
    workflow_id: str
    workflow_type: WorkflowType
    system_id: str
    session_id: str

    # ── Phase tracking ──
    phase: WorkflowPhase
    previous_phase: WorkflowPhase | None

    # ── LangChain messages (reducer-based) ──
    messages: list[BaseMessage]

    # ── Planning ──
    plan: str | None              # approved plan text (markdown)
    user_request: str             # original user message

    # ── Clarification ──
    clarifications: list[ClarificationQA]
    needs_clarification: bool     # set by Clarifier → gates back to user

    # ── Coding artifacts ──
    artifacts: dict[str, str]     # object_name → source code / definition
    created_objects: list[str]    # names of objects created this workflow

    # ── Review ──
    review_findings: list[dict[str, Any]]
    review_pass: bool             # True if no blocking issues found

    # ── Testing ──
    test_results: dict[str, Any]
    tests_pass: bool

    # ── Analysis (analyzer agent) ──
    analysis_results: dict[str, Any]   # performance data, dependency maps, etc.
    analysis_summary: str | None       # human-readable analysis summary

    # ── Documentation (documenter agent) ──
    documentation: str | None          # generated documentation text

    # ── Migration (migrator agent) ──
    migration_log: list[dict[str, Any]]  # migration actions performed

    # ── Approval ──
    approvals: list[ApprovalRequest]
    current_approval: ApprovalRequest | None

    # ── Steps log ──
    steps: list[WorkflowStep]

    # ── Metadata (package, transport, object type etc.) ──
    metadata: dict[str, Any]

    # ── Error ──
    error: str | None

    # ── Retry counter (for Coder→Reviewer fix loops) ──
    fix_attempts: int

    # ── Graph type used (for visualization) ──
    graph_type: str | None

    # ── Timestamps ──
    created_at: float
    updated_at: float


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def new_workflow_state(
    *,
    workflow_type: WorkflowType,
    system_id: str,
    session_id: str,
    user_request: str,
) -> WorkflowState:
    """Create a fresh WorkflowState with sensible defaults."""
    now = time.time()
    return WorkflowState(
        workflow_id=str(uuid.uuid4()),
        workflow_type=workflow_type,
        system_id=system_id,
        session_id=session_id,
        phase="clarifying",
        previous_phase=None,
        messages=[],
        plan=None,
        user_request=user_request,
        clarifications=[],
        needs_clarification=False,
        artifacts={},
        created_objects=[],
        review_findings=[],
        review_pass=False,
        test_results={},
        tests_pass=False,
        analysis_results={},
        analysis_summary=None,
        documentation=None,
        migration_log=[],
        approvals=[],
        current_approval=None,
        steps=[],
        metadata={},
        error=None,
        fix_attempts=0,
        graph_type=None,
        created_at=now,
        updated_at=now,
    )
