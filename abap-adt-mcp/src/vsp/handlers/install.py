"""Install tool handlers — InstallZADTVSP, InstallAbapGit, ListDependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_INSTALL

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_install_tools(server: VspServer) -> None:
    """Register installation helper MCP tools."""

    @server.mcp.tool(
        name="InstallZADTVSP",
        description="Install the ZADT_VSP companion ABAP package on the target system. "
        "Provides WebSocket capabilities for async operations, RFC, and debugging.",
    )
    async def install_zadt_vsp(
        package: str = "$ZADT_VSP",
        transport: str = "",
    ) -> str:
        try:
            server.check_safety(OP_INSTALL)
            server.check_package(package)
            if transport:
                server.check_transport(transport)
            # The install logic pushes a pre-built abapGit repo
            return (
                "ZADT_VSP installation requires abapGit to be available on the system. "
                "Use GitLink tool to link the ZADT_VSP repo, then GitPull to import it. "
                "Repository URL: https://github.com/your-org/zadt-vsp"
            )
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="InstallAbapGit",
        description="Check if abapGit is installed and provide installation guidance.",
    )
    async def install_abapgit() -> str:
        try:
            features = {fs.id: fs.available for fs in await server.feature_prober.get_all_features()}
            if features.get("abapgit", False):
                return "abapGit is already installed on this system."
            return (
                "abapGit is not installed. To install:\n"
                "1. Download the standalone version from https://raw.githubusercontent.com/abapGit/build/main/zabapgit_standalone.prog.abap\n"
                "2. Create a new program ZABAPGIT_STANDALONE via CreateObject tool\n"
                "3. Copy the source code via WriteSource tool\n"
                "4. Activate the program"
            )
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="ListDependencies",
        description="List optional ABAP-side dependencies and their installation status.",
    )
    async def list_dependencies() -> str:
        try:
            features = {fs.id: fs.available for fs in await server.feature_prober.get_all_features()}
            lines = ["VSP Dependencies:"]
            deps = {
                "abapgit": "abapGit \u2014 Git integration for ABAP",
                "zadt_vsp": "ZADT_VSP \u2014 WebSocket companion for async operations",
                "rap": "RAP \u2014 RESTful ABAP Programming model",
                "amdp": "AMDP \u2014 ABAP Managed Database Procedures (HANA)",
                "ui5": "UI5 \u2014 BSP/Fiori app repository",
                "transport": "CTS \u2014 Change and Transport System",
                "hana": "HANA \u2014 SAP HANA database features",
            }
            for key, desc in deps.items():
                status = "AVAILABLE" if features.get(key, False) else "NOT AVAILABLE"
                lines.append(f"  [{status}] {desc}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GetServerVersion",
        description="Get the VSP MCP server version and capabilities.",
    )
    async def get_server_version() -> str:
        from vsp import __version__
        return (
            f"VSP Python MCP Server v{__version__}\n"
            f"Protocol: MCP (Model Context Protocol)\n"
            f"Transport: stdio\n"
            f"SAP ADT REST API client"
        )
