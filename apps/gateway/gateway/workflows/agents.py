"""Agent node definitions for LangGraph workflow graphs.

Each agent is a function ``(WorkflowState) -> dict`` that can be used as a
LangGraph node.  Agents:

1. Build a scoped system prompt.
2. Filter MCP tools to only those relevant for the agent's role.
3. Run an LLM chat loop (with tool calling) using the shared AsyncOpenAI client.
4. Return a state-update dict (e.g. new messages, phase changes, artifacts).

Heavy MCP tool execution still goes through ``MCPConnection.call_tool``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ..mcp_manager import MCPConnection, MCPError, mcp_manager
from ..routes.llm import get_litellm_api_key, get_litellm_base_url
from ..config import settings
from .state import AgentRole, WorkflowPhase, WorkflowState, WorkflowStep
from .tool_filter import filter_tools_for_agent

logger = logging.getLogger("gateway.workflows.agents")

# Strings that hint the MCP / SAP connection is dead or stale
_CONNECTION_ERROR_HINTS = (
    "getaddrinfo", "connect", "timed out", "connection reset",
    "connection refused", "broken pipe", "eof", "closed",
    "mcp process exited",
)


def _is_connection_error(error: Exception) -> bool:
    """Detect errors that suggest the MCP/SAP connection is stale."""
    msg = str(error).lower()
    return any(hint in msg for hint in _CONNECTION_ERROR_HINTS)


async def _get_mcp_conn_or_reconnect(
    mcp_conn: MCPConnection, system_id: str, context: str = ""
) -> MCPConnection:
    """Return a healthy MCP connection, reconnecting if necessary."""
    if mcp_conn.is_alive:
        return mcp_conn
    logger.warning("MCP connection dead for %s (%s) — attempting reconnect", system_id, context)
    if mcp_manager.has_params(system_id):
        new_conn = await mcp_manager.reconnect(system_id)
        if new_conn and new_conn.is_alive:
            return new_conn
    raise RuntimeError(f"MCP connection lost for system {system_id} and reconnect failed")

# ──────────────────────────────────────────────────────────────────────
# System prompts per role
# ──────────────────────────────────────────────────────────────────────

AGENT_PROMPTS: dict[AgentRole, str] = {
    "planner": """\
You are the **Planner** agent inside SAP Copilot. Your job is to produce a
step-by-step implementation plan for the user's request.

Rules:
- Read existing objects from SAP to understand the current state before planning.
- Output your plan as a numbered Markdown list.
- Each step should be a concrete, verifiable action (e.g. "Create report ZTEST including …").
- Identify the target package and transport if not provided by the user.
- If the request is ambiguous, set `needs_clarification = True` and list your
  clarifying questions instead of a plan.
- Do NOT create or modify any SAP objects — only read and plan.
""",
    "clarifier": """\
You are the **Clarifier** agent inside SAP Copilot. You are the FIRST agent
in the workflow. Your job is to ask the user all the essential questions needed
before development can begin.

Rules:
- ALWAYS ask questions — never skip this step.
- Ask about: package name (or $TMP for local), transport request (or local object),
  naming conventions, specific requirements, error handling preferences.
- Ask 3-5 targeted questions in a single batch.
- Frame questions so they have short, definitive answers.
- Format each question on its own line starting with a number and question mark.
- Example questions for a report:
  1. What package should this be created in? (e.g., $TMP for local, or ZDEV)
  2. Do you need a transport request, or is this a local object ($TMP)?
  3. What should the report name be? (e.g., ZBP_UPLOAD_REPORT)
  4. Should the upload use a file from the presentation server (local PC) or application server?
  5. Any specific BP fields beyond the standard ones?
""",
    "coder": """\
You are the **Coder** agent inside SAP Copilot. Your job is to implement ABAP
objects according to the approved plan.

Rules:
- Follow the plan step by step. Do not skip steps.
- Always read the current source of an object before editing it.
- After writing source, call SyntaxCheck to verify.
- Record each created/modified object name in your response.
- If syntax errors remain after 2 attempts, report the failure rather than looping.
- Use proper ABAP formatting and naming conventions.
""",
    "reviewer": """\
You are the **Reviewer** agent inside SAP Copilot. Your job is to review the code
produced by the Coder.

Rules:
- Read the source of every object mentioned in the plan / artifacts.
- Run ATC checks (RunATCCheck) on each object.
- List any findings as a Markdown table: | Object | Severity | Message |.
- Set `review_pass = True` only when there are no errors or critical warnings.
- If issues are found, describe what needs to change so the Coder can fix them.
""",
    "tester": """\
You are the **Tester** agent inside SAP Copilot. Your job is to verify the
implementation by running unit tests and checking for runtime issues.

Rules:
- Run unit tests (RunUnitTests) on each relevant class or program.
- Summarise results: passed, failed, and skipped counts.
- If no unit test class exists and one can reasonably be created, suggest it
  but do NOT create it without approval.
- Set `tests_pass = True` only if all tests pass.
""",
    "activator": """\
You are the **Activator** agent inside SAP Copilot. Your job is to activate
objects and manage the transport request.

Rules:
- Activate each inactive object (use ActivateList or Activate).
- Verify activation succeeded by checking for errors.
- If a transport was specified, add all created objects to it.
- Summarise the transport contents and status.
""",
    "analyzer": """\
You are the **Analyzer** agent inside SAP Copilot. Your job is to perform
deep code analysis, performance profiling, and dependency mapping.

Rules:
- Use GetCallGraph, AnalyzeCallGraph, GetCallersOf, GetCalleesOf for dependency analysis.
- Use ListDumps, GetDump, ListTraces, GetTrace, GetTraceAnalysis for performance/dump analysis.
- Use GetObjectStructure, GetObjectExplorer for structural analysis.
- Use FindReferences, GetUsageLocations for impact analysis.
- Present findings in structured tables with severity levels.
- Provide actionable recommendations, not just raw data.
- For performance analysis, identify hot spots and suggest optimizations.
- For dump analysis, identify root cause and suggest fixes.
""",
    "documenter": """\
You are the **Documenter** agent inside SAP Copilot. Your job is to generate
comprehensive technical documentation for ABAP objects.

Rules:
- Read the source code of all relevant objects using GetSource, GetClass, etc.
- Analyse class hierarchies using GetTypeHierarchy and GetClassComponents.
- Document: purpose, parameters, return values, exceptions, dependencies.
- Use Markdown formatting with proper headings and code blocks.
- Include usage examples where appropriate.
- Document relationships between objects (calls, implements, extends).
- Generate both summary and detailed documentation sections.
""",
    "migrator": """\
You are the **Migrator** agent inside SAP Copilot. Your job is to handle
object migration between packages and transport management.

Rules:
- Read the current state of objects before migration.
- Create transport requests if needed (CreateTransport).
- Move objects between packages by updating their package assignment.
- Add all affected objects to the transport (AddToTransport).
- Verify all objects are properly assigned after migration.
- Report a summary of all migration actions performed.
- Do NOT release transports without explicit user approval.
""",
}


# ──────────────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────────────

def _convert_mcp_tools_to_openai(mcp_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to OpenAI function-calling format."""
    openai_tools = []
    for tool in mcp_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
            },
        })
    return openai_tools


def _extract_result_text(result: Any) -> str:
    """Extract text from MCP tool result."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list):
            texts = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            if texts:
                return "\n".join(texts)
        return json.dumps(result, indent=2)
    return str(result)


async def _get_openai_client():
    """Build an AsyncOpenAI client pointing at the LiteLLM proxy."""
    from openai import AsyncOpenAI
    base_url = get_litellm_base_url()
    api_key = get_litellm_api_key() or "not-needed"
    return AsyncOpenAI(base_url=f"{base_url}/v1", api_key=api_key)


async def _run_agent_llm_loop(
    *,
    role: AgentRole,
    state: WorkflowState,
    mcp_conn: MCPConnection,
    system_id: str,
    extra_context: str = "",
    max_rounds: int = 10,
) -> dict[str, Any]:
    """Run a tool-calling LLM loop for a given agent role.

    Returns a state-update dict with `messages`, `steps`, and any other
    fields the agent sets (e.g. `review_pass`, `artifacts`).
    """
    client = await _get_openai_client()
    model = settings.litellm_default_model

    # Ensure we have a healthy connection; reconnect if needed
    mcp_conn = await _get_mcp_conn_or_reconnect(mcp_conn, system_id, context=f"{role} list_tools")

    # Filter tools (with retry on connection error)
    try:
        all_mcp_tools = await mcp_conn.list_tools()
    except Exception as list_err:
        if _is_connection_error(list_err):
            logger.warning("list_tools failed for %s in %s — reconnecting: %s", system_id, role, list_err)
            mcp_conn = await _get_mcp_conn_or_reconnect(mcp_conn, system_id, context=f"{role} list_tools retry")
            all_mcp_tools = await mcp_conn.list_tools()
        else:
            raise
    scoped_tools = filter_tools_for_agent(all_mcp_tools, role)
    openai_tools = _convert_mcp_tools_to_openai(scoped_tools)

    # Build messages for the LLM
    system_content = AGENT_PROMPTS[role]
    if extra_context:
        system_content += f"\n\n{extra_context}"

    # Convert LangChain messages to OpenAI dicts
    llm_messages: list[dict[str, Any]] = [{"role": "system", "content": system_content}]
    for msg in state.get("messages", []):
        if isinstance(msg, HumanMessage):
            llm_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            # Skip empty AI messages that have no content and no tool calls
            if not msg.content and not msg.tool_calls:
                continue
            d: dict[str, Any] = {"role": "assistant"}
            if msg.content:
                d["content"] = msg.content
            if msg.tool_calls:
                d["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
                    }
                    for tc in msg.tool_calls
                ]
            llm_messages.append(d)
        elif isinstance(msg, ToolMessage):
            llm_messages.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            })
        elif isinstance(msg, SystemMessage):
            pass  # Already injected our own system prompt

    # Vertex AI / Claude requires the conversation to end with a user message.
    # If the last message is not a user message, append a synthetic user prompt.
    if llm_messages and llm_messages[-1].get("role") != "user":
        llm_messages.append({
            "role": "user",
            "content": f"You are the {role} agent. Please proceed with your task based on the context above.",
        })

    new_messages: list = []
    steps: list[WorkflowStep] = list(state.get("steps", []))

    step_id = str(uuid.uuid4())[:8]
    current_step = WorkflowStep(
        id=step_id,
        agent=role,
        action=f"{role} processing",
        status="running",
        started_at=time.time(),
        tool_calls=[],
    )
    steps.append(current_step)

    rounds = 0
    while rounds < max_rounds:
        rounds += 1
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=llm_messages,
                tools=openai_tools if openai_tools else None,
                tool_choice="auto" if openai_tools else None,
                stream=False,
            )
        except Exception as e:
            logger.error("LLM error in %s agent: %s", role, e)
            current_step["status"] = "failed"
            current_step["result"] = str(e)
            current_step["completed_at"] = time.time()
            return {"steps": steps, "error": f"LLM error in {role}: {e}"}

        choice = response.choices[0]
        assistant_msg = choice.message

        # Build LangChain AIMessage
        tool_calls_list = []
        if assistant_msg.tool_calls:
            for tc in assistant_msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls_list.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "args": args,
                })

        ai_msg = AIMessage(
            content=assistant_msg.content or "",
            tool_calls=tool_calls_list if tool_calls_list else [],
        )
        new_messages.append(ai_msg)
        llm_messages.append({
            "role": "assistant",
            "content": assistant_msg.content or None,
            **({"tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in assistant_msg.tool_calls
            ]} if assistant_msg.tool_calls else {}),
        })

        # If no tool calls, agent is done
        if not assistant_msg.tool_calls:
            break

        # Execute tool calls via MCP
        for tc in assistant_msg.tool_calls:
            name = tc.function.name
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            start_time = time.monotonic()
            result_text = ""
            status = "success"
            try:
                result = await mcp_conn.call_tool(name, arguments)
                result_text = _extract_result_text(result)
            except (MCPError, Exception) as first_err:
                # Auto-reconnect on connection errors, similar to orchestrator
                if _is_connection_error(first_err) and mcp_manager.has_params(system_id):
                    logger.warning(
                        "Tool %s failed with connection error in %s agent: %s — reconnecting",
                        name, role, first_err,
                    )
                    try:
                        mcp_conn = await _get_mcp_conn_or_reconnect(
                            mcp_conn, system_id, context=f"{role} tool {name}",
                        )
                        result = await mcp_conn.call_tool(name, arguments)
                        result_text = _extract_result_text(result)
                    except Exception as retry_err:
                        result_text = f"Error: {retry_err}"
                        status = "error"
                        logger.error(
                            "Reconnect+retry failed for tool %s in %s agent: %s",
                            name, role, retry_err,
                        )
                else:
                    result_text = f"Error: {first_err}"
                    status = "error"
                    logger.error("Tool %s error in %s agent: %s", name, role, first_err)
            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Record tool call in step
            current_step["tool_calls"].append({
                "id": tc.id,
                "name": name,
                "parameters": json.dumps(arguments),
                "result": result_text[:2000],  # truncate for storage
                "duration": duration_ms,
                "status": status,
            })

            tool_msg = ToolMessage(content=result_text, tool_call_id=tc.id)
            new_messages.append(tool_msg)
            llm_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_text,
            })

    current_step["status"] = "completed"
    current_step["completed_at"] = time.time()
    current_step["result"] = (
        new_messages[-1].content[:500] if new_messages and hasattr(new_messages[-1], "content") else ""
    )

    return {"messages": new_messages, "steps": steps}


# ──────────────────────────────────────────────────────────────────────
# Agent nodes — each returns a state-update dict
# ──────────────────────────────────────────────────────────────────────

async def planner_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Analyse the request and produce a plan."""
    extra = f"User request:\n{state.get('user_request', '')}"
    result = await _run_agent_llm_loop(
        role="planner", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra,
    )
    # Extract plan text from the last AI message
    plan_text = None
    needs_clarification = False
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            plan_text = msg.content
            if "clarif" in msg.content.lower() and "?" in msg.content:
                needs_clarification = True
            break
    result["plan"] = plan_text
    result["needs_clarification"] = needs_clarification
    result["phase"] = "clarifying" if needs_clarification else "coding"
    return result


async def clarifier_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Ask clarifying questions — always runs first in the workflow."""
    # Include any existing answers from previous clarification rounds
    existing_answers = ""
    for clar in state.get("clarifications", []):
        if clar.get("answer"):
            existing_answers += f"- {clar.get('question', '')}: {clar['answer']}\n"

    extra = (
        f"User request:\n{state.get('user_request', '')}\n\n"
        f"{'Previous answers:\n' + existing_answers if existing_answers else ''}"
        f"Generate your clarifying questions now. Each question should be on its own numbered line."
    )
    result = await _run_agent_llm_loop(
        role="clarifier", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra, max_rounds=3,
    )

    # Extract questions from the AI response and populate clarifications
    clarifications = list(state.get("clarifications", []))
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            # Parse numbered questions from the response
            import re
            lines = msg.content.split("\n")
            q_idx = 0
            for line in lines:
                stripped = line.strip()
                # Match patterns like "1. What..?" or "1) What..?" or "- What..?"
                if re.match(r'^(\d+[\.\)]\s*|[-*]\s+)', stripped) and "?" in stripped:
                    q_text = re.sub(r'^(\d+[\.\)]\s*|[-*]\s+)', '', stripped).strip()
                    q_id = f"q{len(clarifications) + q_idx + 1}"
                    # Don't add duplicate questions
                    if not any(c.get("question") == q_text for c in clarifications):
                        clarifications.append({
                            "id": q_id,
                            "question": q_text,
                            "question_type": "text",
                            "options": None,
                            "default": None,
                            "required": True,
                            "answer": None,
                            "answered_at": None,
                        })
                        q_idx += 1
            break

    result["clarifications"] = clarifications
    result["needs_clarification"] = len([c for c in clarifications if not c.get("answer")]) > 0
    result["phase"] = "clarifying"
    return result


async def coder_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Implement the plan by creating/editing ABAP objects."""
    plan = state.get("plan", "No plan available")
    existing_artifacts = state.get("artifacts", {})
    review_feedback = ""
    if state.get("review_findings"):
        review_feedback = "\n\nReviewer feedback to address:\n"
        for f in state["review_findings"]:
            review_feedback += f"- {f.get('message', '')}\n"

    extra = (
        f"Approved plan:\n{plan}\n\n"
        f"Already created objects: {list(existing_artifacts.keys())}"
        f"{review_feedback}"
    )
    result = await _run_agent_llm_loop(
        role="coder", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra,
    )
    result["phase"] = "reviewing"

    # ── Extract created_objects and artifacts from tool calls ──
    created_objects = list(state.get("created_objects", []))
    artifacts = dict(state.get("artifacts", {}))
    _OBJECT_TOOLS = {"CreateObject", "WriteSource", "EditSource", "CloneObject"}

    for step in result.get("steps", []):
        for tc in step.get("tool_calls", []):
            tool_name = tc.get("name", "")
            if tool_name not in _OBJECT_TOOLS:
                continue
            try:
                params = json.loads(tc["parameters"]) if isinstance(tc.get("parameters"), str) else tc.get("parameters", {})
            except (json.JSONDecodeError, TypeError):
                continue
            obj_name = params.get("name", "")
            if obj_name and obj_name not in created_objects:
                created_objects.append(obj_name)
            if tool_name == "WriteSource" and params.get("source"):
                artifacts[obj_name] = params["source"]

    result["created_objects"] = created_objects
    result["artifacts"] = artifacts
    logger.info("coder_node extracted objects=%s artifacts=%s", created_objects, list(artifacts.keys()))
    return result


async def reviewer_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Review the code produced by the coder."""
    artifacts = state.get("artifacts", {})
    created = state.get("created_objects", [])
    extra = (
        f"Objects to review: {created or list(artifacts.keys())}\n"
        f"Plan:\n{state.get('plan', 'N/A')}"
    )
    result = await _run_agent_llm_loop(
        role="reviewer", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra,
    )
    # Parse review_pass from the last AI message
    review_pass = True
    review_findings: list[dict[str, Any]] = []
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            content_lower = msg.content.lower()
            if any(kw in content_lower for kw in ("error", "critical", "must fix", "fail")):
                review_pass = False
            # Simple extraction: look for issues
            if "| " in msg.content and "severity" in content_lower:
                for line in msg.content.split("\n"):
                    if "|" in line and "---" not in line and "object" not in line.lower():
                        parts = [p.strip() for p in line.split("|") if p.strip()]
                        if len(parts) >= 3:
                            review_findings.append({
                                "object": parts[0],
                                "severity": parts[1],
                                "message": parts[2],
                            })
            break

    result["review_findings"] = review_findings
    result["review_pass"] = review_pass
    result["phase"] = "testing" if review_pass else "coding"
    return result


async def tester_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Run tests against the implemented objects."""
    created = state.get("created_objects", [])
    extra = f"Objects to test: {created}\nPlan:\n{state.get('plan', 'N/A')}"
    result = await _run_agent_llm_loop(
        role="tester", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra, max_rounds=5,
    )
    # Parse test results
    tests_pass = True
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            content_lower = msg.content.lower()
            if any(kw in content_lower for kw in ("failed", "failure", "error")):
                tests_pass = False
            break
    result["tests_pass"] = tests_pass
    result["phase"] = "activating" if tests_pass else "reviewing"
    return result


async def activator_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Activate objects and finalise the transport."""
    created = state.get("created_objects", [])
    meta = state.get("metadata", {})
    extra = (
        f"Objects to activate: {created}\n"
        f"Transport: {meta.get('transport', 'auto')}\n"
        f"Package: {meta.get('package', 'unknown')}"
    )
    result = await _run_agent_llm_loop(
        role="activator", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra, max_rounds=5,
    )
    result["phase"] = "completed"
    return result


async def analyzer_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Perform deep code analysis, performance profiling, or dump investigation."""
    created = state.get("created_objects", [])
    artifacts = state.get("artifacts", {})
    extra = (
        f"Objects to analyse: {created or list(artifacts.keys())}\n"
        f"User request:\n{state.get('user_request', '')}\n"
        f"Plan:\n{state.get('plan', 'N/A')}"
    )
    result = await _run_agent_llm_loop(
        role="analyzer", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra, max_rounds=10,
    )
    # Extract analysis summary from the last AI message
    analysis_summary = None
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            analysis_summary = msg.content
            break
    result["analysis_summary"] = analysis_summary
    result["phase"] = "reviewing"
    return result


async def documenter_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Generate technical documentation for ABAP objects."""
    created = state.get("created_objects", [])
    artifacts = state.get("artifacts", {})
    analysis = state.get("analysis_summary", "")
    extra = (
        f"Objects to document: {created or list(artifacts.keys())}\n"
        f"User request:\n{state.get('user_request', '')}\n"
        f"Plan:\n{state.get('plan', 'N/A')}\n"
        f"Analysis summary:\n{analysis or 'N/A'}"
    )
    result = await _run_agent_llm_loop(
        role="documenter", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra, max_rounds=8,
    )
    # Extract documentation from the last AI message
    documentation = None
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            documentation = msg.content
            break
    result["documentation"] = documentation
    result["phase"] = "completed"
    return result


async def migrator_node(state: WorkflowState, mcp_conn: MCPConnection, system_id: str) -> dict:
    """Handle object migration between packages and transport management."""
    meta = state.get("metadata", {})
    extra = (
        f"User request:\n{state.get('user_request', '')}\n"
        f"Plan:\n{state.get('plan', 'N/A')}\n"
        f"Source package: {meta.get('source_package', 'unknown')}\n"
        f"Target package: {meta.get('target_package', 'unknown')}\n"
        f"Transport: {meta.get('transport', 'auto')}"
    )
    result = await _run_agent_llm_loop(
        role="migrator", state=state, mcp_conn=mcp_conn,
        system_id=system_id, extra_context=extra, max_rounds=8,
    )
    # Extract migration log from the last AI message
    migration_log: list[dict[str, Any]] = []
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            # Simple extraction: each line starting with "- " is a migration action
            for line in msg.content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("- ") or stripped.startswith("* "):
                    migration_log.append({
                        "action": stripped[2:],
                        "timestamp": time.time(),
                    })
            break
    result["migration_log"] = migration_log
    result["phase"] = "reviewing"
    return result


# Map role names to node functions for easy lookup
AGENT_NODES = {
    "planner": planner_node,
    "clarifier": clarifier_node,
    "coder": coder_node,
    "reviewer": reviewer_node,
    "tester": tester_node,
    "activator": activator_node,
    "analyzer": analyzer_node,
    "documenter": documenter_node,
    "migrator": migrator_node,
}
