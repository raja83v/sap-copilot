"""AMDP (ABAP Managed Database Procedures) tool handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_DEBUG

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_amdp_tools(server: VspServer) -> None:
    """Register AMDP debugging MCP tools."""

    @server.mcp.tool(
        name="AMDPGetProcedures",
        description="List AMDP procedures in a class.",
    )
    async def amdp_get_procedures(class_name: str) -> str:
        try:
            from vsp.config import OP_READ
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/oo/classes/{class_name.upper()}/amdp/procedures"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AMDPGetSource",
        description="Get SQL Script source of an AMDP implementation.",
    )
    async def amdp_get_source(class_name: str, method_name: str) -> str:
        try:
            from vsp.config import OP_READ
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/oo/classes/{class_name.upper()}/amdp/procedures/{method_name.upper()}/source"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AMDPDebuggerStart",
        description="Start an AMDP (SQL Script) debug session. Requires HANA and AMDP feature.",
    )
    async def amdp_debugger_start(
        class_name: str,
        method_name: str,
    ) -> str:
        try:
            server.check_safety(OP_DEBUG)
            # Check feature availability
            features = {fs.id: fs.available for fs in await server.feature_prober.get_all_features()}
            if not features.get("amdp", False):
                return "Error: AMDP debugging is not available on this system."
            if not features.get("hana", False):
                return "Error: HANA is required for AMDP debugging."

            resp = await server.transport.post(
                "/sap/bc/adt/amdp/debugger/sessions",
                content=(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<amdp:session xmlns:amdp="http://www.sap.com/adt/amdp">'
                    f'<amdp:class>{class_name.upper()}</amdp:class>'
                    f'<amdp:method>{method_name.upper()}</amdp:method>'
                    '</amdp:session>'
                ),
                headers={"Content-Type": "application/vnd.sap.adt.amdp.debugger.session.v1+xml"},
            )
            return f"AMDP debug session started: {resp.text.strip()}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AMDPDebuggerResume",
        description="Resume execution in an AMDP debug session.",
    )
    async def amdp_debugger_resume(session_id: str) -> str:
        try:
            server.check_safety(OP_DEBUG)
            resp = await server.transport.post(
                f"/sap/bc/adt/amdp/debugger/sessions/{session_id}/resume"
            )
            return f"Session resumed: {resp.text.strip()}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AMDPDebuggerStep",
        description="Step in an AMDP debug session (into, over, out).",
    )
    async def amdp_debugger_step(
        session_id: str,
        action: str = "over",
    ) -> str:
        try:
            server.check_safety(OP_DEBUG)
            resp = await server.transport.post(
                f"/sap/bc/adt/amdp/debugger/sessions/{session_id}/step{action}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AMDPDebuggerGetVariables",
        description="Get variables in current AMDP debug session scope.",
    )
    async def amdp_debugger_get_variables(session_id: str) -> str:
        try:
            server.check_safety(OP_DEBUG)
            resp = await server.transport.get(
                f"/sap/bc/adt/amdp/debugger/sessions/{session_id}/variables"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AMDPDebuggerStop",
        description="Stop/terminate an AMDP debug session.",
    )
    async def amdp_debugger_stop(session_id: str) -> str:
        try:
            server.check_safety(OP_DEBUG)
            resp = await server.transport.delete(
                f"/sap/bc/adt/amdp/debugger/sessions/{session_id}"
            )
            return f"AMDP debug session {session_id} terminated."
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AMDPSetBreakpoint",
        description="Set a breakpoint in AMDP SQL Script code.",
    )
    async def amdp_set_breakpoint(
        session_id: str,
        line: int,
    ) -> str:
        try:
            server.check_safety(OP_DEBUG)
            resp = await server.transport.post(
                f"/sap/bc/adt/amdp/debugger/sessions/{session_id}/breakpoints",
                content=(
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<amdp:breakpoint xmlns:amdp="http://www.sap.com/adt/amdp">'
                    f'<amdp:line>{line}</amdp:line>'
                    '</amdp:breakpoint>'
                ),
                headers={"Content-Type": "application/vnd.sap.adt.amdp.debugger.breakpoint.v1+xml"},
            )
            return f"Breakpoint set at line {line}: {resp.text.strip()}"
        except Exception as e:
            return f"Error: {e}"
