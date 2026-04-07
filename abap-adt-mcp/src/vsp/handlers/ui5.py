"""UI5 tool handlers — UI5 Repository operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ, OP_WRITE

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_ui5_tools(server: VspServer) -> None:
    """Register UI5 repository MCP tools."""

    @server.mcp.tool(
        name="UI5ListApps",
        description="List BSP (UI5) applications in the ABAP repository.",
    )
    async def ui5_list_apps(
        name_filter: str = "*",
        max_results: int = 50,
    ) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                "/sap/bc/adt/filestore/ui5-bsp/objects",
                params={"name": name_filter, "maxResults": str(max_results)},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="UI5GetApp",
        description="Get metadata and file list of a UI5/BSP application.",
    )
    async def ui5_get_app(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/filestore/ui5-bsp/objects/{name.upper()}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="UI5GetFileContent",
        description="Get content of a specific file in a UI5/BSP application.",
    )
    async def ui5_get_file_content(app_name: str, file_path: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/filestore/ui5-bsp/objects/{app_name.upper()}/{file_path}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="UI5UploadFile",
        description="Upload / update a file in a UI5/BSP application.",
    )
    async def ui5_upload_file(
        app_name: str,
        file_path: str,
        content: str,
        transport: str = "",
    ) -> str:
        try:
            server.check_safety(OP_WRITE)
            if transport:
                server.check_transport(transport)
            headers = {"Content-Type": "application/octet-stream"}
            params = {}
            if transport:
                params["corrNr"] = transport
            resp = await server.transport.put(
                f"/sap/bc/adt/filestore/ui5-bsp/objects/{app_name.upper()}/{file_path}",
                content=content.encode("utf-8"),
                headers=headers,
                params=params,
            )
            return f"Uploaded {file_path} to {app_name}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="UI5DeleteFile",
        description="Delete a file from a UI5/BSP application.",
    )
    async def ui5_delete_file(
        app_name: str,
        file_path: str,
        transport: str = "",
    ) -> str:
        try:
            from vsp.config import OP_DELETE
            server.check_safety(OP_DELETE)
            if transport:
                server.check_transport(transport)
            params = {}
            if transport:
                params["corrNr"] = transport
            resp = await server.transport.delete(
                f"/sap/bc/adt/filestore/ui5-bsp/objects/{app_name.upper()}/{file_path}",
                params=params,
            )
            return f"Deleted {file_path} from {app_name}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="UI5CreateApp",
        description="Create a new UI5/BSP application.",
    )
    async def ui5_create_app(
        name: str,
        package: str,
        description: str = "",
        transport: str = "",
    ) -> str:
        try:
            from vsp.config import OP_CREATE
            server.check_safety(OP_CREATE)
            server.check_package(package)
            if transport:
                server.check_transport(transport)
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<filestore:application xmlns:filestore="http://www.sap.com/adt/filestore"'
                f' filestore:name="{name.upper()}"'
                f' filestore:package="{package.upper()}"'
                f' filestore:description="{description}"'
                "/>"
            )
            params = {}
            if transport:
                params["corrNr"] = transport
            resp = await server.transport.post(
                "/sap/bc/adt/filestore/ui5-bsp/objects",
                content=xml,
                headers={"Content-Type": "application/vnd.sap.adt.filestore.application.v1+xml"},
                params=params,
            )
            return f"Created UI5 application {name}"
        except Exception as e:
            return f"Error: {e}"
