"""Debug tool handlers — Breakpoints, Debug sessions, ABAP Debugger."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_DEBUG

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_debug_tools(server: VspServer) -> None:
    """Register debugging MCP tools."""

    @server.mcp.tool(
        name="SetBreakpoint",
        description="Set an ABAP external breakpoint. Specify object name and line number. "
        "The breakpoint will trigger when any session hits that point.",
    )
    async def set_breakpoint(
        name: str,
        line: int,
        object_type: str = "",
    ) -> str:
        try:
            server.check_safety(OP_DEBUG)
            bp = await server.debugger.set_breakpoint(name, line, object_type=object_type)
            return f"Breakpoint set: {bp}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetBreakpoints",
        description="List all active external breakpoints.",
    )
    async def get_breakpoints() -> str:
        try:
            server.check_safety(OP_DEBUG)
            bps = await server.debugger.get_breakpoints()
            if not bps:
                return "No active breakpoints."
            lines = [f"Active breakpoints ({len(bps)}):"]
            for bp in bps:
                lines.append(f"  {bp.object_name}:{bp.line} (ID: {bp.id})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DeleteBreakpoint",
        description="Delete a specific breakpoint by ID.",
    )
    async def delete_breakpoint(breakpoint_id: str) -> str:
        try:
            server.check_safety(OP_DEBUG)
            await server.debugger.delete_breakpoint(breakpoint_id)
            return f"Breakpoint {breakpoint_id} deleted."
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DeleteAllBreakpoints",
        description="Delete all active external breakpoints.",
    )
    async def delete_all_breakpoints() -> str:
        try:
            server.check_safety(OP_DEBUG)
            await server.debugger.delete_all_breakpoints()
            return "All breakpoints deleted."
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DebuggerListen",
        description="Listen for a debug session to start (breakpoint hit). "
        "Blocks until a session is caught or timeout.",
    )
    async def debugger_listen(timeout: int = 60) -> str:
        try:
            server.check_safety(OP_DEBUG)
            session = await server.debugger.listen(timeout=timeout)
            if session is None:
                return "No debug session caught within timeout."
            return f"Debug session caught: {session}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DebuggerStep",
        description="Execute a debugger step (into, over, out, continue).",
    )
    async def debugger_step(
        action: str = "over",
    ) -> str:
        try:
            server.check_safety(OP_DEBUG)
            result = await server.debugger.step(action)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DebuggerGetStack",
        description="Get the current call stack in the debug session.",
    )
    async def debugger_get_stack() -> str:
        try:
            server.check_safety(OP_DEBUG)
            frames = await server.debugger.get_stack()
            if not frames:
                return "No active debug session or empty stack."
            lines = ["Call Stack:"]
            for i, f in enumerate(frames):
                lines.append(f"  #{i}: {f.object_name}:{f.line} ({f.event})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DebuggerGetVariables",
        description="Get variable values in the current debug session. "
        "Optionally specify scope (local, global, etc.).",
    )
    async def debugger_get_variables(scope: str = "local") -> str:
        try:
            server.check_safety(OP_DEBUG)
            variables = await server.debugger.get_variables(scope)
            if not variables:
                return f"No variables in scope '{scope}'."
            lines = [f"Variables ({scope}):"]
            for v in variables:
                lines.append(f"  {v.name} ({v.type}) = {v.value}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DebuggerSetVariable",
        description="Modify a variable value in the current debug session.",
    )
    async def debugger_set_variable(
        name: str,
        value: str,
    ) -> str:
        try:
            server.check_safety(OP_DEBUG)
            result = await server.debugger.set_variable(name, value)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DebuggerGetSource",
        description="Get source code around the current execution point in the debugger.",
    )
    async def debugger_get_source() -> str:
        try:
            server.check_safety(OP_DEBUG)
            result = await server.debugger.get_current_source()
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DebuggerDetach",
        description="Detach from the current debug session (continue execution).",
    )
    async def debugger_detach() -> str:
        try:
            server.check_safety(OP_DEBUG)
            await server.debugger.detach()
            return "Detached from debug session."
        except Exception as e:
            return f"Error: {e}"
