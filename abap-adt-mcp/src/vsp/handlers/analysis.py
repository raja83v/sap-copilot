"""Analysis tool handlers — CallGraph, ObjectStructure, CallerOf, CalleesOf."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_analysis_tools(server: VspServer) -> None:
    """Register code analysis MCP tools."""

    @server.mcp.tool(
        name="GetCallGraph",
        description="Get the call graph for an ABAP object showing which objects it calls and is called by.",
    )
    async def get_call_graph(
        name: str,
        object_type: str = "",
        depth: int = 3,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                "/sap/bc/adt/repository/informationsystem/callgraph",
                params={
                    "uri": f"/sap/bc/adt/{object_type.lower()}/{name.lower()}" if object_type else name,
                    "depth": str(depth),
                },
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetObjectStructure",
        description="Get internal structure of an ABAP object (includes, sections, components).",
    )
    async def get_object_structure(
        name: str,
        object_type: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/{object_type.lower()}/{name.lower()}/objectstructure"
                if object_type
                else f"/sap/bc/adt/programs/programs/{name.lower()}/objectstructure"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetCallersOf",
        description="Find all callers (where-used) of an ABAP object or method.",
    )
    async def get_callers_of(
        name: str,
        object_type: str = "",
        method: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            params: dict = {}
            if object_type:
                params["uri"] = f"/sap/bc/adt/{object_type.lower()}/{name.lower()}"
            else:
                params["uri"] = name
            if method:
                params["method"] = method
            resp = await server.transport.get(
                "/sap/bc/adt/repository/informationsystem/usedbylist",
                params=params,
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetCalleesOf",
        description="Find all objects called by an ABAP object or method.",
    )
    async def get_callees_of(
        name: str,
        object_type: str = "",
        method: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            params: dict = {}
            if object_type:
                params["uri"] = f"/sap/bc/adt/{object_type.lower()}/{name.lower()}"
            else:
                params["uri"] = name
            if method:
                params["method"] = method
            resp = await server.transport.get(
                "/sap/bc/adt/repository/informationsystem/useslist",
                params=params,
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AnalyzeCallGraph",
        description="Deep call graph analysis: fan-in, fan-out, cyclic dependencies, statistics.",
    )
    async def analyze_call_graph(
        name: str,
        object_type: str = "",
        depth: int = 5,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            # Get both directions
            uri = f"/sap/bc/adt/{object_type.lower()}/{name.lower()}" if object_type else name
            callers_resp = await server.transport.get(
                "/sap/bc/adt/repository/informationsystem/usedbylist",
                params={"uri": uri},
            )
            callees_resp = await server.transport.get(
                "/sap/bc/adt/repository/informationsystem/useslist",
                params={"uri": uri},
            )
            lines = [
                f"Call Graph Analysis for {name}:",
                f"\n--- Callers (used by) ---",
                callers_resp.text[:2000],
                f"\n--- Callees (uses) ---",
                callees_resp.text[:2000],
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetObjectExplorer",
        description="Browse an object's structure tree (similar to SE80 object list).",
    )
    async def get_object_explorer(
        name: str,
        object_type: str = "",
        node_path: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            path = f"/sap/bc/adt/{object_type.lower()}/{name.lower()}" if object_type else name
            if node_path:
                path += f"/{node_path}"
            resp = await server.transport.get(path)
            return resp.text
        except Exception as e:
            return f"Error: {e}"
