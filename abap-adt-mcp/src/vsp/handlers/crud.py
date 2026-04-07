"""CRUD tool handlers — Lock, Unlock, Create, Delete, Write, Edit, Clone."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_CREATE, OP_DELETE, OP_WRITE

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_crud_tools(server: VspServer) -> None:
    """Register CRUD-related MCP tools."""

    @server.mcp.tool(
        name="LockObject",
        description="Acquire an exclusive lock on an ABAP object for editing. "
        "Returns a lock handle required for write operations.",
    )
    async def lock_object(name: str, object_type: str) -> str:
        try:
            server.check_safety(OP_WRITE)
            handle = await server.crud.lock_object(object_type, name)
            return f"Lock acquired. Handle: {handle}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="UnlockObject",
        description="Release a previously acquired lock on an ABAP object.",
    )
    async def unlock_object(name: str, object_type: str, lock_handle: str) -> str:
        try:
            server.check_safety(OP_WRITE)
            await server.crud.unlock_object(object_type, name, lock_handle)
            return f"Lock released for {object_type} {name}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="CreateObject",
        description="Create a new ABAP object. Supports: PROG, CLAS, INTF, FUGR, FUNC, INCL, TABL, DDLS, SRVD, SRVB, etc. "
        "Requires package and optional transport request. For SRVB, provide service_definition name.",
    )
    async def create_object(
        name: str,
        object_type: str,
        package: str,
        description: str = "",
        transport: str = "",
        source: str = "",
        service_definition: str = "",
    ) -> str:
        try:
            server.check_safety(OP_CREATE)
            server.check_package(package)
            if transport:
                server.check_transport(transport)
            kwargs: dict[str, str] = {}
            if service_definition:
                kwargs["service_definition"] = service_definition
            await server.crud.create_object(
                object_type, name,
                package=package,
                description=description,
                transport=transport,
                source=source,
                **kwargs,
            )
            return f"Created {object_type} {name} in package {package}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="CreatePackage",
        description="Create a new ABAP package (development class).",
    )
    async def create_package(
        name: str,
        description: str,
        super_package: str = "",
        transport: str = "",
        software_component: str = "",
        transport_layer: str = "",
    ) -> str:
        try:
            server.check_safety(OP_CREATE)
            await server.crud.create_package(
                name,
                description=description,
                super_package=super_package,
                transport=transport,
                software_component=software_component,
                transport_layer=transport_layer,
            )
            return f"Created package {name}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="CreateTable",
        description="Create a new transparent database table.",
    )
    async def create_table(
        name: str,
        package: str,
        description: str = "",
        transport: str = "",
        source: str = "",
    ) -> str:
        try:
            server.check_safety(OP_CREATE)
            server.check_package(package)
            if transport:
                server.check_transport(transport)
            await server.crud.create_table(
                name,
                package=package,
                description=description,
                transport=transport,
                source=source,
            )
            return f"Created table {name}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DeleteObject",
        description="Delete an ABAP object. Requires transport for transportable objects.",
    )
    async def delete_object(
        name: str,
        object_type: str,
        transport: str = "",
        lock_handle: str = "",
    ) -> str:
        try:
            server.check_safety(OP_DELETE)
            if transport:
                server.check_transport(transport)
            # Auto-acquire lock if not provided
            acquired_handle = lock_handle
            if not acquired_handle:
                acquired_handle = await server.crud.lock_object(object_type, name)
            try:
                await server.crud.delete_object(
                    object_type, name,
                    transport=transport,
                    lock_handle=acquired_handle,
                )
            except Exception:
                # Best-effort unlock on failure
                if not lock_handle and acquired_handle:
                    try:
                        await server.crud.unlock_object(object_type, name, acquired_handle)
                    except Exception:
                        pass
                raise
            return f"Deleted {object_type} {name}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="WriteSource",
        description="High-level: Write (replace) source code of an ABAP object. "
        "Handles lock/unlock and optional activation automatically. "
        "Supports method-level writes for classes.",
    )
    async def write_source(
        name: str,
        source: str,
        object_type: str = "",
        method: str = "",
        transport: str = "",
        activate: bool = True,
    ) -> str:
        try:
            server.check_safety(OP_WRITE)
            if transport:
                server.check_transport(transport)
            result = await server.workflows.write_source(
                object_type, name, source,
                method=method,
                transport=transport,
                activate=activate,
            )
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="EditSource",
        description="High-level: Search and replace within source code. "
        "Handles lock/unlock/activation. Supports regex patterns.",
    )
    async def edit_source(
        name: str,
        search: str,
        replace: str,
        object_type: str = "",
        method: str = "",
        transport: str = "",
        activate: bool = True,
        regex: bool = False,
    ) -> str:
        try:
            server.check_safety(OP_WRITE)
            if transport:
                server.check_transport(transport)
            result = await server.workflows.edit_source(
                object_type, name,
                search=search,
                replace=replace,
                method=method,
                transport=transport,
                activate=activate,
                regex=regex,
            )
            return result
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="CompareSource",
        description="Compare current source with given source; returns unified diff.",
    )
    async def compare_source(
        name: str,
        source: str,
        object_type: str = "",
        method: str = "",
    ) -> str:
        try:
            server.check_safety(OP_WRITE)
            diff = await server.workflows.compare_source(
                object_type, name, source, method=method
            )
            return diff if diff else "No differences"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="CloneObject",
        description="Clone an ABAP object to a new name. Copies source and creates the target.",
    )
    async def clone_object(
        source_name: str,
        target_name: str,
        object_type: str,
        package: str,
        transport: str = "",
    ) -> str:
        try:
            server.check_safety(OP_CREATE)
            server.check_package(package)
            if transport:
                server.check_transport(transport)
            result = await server.workflows.clone_object(
                object_type, source_name, target_name,
                package=package,
                transport=transport,
            )
            return result
        except Exception as e:
            return f"Error: {e}"
