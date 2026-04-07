"""CodeIntel tool handlers — FindDefinition, FindReferences, CodeCompletion, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_codeintel_tools(server: VspServer) -> None:
    """Register code intelligence MCP tools."""

    @server.mcp.tool(
        name="FindDefinition",
        description="Navigate to the definition/declaration of an ABAP symbol. "
        "Provide source URI, line, and column. Returns the location of the definition.",
    )
    async def find_definition(
        uri: str,
        line: int,
        column: int,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.codeintel.find_definition(uri, line, column)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="FindReferences",
        description="Find all references/usages of an ABAP symbol across the system. "
        "Returns list of locations where the symbol is used.",
    )
    async def find_references(
        uri: str,
        line: int,
        column: int,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.codeintel.find_references(uri, line, column)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="CodeCompletion",
        description="Get code completion suggestions at a given position in ABAP source. "
        "Returns list of completion items with types and descriptions.",
    )
    async def code_completion(
        uri: str,
        line: int,
        column: int,
        prefix: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.codeintel.code_completion(uri, line, column, prefix=prefix)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetTypeHierarchy",
        description="Get inheritance/interface hierarchy for a class or interface. "
        "Shows superclasses, subclasses, and implemented interfaces.",
    )
    async def get_type_hierarchy(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.codeintel.get_type_hierarchy(name)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetClassComponents",
        description="Get all components (methods, attributes, events, types) of a class or interface.",
    )
    async def get_class_components(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.codeintel.get_class_components(name)
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetUsageLocations",
        description="Find where-used list for an ABAP object. "
        "Returns all objects that reference the given object.",
    )
    async def get_usage_locations(
        name: str,
        object_type: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/repository/informationsystem/usedbylist",
                params={"uri": f"/sap/bc/adt/{object_type.lower()}/{name.lower()}"},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"
