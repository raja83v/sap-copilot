"""Transport tool handlers — List, Get, Create, Release, Delete transports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ, OP_TRANSPORT

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_transport_tools(server: VspServer) -> None:
    """Register transport management MCP tools."""

    @server.mcp.tool(
        name="ListTransports",
        description="List transport requests. Optionally filter by user, type, or status.",
    )
    async def list_transports(
        user: str = "",
        status: str = "modifiable",
        target: str = "",
        max_results: int = 50,
    ) -> str:
        try:
            server.check_safety(OP_TRANSPORT)
            params: dict = {"maxResults": str(max_results)}
            if user:
                params["user"] = user
            if status:
                params["status"] = status
            if target:
                params["target"] = target
            resp = await server.transport.get(
                "/sap/bc/adt/cts/transportrequests", params=params
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetTransport",
        description="Get details of a specific transport request including its tasks and objects.",
    )
    async def get_transport(transport_id: str) -> str:
        try:
            server.check_safety(OP_TRANSPORT)
            resp = await server.transport.get(
                f"/sap/bc/adt/cts/transportrequests/{transport_id}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="CreateTransport",
        description="Create a new transport request.",
    )
    async def create_transport(
        description: str,
        target: str = "",
        transport_type: str = "K",
    ) -> str:
        try:
            server.check_safety(OP_TRANSPORT)
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<tm:root xmlns:tm="http://www.sap.com/cts/adt/tm">'
                f'<tm:request tm:type="{transport_type}">'
                f'<tm:short_text>{description}</tm:short_text>'
            )
            if target:
                xml += f'<tm:target>{target}</tm:target>'
            xml += "</tm:request></tm:root>"

            resp = await server.transport.post(
                "/sap/bc/adt/cts/transportrequests",
                content=xml,
                headers={"Content-Type": "application/vnd.sap.adt.cts.transportrequests.v1+xml"},
            )
            return f"Transport created: {resp.text.strip()}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="ReleaseTransport",
        description="Release a transport request or task (makes it ready for import).",
    )
    async def release_transport(transport_id: str) -> str:
        try:
            server.check_safety(OP_TRANSPORT)
            server.check_transport(transport_id)
            resp = await server.transport.post(
                f"/sap/bc/adt/cts/transportrequests/{transport_id}/newreleasejobs"
            )
            return f"Transport {transport_id} released. {resp.text.strip()}"
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="DeleteTransport",
        description="Delete a transport request (must be empty/modifiable).",
    )
    async def delete_transport(transport_id: str) -> str:
        try:
            from vsp.config import OP_DELETE
            server.check_safety(OP_DELETE)
            server.check_transport(transport_id)
            resp = await server.transport.delete(
                f"/sap/bc/adt/cts/transportrequests/{transport_id}"
            )
            return f"Transport {transport_id} deleted."
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="AddToTransport",
        description="Add an object to a transport request.",
    )
    async def add_to_transport(
        transport_id: str,
        name: str,
        object_type: str,
    ) -> str:
        try:
            server.check_safety(OP_TRANSPORT)
            server.check_transport(transport_id)
            resp = await server.transport.post(
                f"/sap/bc/adt/cts/transportrequests/{transport_id}/tasks",
                params={"objname": name, "objtype": object_type},
            )
            return f"Added {object_type} {name} to transport {transport_id}"
        except Exception as e:
            return f"Error: {e}"
