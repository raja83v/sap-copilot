"""Search tool handlers — SearchObject, GrepObjects, GrepPackages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_search_tools(server: VspServer) -> None:
    """Register search-related MCP tools."""

    @server.mcp.tool(
        name="SearchObject",
        description="Search for ABAP objects by name pattern. Supports wildcards (*). "
        "Filter by type: PROG, CLAS, INTF, FUNC, FUGR, TABL, DTEL, DOMA, VIEW, DDLS, "
        "SRVB, BDEF, TRAN, MSAG, etc.",
    )
    async def search_object(
        query: str,
        object_type: str = "",
        max_results: int = 50,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            results = await server.client.search_object(
                query, type_filter=object_type, max_results=max_results
            )
            if not results:
                return f"No objects found matching '{query}'"
            lines = [f"Found {len(results)} objects:"]
            for r in results:
                lines.append(f"  [{r.type}] {r.name} - {r.description}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GrepObject",
        description="Search inside the source code of an ABAP object for a pattern. "
        "Returns matching lines with line numbers. Supports regex.",
    )
    async def grep_object(
        name: str,
        pattern: str,
        object_type: str = "",
        regex: bool = False,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.workflows.grep_objects(
                [name], pattern, object_type=object_type, regex=regex
            )
            if not result.matches:
                return f"No matches for '{pattern}' in {name}"
            lines = [f"Found {len(result.matches)} matches:"]
            for m in result.matches:
                lines.append(f"  {m.object_name}:{m.line_number}: {m.line_content.strip()}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GrepPackage",
        description="Search source code of all objects in a package for a pattern. "
        "Returns matching lines with object names and line numbers.",
    )
    async def grep_package(
        package: str,
        pattern: str,
        regex: bool = False,
        recursive: bool = True,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.workflows.grep_package(
                package, pattern, regex=regex, recursive=recursive
            )
            if not result.matches:
                return f"No matches for '{pattern}' in package {package}"
            lines = [f"Found {len(result.matches)} matches across {result.files_searched} files:"]
            for m in result.matches:
                lines.append(f"  {m.object_name}:{m.line_number}: {m.line_content.strip()}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"
