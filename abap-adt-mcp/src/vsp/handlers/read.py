"""Read tool handlers — GetSource, GetProgram, GetClass, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_read_tools(server: VspServer) -> None:
    """Register read-related MCP tools."""

    @server.mcp.tool(
        name="GetSource",
        description="Get source code of any ABAP object (PROG, CLAS, INTF, FUNC, INCL, DDLS, TABL, etc.). "
        "Supports method-level access for classes. Use object_type to specify the type.",
    )
    async def get_source(
        name: str,
        object_type: str = "",
        method: str = "",
        group: str = "",
    ) -> str:
        try:
            server.check_safety(OP_READ)
            source = await server.client.get_source(object_type, name, method=method, group=group)
            return source
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetClassInclude",
        description="Get a class include: testclasses, locals_def, locals_imp, or macros.",
    )
    async def get_class_include(name: str, include_type: str) -> str:
        try:
            server.check_safety(OP_READ)
            return await server.client.get_class_include(name, include_type)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetClassInfo",
        description="Get class structure including method list with line boundaries.",
    )
    async def get_class_info(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            return await server.codeintel.get_class_info(name)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetPackage",
        description="Get contents of an ABAP package (sub-packages and objects).",
    )
    async def get_package(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            pkg = await server.client.get_package(name)
            lines = [f"Package: {pkg.name}"]
            if pkg.sub_packages:
                lines.append(f"\nSub-packages ({len(pkg.sub_packages)}):")
                for sp in pkg.sub_packages:
                    lines.append(f"  {sp}")
            lines.append(f"\nObjects ({len(pkg.objects)}):")
            for obj in pkg.objects:
                lines.append(f"  [{obj.type}] {obj.name} - {obj.description}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetTable",
        description="Get table definition source code.",
    )
    async def get_table(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            return await server.client.get_table_source(name)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetTableContents",
        description="Preview table data (SELECT from database table). Returns rows in tabular format. "
        "This is the PREFERRED tool for reading table data — use it instead of RunQuery when you just need "
        "to see rows from a single table. Supports filtering via the 'where' parameter.",
    )
    async def get_table_contents(table: str, max_rows: int = 100, where: str = "") -> str:
        try:
            server.check_safety(OP_READ)
            result = await server.client.get_table_contents(table, max_rows=max_rows, where=where)
            if not result.rows:
                return f"No data found in table {table}"
            # Format as table
            lines = []
            if result.columns:
                header = " | ".join(c.name for c in result.columns)
                lines.append(header)
                lines.append("-" * len(header))
            for row in result.rows:
                lines.append(" | ".join(str(v) for v in row.values()))
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="RunQuery",
        description="Execute a free SQL query against the SAP database using ABAP SQL syntax. Returns results in tabular format. "
        "IMPORTANT: Use ABAP SQL syntax — columns must be comma-separated (e.g. 'SELECT col1, col2, col3 FROM table'), "
        "use 'UP TO N ROWS' instead of 'TOP N' for row limits, and use single quotes for string literals. "
        "Only use this tool for complex queries (JOINs, aggregations, etc.). For simple table reads, prefer GetTableContents.",
    )
    async def run_query(sql: str) -> str:
        try:
            server.check_safety(OP_READ)
            from vsp.config import OP_FREE_SQL
            server.check_safety(OP_FREE_SQL)
            result = await server.client.run_query(sql)
            if not result.rows:
                return "No results"
            lines = []
            if result.columns:
                header = " | ".join(c.name for c in result.columns)
                lines.append(header)
                lines.append("-" * len(header))
            for row in result.rows:
                lines.append(" | ".join(str(v) for v in row.values()))
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetFunctionGroup",
        description="Get function group metadata and list of function modules.",
    )
    async def get_function_group(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            fg = await server.client.get_function_group(name)
            lines = [f"Function Group: {fg.name} - {fg.description}"]
            lines.append(f"\nFunction Modules ({len(fg.modules)}):")
            for fm in fg.modules:
                lines.append(f"  {fm.name} - {fm.description}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetMessages",
        description="Get message class texts (all messages in a message class).",
    )
    async def get_messages(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            mc = await server.client.get_message_class(name)
            lines = [f"Message Class: {mc.name} - {mc.description}"]
            for msg in mc.messages:
                lines.append(f"  {msg.number}: {msg.text}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetCDSDependencies",
        description="Get CDS view dependency tree.",
    )
    async def get_cds_dependencies(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            return await server.client.get_cds_dependencies(name)
        except Exception as e:
            return f"Error: {e}"

    # Expert-only read tools
    if server._is_expert():
        @server.mcp.tool(
            name="GetProgram",
            description="[Expert] Get program source code directly.",
        )
        async def get_program(name: str) -> str:
            try:
                server.check_safety(OP_READ)
                return await server.client.get_program_source(name)
            except Exception as e:
                return f"Error: {e}"

        @server.mcp.tool(
            name="GetClass",
            description="[Expert] Get class main source code directly.",
        )
        async def get_class(name: str) -> str:
            try:
                server.check_safety(OP_READ)
                return await server.client.get_class_source(name)
            except Exception as e:
                return f"Error: {e}"

        @server.mcp.tool(
            name="GetInterface",
            description="[Expert] Get interface source code directly.",
        )
        async def get_interface(name: str) -> str:
            try:
                server.check_safety(OP_READ)
                return await server.client.get_interface_source(name)
            except Exception as e:
                return f"Error: {e}"

        @server.mcp.tool(
            name="GetFunction",
            description="[Expert] Get function module source code.",
        )
        async def get_function(group: str, name: str) -> str:
            try:
                server.check_safety(OP_READ)
                return await server.client.get_function_source(group, name)
            except Exception as e:
                return f"Error: {e}"

        @server.mcp.tool(
            name="GetInclude",
            description="[Expert] Get include program source code.",
        )
        async def get_include(name: str) -> str:
            try:
                server.check_safety(OP_READ)
                return await server.client.get_include_source(name)
            except Exception as e:
                return f"Error: {e}"

        @server.mcp.tool(
            name="GetStructure",
            description="[Expert] Get DDIC structure source.",
        )
        async def get_structure(name: str) -> str:
            try:
                server.check_safety(OP_READ)
                return await server.client.get_structure_source(name)
            except Exception as e:
                return f"Error: {e}"

        @server.mcp.tool(
            name="GetTransaction",
            description="[Expert] Get transaction code information.",
        )
        async def get_transaction(tcode: str) -> str:
            try:
                server.check_safety(OP_READ)
                tx = await server.client.get_transaction(tcode)
                return f"Transaction: {tx.name}\nDescription: {tx.description}\nProgram: {tx.program}"
            except Exception as e:
                return f"Error: {e}"

        @server.mcp.tool(
            name="GetTypeInfo",
            description="[Expert] Get type information for a data element.",
        )
        async def get_type_info(name: str) -> str:
            try:
                server.check_safety(OP_READ)
                ti = await server.client.get_type_info(name)
                return f"Type: {ti.name}\nABAP Type: {ti.type}\nLength: {ti.length}\nDecimals: {ti.decimals}\nDescription: {ti.description}"
            except Exception as e:
                return f"Error: {e}"
