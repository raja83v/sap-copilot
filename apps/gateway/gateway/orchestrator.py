"""Chat Orchestrator — AI chat loop with MCP tool calling via LiteLLM proxy.

Sends user messages to the LiteLLM proxy (OpenAI-compatible), processes tool
calls by forwarding them to the appropriate MCP connection, and streams
responses back via SSE events.

For multi-step development tasks (create report, refactor class, etc.) the
chat route automatically classifies intent and delegates to the LangGraph
workflow engine. Simple chat queries go through the direct LLM loop below.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from .mcp_manager import MCPConnection, MCPError, mcp_manager
from .routes.llm import get_litellm_base_url, get_litellm_api_key
from .config import settings

logger = logging.getLogger("gateway.orchestrator")

# Maximum tool call rounds to prevent infinite loops
MAX_TOOL_ROUNDS = 15

SYSTEM_PROMPT = """\
You are SAP Copilot, an expert SAP ABAP development assistant. You have access to a live SAP system \
through MCP tools that allow you to read source code, search objects, create and edit programs, \
run tests, manage transports, debug code, and much more.

Guidelines:
- Use tools to answer questions about the SAP system rather than guessing.
- When modifying code, always read the current source first.
- After creating or editing objects, activate them.
- Be concise but thorough in explanations.
- When showing ABAP code, use proper formatting.
- If a tool call fails, explain the error and suggest alternatives.
- For destructive operations, confirm with the user first.
- Do NOT call multiple tools for the same purpose in a single turn. Pick the single best tool.
- For reading table data, always prefer GetTableContents over RunQuery. Only use RunQuery for complex \
queries that involve JOINs, aggregations, sub-queries, or expressions that GetTableContents cannot handle.
- RunQuery uses ABAP SQL syntax: columns must be comma-separated, use 'UP TO N ROWS' (not 'TOP N'), \
and string literals use single quotes.
"""


def _get_openai_client() -> AsyncOpenAI:
    """Build an AsyncOpenAI client pointing at the LiteLLM proxy."""
    base_url = get_litellm_base_url()
    api_key = get_litellm_api_key() or "not-needed"
    return AsyncOpenAI(base_url=f"{base_url}/v1", api_key=api_key)


@dataclass
class ChatEvent:
    """A single SSE event in the chat stream."""

    type: str  # "content", "tool_start", "tool_end", "error", "done"
    data: dict[str, Any]

    def to_sse(self) -> str:
        return f"event: {self.type}\ndata: {json.dumps(self.data)}\n\n"


_CONNECTION_ERROR_HINTS = ("getaddrinfo", "connect", "timed out", "connection reset",
                           "connection refused", "broken pipe", "eof", "closed")


def _is_connection_error(error: Exception) -> bool:
    """Detect errors that suggest the MCP/SAP connection is stale."""
    msg = str(error).lower()
    return any(hint in msg for hint in _CONNECTION_ERROR_HINTS)


async def chat_stream(
    messages: list[dict[str, Any]],
    model: str,
    mcp_conn: MCPConnection,
    system_id: str,
    tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[ChatEvent]:
    """Run the AI chat loop, streaming events back.

    1. Send messages to LiteLLM proxy (OpenAI-compatible)
    2. If the model wants to call tools, execute them via MCP
    3. Feed results back and continue
    4. Yield SSE events throughout
    """
    client = _get_openai_client()

    # Use default model if none specified
    effective_model = model or settings.litellm_default_model

    # Build tool definitions from MCP tool list
    if tools is None:
        raw_tools = await mcp_conn.list_tools()
        tools = _convert_mcp_tools_to_openai(raw_tools)

    # Prepend system prompt
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    rounds = 0
    while rounds < MAX_TOOL_ROUNDS:
        rounds += 1

        try:
            response = await client.chat.completions.create(
                model=effective_model,
                messages=full_messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                stream=True,
            )
        except Exception as e:
            yield ChatEvent("error", {"message": f"LLM error: {e}"})
            return

        # Accumulate the streamed response
        content_chunks: list[str] = []
        tool_calls_acc: dict[int, dict[str, Any]] = {}

        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Stream content tokens
            if delta.content:
                content_chunks.append(delta.content)
                yield ChatEvent("content", {"text": delta.content})

            # Accumulate tool calls
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc.id or f"call_{idx}",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["function"]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments

        # Build the assistant message
        assistant_content = "".join(content_chunks) or None
        assistant_msg: dict[str, Any] = {"role": "assistant"}
        if assistant_content:
            assistant_msg["content"] = assistant_content

        # If no tool calls, we're done
        if not tool_calls_acc:
            yield ChatEvent("done", {"content": assistant_content or ""})
            return

        # Process tool calls
        sorted_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc.keys())]
        assistant_msg["tool_calls"] = sorted_calls
        full_messages.append(assistant_msg)

        for tc in sorted_calls:
            name = tc["function"]["name"]
            try:
                arguments = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                arguments = {}

            call_id = tc["id"]
            yield ChatEvent("tool_start", {
                "id": call_id,
                "name": name,
                "parameters": arguments,
            })

            # Execute via MCP (with auto-reconnect on connection errors)
            start_time = time.monotonic()
            result = None
            error_text = None
            try:
                result = await mcp_conn.call_tool(name, arguments)
            except (MCPError, Exception) as first_err:
                if _is_connection_error(first_err) and mcp_manager.has_params(system_id):
                    logger.warning(
                        "Tool %s failed with connection error for system %s: %s — attempting reconnect",
                        name, system_id, first_err,
                    )
                    try:
                        new_conn = await mcp_manager.reconnect(system_id)
                        if new_conn:
                            mcp_conn = new_conn
                            result = await mcp_conn.call_tool(name, arguments)
                        else:
                            error_text = str(first_err)
                    except Exception as retry_err:
                        logger.error("Reconnect+retry failed for system %s tool %s: %s", system_id, name, retry_err)
                        error_text = str(retry_err)
                else:
                    logger.error("Tool %s error for system %s: %s", name, system_id, first_err)
                    error_text = str(first_err)

            duration_ms = int((time.monotonic() - start_time) * 1000)

            if error_text:
                yield ChatEvent("tool_end", {
                    "id": call_id,
                    "name": name,
                    "status": "error",
                    "result": error_text,
                    "duration": duration_ms,
                })
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": f"Error: {error_text}",
                })
            else:
                result_text = _extract_result_text(result)
                yield ChatEvent("tool_end", {
                    "id": call_id,
                    "name": name,
                    "status": "success",
                    "result": result_text,
                    "duration": duration_ms,
                })
                full_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result_text,
                })

        # Continue the loop — model will process tool results

    yield ChatEvent("error", {"message": "Maximum tool call rounds exceeded"})


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
        # MCP result format: {"content": [{"type": "text", "text": "..."}]}
        content = result.get("content", [])
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
            if texts:
                return "\n".join(texts)
        # Fallback: return JSON
        return json.dumps(result, indent=2)
    return str(result)
