"""Git (abapGit) tool handlers — GitTypes, GitExport, GitImport."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vsp.config import OP_READ, OP_WRITE

if TYPE_CHECKING:
    from vsp.server import VspServer


def register_git_tools(server: VspServer) -> None:
    """Register abapGit-related MCP tools."""

    @server.mcp.tool(
        name="GitListRepos",
        description="List abapGit repositories on the system.",
    )
    async def git_list_repos() -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                "/sap/bc/adt/abapgit/repos"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GitGetRepo",
        description="Get details of a specific abapGit repository.",
    )
    async def git_get_repo(repo_key: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/abapgit/repos/{repo_key}"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GitExport",
        description="Export an ABAP package to a Git-like format (serialized ABAP objects).",
    )
    async def git_export(package: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.post(
                "/sap/bc/adt/abapgit/externalrepo/export",
                content=f'<?xml version="1.0" encoding="UTF-8"?>'
                f'<abapgit:externalRepo xmlns:abapgit="http://www.sap.com/adt/abapgit">'
                f'<abapgit:package>{package.upper()}</abapgit:package>'
                f'</abapgit:externalRepo>',
                headers={"Content-Type": "application/vnd.sap.adt.abapgit.externalrepo.v1+xml"},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GitPull",
        description="Pull (import) from a remote Git repository into SAP.",
    )
    async def git_pull(
        repo_key: str,
        branch: str = "main",
        transport: str = "",
    ) -> str:
        try:
            server.check_safety(OP_WRITE)
            if transport:
                server.check_transport(transport)
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<abapgit:pull xmlns:abapgit="http://www.sap.com/adt/abapgit">'
                f'<abapgit:branch>refs/heads/{branch}</abapgit:branch>'
            )
            if transport:
                xml += f'<abapgit:transportRequest>{transport}</abapgit:transportRequest>'
            xml += '</abapgit:pull>'
            resp = await server.transport.post(
                f"/sap/bc/adt/abapgit/repos/{repo_key}/pull",
                content=xml,
                headers={"Content-Type": "application/vnd.sap.adt.abapgit.pull.v1+xml"},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GitStage",
        description="Stage changes in an abapGit repo.",
    )
    async def git_stage(repo_key: str) -> str:
        try:
            server.check_safety(OP_READ)
            resp = await server.transport.get(
                f"/sap/bc/adt/abapgit/repos/{repo_key}/stage"
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GitPush",
        description="Push changes from SAP to the remote Git repository.",
    )
    async def git_push(
        repo_key: str,
        message: str,
        branch: str = "main",
    ) -> str:
        try:
            server.check_safety(OP_WRITE)
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<abapgit:push xmlns:abapgit="http://www.sap.com/adt/abapgit">'
                f'<abapgit:branch>refs/heads/{branch}</abapgit:branch>'
                f'<abapgit:comment>{message}</abapgit:comment>'
                f'</abapgit:push>'
            )
            resp = await server.transport.post(
                f"/sap/bc/adt/abapgit/repos/{repo_key}/push",
                content=xml,
                headers={"Content-Type": "application/vnd.sap.adt.abapgit.push.v1+xml"},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"

    @server.mcp.tool(
        name="GitLink",
        description="Link an existing ABAP package to a remote Git repository.",
    )
    async def git_link(
        url: str,
        package: str,
        branch: str = "main",
        transport: str = "",
    ) -> str:
        try:
            server.check_safety(OP_WRITE)
            server.check_package(package)
            if transport:
                server.check_transport(transport)
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<abapgit:externalRepo xmlns:abapgit="http://www.sap.com/adt/abapgit">'
                f'<abapgit:url>{url}</abapgit:url>'
                f'<abapgit:package>{package.upper()}</abapgit:package>'
                f'<abapgit:branch>refs/heads/{branch}</abapgit:branch>'
            )
            if transport:
                xml += f'<abapgit:transportRequest>{transport}</abapgit:transportRequest>'
            xml += '</abapgit:externalRepo>'
            resp = await server.transport.post(
                "/sap/bc/adt/abapgit/repos",
                content=xml,
                headers={"Content-Type": "application/vnd.sap.adt.abapgit.externalrepo.v1+xml"},
            )
            return resp.text
        except Exception as e:
            return f"Error: {e}"
