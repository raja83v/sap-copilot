"""Diagnostics tool handlers — Dumps, Traces, SQL Traces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ, OP_WRITE

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_diagnostics_tools(server: VspServer) -> None:
    """Register diagnostics MCP tools."""

    @server.mcp.tool(
        name="ListDumps",
        description="List recent runtime dumps (ST22). Optionally filter by date range or user.",
    )
    async def list_dumps(
        from_date: str = "",
        to_date: str = "",
        user: str = "",
        max_results: int = 50,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            params: dict = {"maxResults": str(max_results)}
            if from_date:
                params["fromDate"] = from_date
            if to_date:
                params["toDate"] = to_date
            if user:
                params["user"] = user
            resp = await server.transport.get(
                "/sap/bc/adt/runtime/dumps", params=params
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetDump",
        description="Get details of a specific runtime dump by ID.",
    )
    async def get_dump(dump_id: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/runtime/dumps/{dump_id}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="ListTraces",
        description="List ABAP traces. Returns recent trace entries.",
    )
    async def list_traces(max_results: int = 50) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                "/sap/bc/adt/traces",
                params={"maxResults": str(max_results)},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetTrace",
        description="Get details of a specific ABAP trace.",
    )
    async def get_trace(trace_id: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/traces/{trace_id}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetTraceAnalysis",
        description="Analyze an ABAP trace: hot spots, call tree, DB access stats.",
    )
    async def get_trace_analysis(trace_id: str, analysis_type: str = "hitlist") -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/traces/{trace_id}/{analysis_type}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetSQLTraceState",
        description="Get the current SQL trace (ST05) on/off state.",
    )
    async def get_sql_trace_state() -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                "/sap/bc/adt/traces/sqltrace/state"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="SetSQLTraceState",
        description="Toggle SQL trace (ST05) on or off.",
    )
    async def set_sql_trace_state(enabled: bool) -> str:
        try:
            server.check_safety(OP_WRITE)
            state = "on" if enabled else "off"
            resp = await server.transport.post(
                "/sap/bc/adt/traces/sqltrace/state",
                content=state,
            )
            return f"SQL trace set to {state}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="ListSQLTraces",
        description="List captured SQL trace entries.",
    )
    async def list_sql_traces(max_results: int = 100) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                "/sap/bc/adt/traces/sqltrace/entries",
                params={"maxResults": str(max_results)},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"
