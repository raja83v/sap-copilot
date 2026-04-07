"""System tool handlers — GetConnectionInfo, GetFeatures, GetAbapHelp, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_system_tools(server: VspServer) -> None:
    """Register system-related MCP tools."""

    @server.mcp.tool(
        name="GetConnectionInfo",
        description="Get information about the current SAP connection (system, client, user, language, features).",
    )
    async def get_connection_info() -> str:
        try:
            cfg = server.transport.config
            info = await server.client.get_system_info()
            lines = [
                f"URL: {cfg.base_url}",
                f"Client: {cfg.client}",
                f"User: {cfg.username}",
                f"Language: {cfg.language}",
                f"Host: {info.node_name}",
                f"App Server: {info.app_server}",
                f"Kernel: {info.kernel_release}",
                f"DB: {info.database_system} {info.database_release}",
                f"IP: {info.ip_address}",
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetFeatures",
        description="Check which optional features are available on this system "
        "(ABAPGit, RAP, AMDP, UI5 Repository, Transport, HANA).",
    )
    async def get_features() -> str:
        try:
            statuses = await server.feature_prober.get_all_features()
            lines = ["Feature availability:"]
            for fs in statuses:
                mark = "YES" if fs.available else "NO"
                lines.append(f"  {fs.id}: {mark} ({fs.message})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetAbapHelp",
        description="Get ABAP keyword documentation / F1 help for a given keyword.",
    )
    async def get_abap_help(keyword: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/docu/abap/langu?keyword={keyword.upper()}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetSystemInfo",
        description="Get detailed SAP system information.",
    )
    async def get_system_info() -> str:
        try:
            info = await server.client.get_system_info()
            return str(info)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetInstalledComponents",
        description="Get list of installed software components and their versions.",
    )
    async def get_installed_components() -> str:
        try:
            server.check_safety(OP_READ)
            components = await server.client.get_installed_components()
            if not components:
                return "No installed components found."
            lines = [f"Installed Components ({len(components)}):"]
            for c in components:
                lines.append(f"  {c.name} {c.version} - {c.description}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetServiceBinding",
        description="Get service binding metadata including published services and endpoints.",
    )
    async def get_service_binding(name: str) -> str:
        try:
            server.check_safety(OP_READ)
            sb = await server.client.get_service_binding(name)
            lines = [f"Service Binding: {sb.name}", f"Description: {sb.description}"]
            if sb.services:
                lines.append(f"\nPublished Services ({len(sb.services)}):")
                for svc in sb.services:
                    lines.append(f"  {svc.get('name', 'N/A')} - {svc.get('version', 'N/A')}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"
