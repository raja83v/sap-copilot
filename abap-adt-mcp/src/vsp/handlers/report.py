"""Report tool handlers â€” RunReport, RunReportAsync, GetVariants, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_report_tools(server: VspServer) -> None:
    """Register report execution MCP tools."""

    @server.mcp.tool(
        name="RunReport",
        description="Execute an ABAP report (program) with optional parameters. "
        "Requires ZADT_VSP WebSocket extension. Use RunReportAsync for non-blocking execution. "
        "Note: synchronous report execution via standard ADT REST is not supported — "
        "this tool routes through the WebSocket channel when available.",
    )
    async def run_report(
        name: str,
        variant: str = "",
        parameters: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            import json
            # Standard SAP ADT has no synchronous report-run REST endpoint.
            # Route through WebSocket (ZADT_VSP) when available; otherwise
            # return a clear explanation so the LLM can advise the user correctly.
            if not server.ws_client:
                return (
                    "Error: RunReport requires the ZADT_VSP WebSocket extension which is "
                    "not connected on this system. "
                    "Standard SAP ADT REST API does not provide a synchronous report "
                    "execution endpoint. "
                    "Options: (1) Install ZADT_VSP and use InstallZADTVSP, "
                    "(2) Use RunReportAsync once ZADT_VSP is available, "
                    "(3) Execute the report directly in SAP and read its spool via GetReportOutput."
                )
            params: dict = {"program": name.upper()}
            if variant:
                params["variant"] = variant
            if parameters:
                try:
                    params["parameters"] = json.loads(parameters)
                except json.JSONDecodeError:
                    pass
            result = await server.ws_client.send("report", "run", params)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="RunReportAsync",
        description="Execute an ABAP report asynchronously via WebSocket. "
        "Returns a job ID that can be polled with GetAsyncResult.",
    )
    async def run_report_async(
        name: str,
        variant: str = "",
        parameters: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            if not server.ws_client:
                return "Error: WebSocket client not available. ZADT_VSP required for async execution."
            import json
            params: dict = {"program": name.upper()}
            if variant:
                params["variant"] = variant
            if parameters:
                try:
                    params["parameters"] = json.loads(parameters)
                except json.JSONDecodeError:
                    pass
            result = await server.ws_client.send("report", "run", params)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetAsyncResult",
        description="Get result of a previously started async operation by job ID.",
    )
    async def get_async_result(job_id: str) -> str:
        try:
            server.check_safety(OP_READ)
            if not server.ws_client:
                return "Error: WebSocket client not available."
            import json
            result = await server.ws_client.send("report", "getResult", {"jobId": job_id})
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetVariants",
        description="Get list of report variants for a program.",
    )
    async def get_variants(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/programs/programs/{name.upper()}/variants"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetReportOutput",
        description="Get the output (spool) of a previously executed report.",
    )
    async def get_report_output(spool_id: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/runtime/spooloutput/{spool_id}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="RFCCall",
        description="Call an RFC Function Module with parameters via WebSocket (requires ZADT_VSP).",
    )
    async def rfc_call(
        function_module: str,
        parameters: str = "{}",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            if not server.ws_client:
                return "Error: WebSocket client not available. ZADT_VSP required for RFC calls."
            import json
            try:
                params = json.loads(parameters)
            except json.JSONDecodeError:
                return "Error: parameters must be valid JSON"
            result = await server.ws_client.send(
                "rfc", "call",
                {"functionModule": function_module.upper(), "parameters": params},
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error: {e}"
