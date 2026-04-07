"""MCP Server — tool registration and handler dispatch.

Registers all tools with the MCP SDK and dispatches calls
to the appropriate ADT client methods.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from mcp.server import FastMCP
from mcp.types import TextContent, Tool

from vsp.adt.client import ADTClient
from vsp.adt.codeintel import CodeIntelligence
from vsp.adt.crud import CRUDOperations
from vsp.adt.debugger import Debugger
from vsp.adt.devtools import DevTools
from vsp.adt.features import FeatureProber
from vsp.adt.safety import SafetyError, check_operation, check_package, safety_check
from vsp.adt.websocket import WebSocketClient
from vsp.adt.workflows import Workflows
from vsp.config import (
    Config,
    OP_ACTIVATE,
    OP_CREATE,
    OP_DEBUG,
    OP_DELETE,
    OP_FREE_SQL,
    OP_INSTALL,
    OP_INTELLIGENCE,
    OP_LOCK,
    OP_QUERY,
    OP_READ,
    OP_SEARCH,
    OP_TEST,
    OP_TRANSPORT,
    OP_UPDATE,
    OP_WORKFLOW,
    ToolMode,
)

logger = logging.getLogger("vsp.server")

# Tool group codes for --disabled-groups
TOOL_GROUPS = {
    "5": "ui5",
    "U": "ui5",
    "T": "test",
    "H": "hana",
    "D": "debug",
    "C": "cts",
    "G": "git",
    "R": "reports",
    "I": "install",
    "X": "experimental",
}


class VspServer:
    """MCP Server for SAP ABAP Development Tools.

    Provides 52 essential tools (focused mode) or 99 complete tools (expert mode).
    """

    def __init__(self, config: Config):
        self.config = config
        self.mcp = FastMCP("vsp")

        # ADT components (initialized on startup)
        self._client: Optional[ADTClient] = None
        self._crud: Optional[CRUDOperations] = None
        self._devtools: Optional[DevTools] = None
        self._codeintel: Optional[CodeIntelligence] = None
        self._workflows: Optional[Workflows] = None
        self._debugger: Optional[Debugger] = None
        self._ws_client: Optional[WebSocketClient] = None
        self._feature_prober: Optional[FeatureProber] = None

        # Parse disabled groups
        self._disabled_groups: set[str] = set()
        for ch in config.disabled_groups.upper():
            group = TOOL_GROUPS.get(ch)
            if group:
                self._disabled_groups.add(group)

        # Register tools
        self._register_tools()

    def _is_group_enabled(self, group: str) -> bool:
        """Check if a tool group is enabled."""
        return group not in self._disabled_groups

    def _is_expert(self) -> bool:
        """Check if expert mode is active."""
        return self.config.mode == ToolMode.EXPERT

    # =========================================================================
    # Tool Registration
    # =========================================================================

    def _register_tools(self) -> None:
        """Register all MCP tools based on mode and disabled groups."""

        # Import handlers
        from vsp.handlers.read import register_read_tools
        from vsp.handlers.search import register_search_tools
        from vsp.handlers.system import register_system_tools
        from vsp.handlers.crud import register_crud_tools
        from vsp.handlers.devtools import register_devtools_tools
        from vsp.handlers.codeintel import register_codeintel_tools
        from vsp.handlers.diagnostics import register_diagnostics_tools
        from vsp.handlers.transport import register_transport_tools
        from vsp.handlers.analysis import register_analysis_tools

        # Always-registered tools
        register_system_tools(self)

        # Core tools (focused + expert)
        register_read_tools(self)
        register_search_tools(self)
        register_devtools_tools(self)
        register_codeintel_tools(self)
        register_diagnostics_tools(self)
        register_analysis_tools(self)

        # CRUD tools
        register_crud_tools(self)

        # Transport tools
        if self._is_group_enabled("cts"):
            register_transport_tools(self)

        # Conditional tool groups
        if self._is_group_enabled("debug"):
            from vsp.handlers.debug import register_debug_tools
            register_debug_tools(self)

        if self._is_group_enabled("ui5"):
            from vsp.handlers.ui5 import register_ui5_tools
            register_ui5_tools(self)

        if self._is_group_enabled("git"):
            from vsp.handlers.git import register_git_tools
            register_git_tools(self)

        if self._is_group_enabled("reports"):
            from vsp.handlers.report import register_report_tools
            register_report_tools(self)

        if self._is_group_enabled("install"):
            from vsp.handlers.install import register_install_tools
            register_install_tools(self)

        if self._is_group_enabled("hana"):
            from vsp.handlers.amdp import register_amdp_tools
            register_amdp_tools(self)

    # =========================================================================
    # Component accessors (lazy init)
    # =========================================================================

    @property
    def client(self) -> ADTClient:
        if self._client is None:
            raise RuntimeError("Server not started")
        return self._client

    @property
    def crud(self) -> CRUDOperations:
        if self._crud is None:
            raise RuntimeError("Server not started")
        return self._crud

    @property
    def devtools(self) -> DevTools:
        if self._devtools is None:
            raise RuntimeError("Server not started")
        return self._devtools

    @property
    def codeintel(self) -> CodeIntelligence:
        if self._codeintel is None:
            raise RuntimeError("Server not started")
        return self._codeintel

    @property
    def workflows(self) -> Workflows:
        if self._workflows is None:
            raise RuntimeError("Server not started")
        return self._workflows

    @property
    def debugger(self) -> Debugger:
        if self._debugger is None:
            raise RuntimeError("Server not started")
        return self._debugger

    @property
    def ws_client(self) -> WebSocketClient:
        if self._ws_client is None:
            raise RuntimeError("Server not started")
        return self._ws_client

    @property
    def feature_prober(self) -> FeatureProber:
        if self._feature_prober is None:
            raise RuntimeError("Server not started")
        return self._feature_prober

    # =========================================================================
    # Safety helpers
    # =========================================================================

    def check_safety(self, op: str, package: str = "") -> None:
        """Run safety checks, raising SafetyError on failure."""
        safety_check(op, self.config.safety, package or None)

    def check_package(self, package: str) -> None:
        """Run package safety checks."""
        check_package(package, self.config.safety)

    def check_transport(self, transport_id: str) -> None:
        """Validate transport ID against allowed list."""
        from vsp.adt.safety import check_transport_id
        check_transport_id(transport_id, self.config.safety)

    @property
    def transport(self):
        """Access the HTTP transport layer directly."""
        return self.client.transport

    # =========================================================================
    # Server lifecycle
    # =========================================================================

    async def run_stdio(self) -> None:
        """Run the MCP server over stdio."""
        # Initialize ADT components
        self._client = ADTClient(self.config)
        await self._client.__aenter__()

        self._crud = CRUDOperations(self._client.transport, self.config)
        self._devtools = DevTools(self._client.transport, self.config)
        self._codeintel = CodeIntelligence(self._client.transport, self.config)
        self._workflows = Workflows(self._client, self._crud, self._devtools)
        self._debugger = Debugger(self._client.transport, self.config)
        self._ws_client = WebSocketClient(self.config)
        self._feature_prober = FeatureProber(self._client.transport, self.config.features, self.config.verbose)

        if self.config.verbose:
            logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
            logger.info(
                "VSP server starting (mode=%s)",
                self.config.mode.value,
            )

        try:
            await self.mcp.run_stdio_async()
        finally:
            await self._client.__aexit__(None, None, None)
            await self._ws_client.close()


def tool_result_text(text: str) -> list[TextContent]:
    """Create a successful tool result with text content."""
    return [TextContent(type="text", text=text)]


def tool_result_error(message: str) -> list[TextContent]:
    """Create an error tool result."""
    return [TextContent(type="text", text=f"Error: {message}")]
