"""ADT Client — core read operations.

Provides methods for reading ABAP objects, searching, and retrieving metadata
from a SAP system via the ADT REST API.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import quote

from vsp.adt.http import Transport
from vsp.adt.xml_types import (
    FunctionGroup,
    InstalledComponent,
    MessageClass,
    MethodInfo,
    PackageContent,
    SearchResult,
    ServiceBinding,
    SystemInfo,
    TableContentsResult,
    Transaction,
    TypeInfo,
)
from vsp.config import Config

logger = logging.getLogger("vsp.adt.client")

# Object type to source URL path mapping
OBJECT_TYPE_PATHS: dict[str, str] = {
    "PROG": "/sap/bc/adt/programs/programs/{name}/source/main",
    "CLAS": "/sap/bc/adt/oo/classes/{name}/source/main",
    "INTF": "/sap/bc/adt/oo/interfaces/{name}/source/main",
    "FUGR": "/sap/bc/adt/functions/groups/{name}",
    "FUNC": "/sap/bc/adt/functions/groups/{group}/fmodules/{name}/source/main",
    "INCL": "/sap/bc/adt/programs/includes/{name}/source/main",
    "DDLS": "/sap/bc/adt/ddic/ddl/sources/{name}/source/main",
    "TABL": "/sap/bc/adt/ddic/tables/{name}/source/main",
    "VIEW": "/sap/bc/adt/ddic/views/{name}/source/main",
    "STRU": "/sap/bc/adt/ddic/structures/{name}/source/main",
    "DTEL": "/sap/bc/adt/ddic/dataelements/{name}",
    "SRVD": "/sap/bc/adt/ddic/srvd/sources/{name}/source/main",
    "BDEF": "/sap/bc/adt/bo/behaviordefinitions/{name}/source/main",
    "SRVB": "/sap/bc/adt/businessservices/bindings/{name}",
    "MSAG": "/sap/bc/adt/messageclass/{name}",
    "TRAN": "/sap/bc/adt/vit/wb/object_type/TRAN/object_name/{name}",
}

# Class include types
CLASS_INCLUDE_TYPES = {
    "testclasses": "testclasses",
    "locals_def": "locals_def",
    "locals_imp": "locals_imp",
    "macros": "macros",
}


class ADTClient:
    """Client for SAP ABAP Development Tools (ADT) REST API.

    Usage:
        async with ADTClient(config) as client:
            source = await client.get_source("PROG", "ZTEST")
    """

    def __init__(self, config: Config):
        self.config = config
        self.transport = Transport(config)

    async def __aenter__(self) -> ADTClient:
        await self.transport.__aenter__()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.transport.__aexit__(*args)

    # =========================================================================
    # Search
    # =========================================================================

    async def search_object(
        self,
        query: str,
        *,
        type_filter: str = "",
        max_results: int = 50,
    ) -> list[SearchResult]:
        """Search for ABAP objects.

        Args:
            query: Search query (supports * wildcards).
            type_filter: Optional ADT type filter (e.g., "CLAS", "PROG").
            max_results: Maximum results to return.

        Returns:
            List of matching objects.
        """
        params: dict[str, str] = {
            "operation": "quickSearch",
            "query": query,
            "maxResults": str(max_results),
        }
        if type_filter:
            params["objectType"] = type_filter

        resp = await self.transport.get(
            "/sap/bc/adt/repository/informationsystem/search",
            params=params,
        )
        return SearchResult.parse_list(resp.text)

    # =========================================================================
    # Source code getters
    # =========================================================================

    async def get_program_source(self, name: str) -> str:
        """Get source code of a program (report)."""
        path = f"/sap/bc/adt/programs/programs/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_class_source(self, name: str) -> str:
        """Get source code of a class (main include)."""
        path = f"/sap/bc/adt/oo/classes/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_interface_source(self, name: str) -> str:
        """Get source code of an interface."""
        path = f"/sap/bc/adt/oo/interfaces/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_function_source(self, group: str, name: str) -> str:
        """Get source code of a function module."""
        path = f"/sap/bc/adt/functions/groups/{quote(group.upper())}/fmodules/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_include_source(self, name: str) -> str:
        """Get source code of an include program."""
        path = f"/sap/bc/adt/programs/includes/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_cds_source(self, name: str) -> str:
        """Get CDS DDL source."""
        path = f"/sap/bc/adt/ddic/ddl/sources/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_table_source(self, name: str) -> str:
        """Get table definition source."""
        path = f"/sap/bc/adt/ddic/tables/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_structure_source(self, name: str) -> str:
        """Get structure definition source."""
        path = f"/sap/bc/adt/ddic/structures/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_data_element(self, name: str) -> str:
        """Get data element metadata XML."""
        path = f"/sap/bc/adt/ddic/dataelements/{quote(name.upper())}"
        resp = await self.transport.get(path)
        return resp.text

    async def get_service_def_source(self, name: str) -> str:
        """Get service definition source."""
        path = f"/sap/bc/adt/ddic/srvd/sources/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_bdef_source(self, name: str) -> str:
        """Get behavior definition source."""
        path = f"/sap/bc/adt/bo/behaviordefinitions/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_view_source(self, name: str) -> str:
        """Get DDIC view source."""
        path = f"/sap/bc/adt/ddic/views/{quote(name.upper())}/source/main"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    # =========================================================================
    # Unified source getter
    # =========================================================================

    async def get_source(
        self,
        object_type: str,
        name: str,
        *,
        method: str = "",
        group: str = "",
    ) -> str:
        """Get source code for any supported object type.

        Args:
            object_type: ABAP object type (PROG, CLAS, INTF, FUNC, etc.)
            name: Object name.
            method: Optional method name for class method-level access.
            group: Function group name (required for FUNC type).

        Returns:
            Source code as text.
        """
        obj_type = object_type.upper()

        # Method-level access for classes
        if method and obj_type == "CLAS":
            return await self.get_method_source(name, method)

        # Type-specific handling
        if obj_type == "PROG":
            return await self.get_program_source(name)
        elif obj_type == "CLAS":
            return await self.get_class_source(name)
        elif obj_type == "INTF":
            return await self.get_interface_source(name)
        elif obj_type == "FUNC":
            return await self.get_function_source(group, name)
        elif obj_type == "INCL":
            return await self.get_include_source(name)
        elif obj_type == "DDLS":
            return await self.get_cds_source(name)
        elif obj_type == "TABL":
            return await self.get_table_source(name)
        elif obj_type == "VIEW":
            return await self.get_view_source(name)
        elif obj_type in ("STRU", "STRUCTURE"):
            return await self.get_structure_source(name)
        elif obj_type == "DTEL":
            return await self.get_data_element(name)
        elif obj_type == "SRVD":
            return await self.get_service_def_source(name)
        elif obj_type == "BDEF":
            return await self.get_bdef_source(name)
        else:
            # Try to guess the path
            raise ValueError(f"Unsupported object type: {object_type}")

    # =========================================================================
    # Class includes and method-level access
    # =========================================================================

    async def get_class_include(self, name: str, include_type: str) -> str:
        """Get a class include (testclasses, locals_def, locals_imp, macros).

        Args:
            name: Class name.
            include_type: One of: testclasses, locals_def, locals_imp, macros.

        Returns:
            Include source code.
        """
        if include_type not in CLASS_INCLUDE_TYPES:
            raise ValueError(f"Invalid include type: {include_type}. Must be one of: {list(CLASS_INCLUDE_TYPES.keys())}")

        path = f"/sap/bc/adt/oo/classes/{quote(name.upper())}/includes/{include_type}"
        resp = await self.transport.get(path, accept="text/plain")
        return resp.text

    async def get_class_methods(self, name: str) -> list[MethodInfo]:
        """Get method boundaries for a class.

        Args:
            name: Class name.

        Returns:
            List of MethodInfo with line boundaries.
        """
        path = f"/sap/bc/adt/oo/classes/{quote(name.upper())}/objectstructure"
        resp = await self.transport.get(path)
        return MethodInfo.parse_object_structure(resp.text)

    async def get_method_source(self, class_name: str, method_name: str) -> str:
        """Get source code for a specific method within a class.

        Args:
            class_name: Class name.
            method_name: Method name.

        Returns:
            Method source code only.
        """
        # Get full source and method boundaries
        source = await self.get_class_source(class_name)
        methods = await self.get_class_methods(class_name)

        # Find the requested method
        method_upper = method_name.upper()
        for m in methods:
            if m.name.upper() == method_upper:
                if m.implementation_start > 0 and m.implementation_end > 0:
                    lines = source.splitlines()
                    return "\n".join(lines[m.implementation_start - 1 : m.implementation_end])
                break

        # Fallback: regex-based extraction
        pattern = rf'(?i)METHOD\s+{re.escape(method_name)}\s*\.'
        match = re.search(pattern, source)
        if match:
            start = source[:match.start()].count("\n")
            end_pattern = rf'(?i)ENDMETHOD\s*\.'
            end_match = re.search(end_pattern, source[match.start():])
            if end_match:
                end = start + source[match.start():match.start() + end_match.end()].count("\n") + 1
                lines = source.splitlines()
                return "\n".join(lines[start:end])

        raise ValueError(f"Method '{method_name}' not found in class '{class_name}'")

    # =========================================================================
    # Package
    # =========================================================================

    async def get_package(self, name: str) -> PackageContent:
        """Get package contents.

        Args:
            name: Package name.

        Returns:
            PackageContent with objects and sub-packages.
        """
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<nodestructure:request xmlns:nodestructure="http://www.sap.com/adt/repository/nodestructure"
    parent_name="{name.upper()}"
    parent_tech_name="{name.upper()}"
    parent_type="DEVC/K"/>"""

        resp = await self.transport.post(
            "/sap/bc/adt/repository/nodestructure",
            content=body,
            content_type="application/xml",
            accept="application/xml",
        )
        return PackageContent.from_xml(resp.text, name)

    # =========================================================================
    # Table data preview
    # =========================================================================

    async def get_table_contents(
        self,
        table: str,
        *,
        max_rows: int = 100,
        columns: str = "",
        where: str = "",
    ) -> TableContentsResult:
        """Preview table data.

        Args:
            table: Table name.
            max_rows: Maximum rows to return.
            columns: Comma-separated column names (empty = all).
            where: WHERE clause (without WHERE keyword).

        Returns:
            TableContentsResult with columns and rows.
        """
        # Use freestyle SQL — simpler and more reliable than the ddic preview endpoint.
        # Normalize row limits to keep requests bounded and predictable.
        row_limit = max(1, min(int(max_rows), 1000))
        cols = columns if columns else "*"
        sql = f"SELECT {cols} FROM {table.upper()}"
        if where:
            sql += f" WHERE {where}"
        sql += f" UP TO {row_limit} ROWS"
        return await self.run_query(sql)

    async def run_query(self, sql: str) -> TableContentsResult:
        """Execute a free SQL query.

        Args:
            sql: SQL query string.

        Returns:
            TableContentsResult with query results.
        """
        sql = self._normalize_sql(sql)
        resp = await self.transport.post(
            "/sap/bc/adt/datapreview/freestyle",
            content=sql,
            content_type="text/plain",
            accept="application/vnd.sap.adt.datapreview.table.v1+xml",
        )
        return TableContentsResult.from_xml(resp.text)

    @staticmethod
    def _normalize_sql(sql: str) -> str:
        """Normalize standard SQL dialect to ABAP SQL.

        Fixes common mismatches LLMs produce:
        - ``SELECT TOP N ...`` → ``SELECT ... UP TO N ROWS``
        - Space-separated SELECT columns → comma-separated
        """
        import re

        # 1. Convert  SELECT TOP <n> <cols> FROM  →  SELECT <cols> FROM ... UP TO <n> ROWS
        top_match = re.match(
            r"(?i)^(SELECT\s+)(?:DISTINCT\s+)?TOP\s+(\d+)\s+(.+?)\s+(FROM\s+.+)$",
            sql.strip(),
        )
        if top_match:
            prefix = top_match.group(1)
            limit = top_match.group(2)
            cols = top_match.group(3)
            rest = top_match.group(4)
            # Preserve DISTINCT if present
            distinct = "DISTINCT " if "DISTINCT" in sql.upper().split("TOP")[0] else ""
            sql = f"{prefix}{distinct}{cols} {rest} UP TO {limit} ROWS"

        # 2. Ensure commas between column names in the SELECT list.
        #    Match: SELECT <col_list> FROM ...
        select_match = re.match(
            r"(?i)^(SELECT\s+(?:DISTINCT\s+)?)(.*?)\s+(FROM\s+.+)$",
            sql.strip(),
        )
        if select_match:
            prefix = select_match.group(1)
            col_part = select_match.group(2).strip()
            rest = select_match.group(3)
            # Only fix if there are no commas yet and multiple tokens (not "*" or a single col)
            if "," not in col_part and col_part != "*":
                tokens = col_part.split()
                if len(tokens) > 1:
                    col_part = ", ".join(tokens)
            sql = f"{prefix}{col_part} {rest}"

        return sql

    # =========================================================================
    # Metadata getters
    # =========================================================================

    async def get_function_group(self, name: str) -> FunctionGroup:
        """Get function group metadata including function modules."""
        path = f"/sap/bc/adt/functions/groups/{quote(name.upper())}"
        resp = await self.transport.get(path)
        return FunctionGroup.from_xml(resp.text)

    async def get_service_binding(self, name: str) -> ServiceBinding:
        """Get service binding metadata."""
        path = f"/sap/bc/adt/businessservices/bindings/{quote(name.upper())}"
        resp = await self.transport.get(path)
        return ServiceBinding.from_xml(resp.text)

    async def get_message_class(self, name: str) -> MessageClass:
        """Get message class with all message texts."""
        path = f"/sap/bc/adt/messageclass/{quote(name.upper())}"
        resp = await self.transport.get(path)
        return MessageClass.from_xml(resp.text)

    async def get_transaction(self, tcode: str) -> Transaction:
        """Get transaction code information."""
        path = f"/sap/bc/adt/vit/wb/object_type/TRAN/object_name/{quote(tcode.upper())}"
        resp = await self.transport.get(path)
        return Transaction.from_xml(resp.text)

    async def get_type_info(self, name: str) -> TypeInfo:
        """Get type information for a data element/structure."""
        path = f"/sap/bc/adt/ddic/dataelements/{quote(name.upper())}"
        resp = await self.transport.get(path)
        return TypeInfo.from_xml(resp.text)

    # =========================================================================
    # System info
    # =========================================================================

    async def get_system_info(self) -> SystemInfo:
        """Get SAP system information."""
        resp = await self.transport.get("/sap/bc/adt/system/information", accept="application/atom+xml;type=feed")
        return SystemInfo.from_xml(resp.text)

    async def get_installed_components(self) -> list[InstalledComponent]:
        """Get list of installed SAP components."""
        resp = await self.transport.get("/sap/bc/adt/system/components")
        return InstalledComponent.parse_list(resp.text)

    # =========================================================================
    # CDS dependencies
    # =========================================================================

    async def get_cds_dependencies(self, name: str) -> str:
        """Get CDS view dependencies (raw XML response).

        Args:
            name: CDS view name.

        Returns:
            XML response showing dependencies.
        """
        path = f"/sap/bc/adt/ddic/ddl/sources/{quote(name.upper())}"
        resp = await self.transport.get(path)
        return resp.text
