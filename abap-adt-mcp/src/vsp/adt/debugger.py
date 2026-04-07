"""Debugger operations — breakpoints, listening, stepping, variables."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from vsp.adt.http import Transport
from vsp.config import Config

if TYPE_CHECKING:
    pass

logger = logging.getLogger("vsp.adt.debugger")


@dataclass
class Breakpoint:
    """An external breakpoint."""
    id: str = ""
    uri: str = ""
    line: int = 0
    type: str = ""  # statement, exception
    active: bool = True
    condition: str = ""


@dataclass
class DebuggerVariable:
    """A variable in the debugger context."""
    name: str = ""
    value: str = ""
    type: str = ""
    kind: str = ""  # local, global, parameter
    has_children: bool = False


@dataclass
class StackFrame:
    """A stack frame in the debugger."""
    index: int = 0
    program: str = ""
    include: str = ""
    line: int = 0
    event: str = ""
    uri: str = ""


@dataclass
class DebugSession:
    """Active debug session information."""
    id: str = ""
    active: bool = False
    thread_id: str = ""
    stopped_at: Optional[StackFrame] = None
    terminal_id: str = ""


class Debugger:
    """External ABAP debugger via ADT HTTP API.

    Note: The primary debugger interface is via WebSocket (ZADT_VSP).
    This class provides the HTTP-based endpoints as fallback.
    """

    def __init__(self, transport: Transport, config: Config):
        self.transport = transport
        self.config = config
        self._terminal_id: str = config.terminal_id
        self._session: Optional[DebugSession] = None

    @property
    def terminal_id(self) -> str:
        """Get the terminal ID for breakpoint sharing."""
        if self._terminal_id:
            return self._terminal_id
        # Generate default from username
        if self.config.username:
            import hashlib
            return hashlib.md5(self.config.username.encode()).hexdigest().upper()
        return ""

    def set_terminal_id(self, terminal_id: str) -> None:
        """Set terminal ID for SAP GUI breakpoint sharing."""
        self._terminal_id = terminal_id

    # =========================================================================
    # Breakpoint operations (via WebSocket when available)
    # =========================================================================

    async def set_breakpoint(
        self,
        uri: str,
        line: int,
        *,
        bp_type: str = "statement",
        condition: str = "",
    ) -> Breakpoint:
        """Set an external breakpoint.

        Args:
            uri: ADT URI of the source object.
            line: Line number (1-based).
            bp_type: Breakpoint type (statement, exception).
            condition: Optional breakpoint condition.

        Returns:
            Created Breakpoint object.
        """
        # This will be delegated to WebSocket client when available
        raise NotImplementedError("Use WebSocket client for breakpoint operations")

    async def get_breakpoints(self) -> list[Breakpoint]:
        """Get all active breakpoints."""
        raise NotImplementedError("Use WebSocket client for breakpoint operations")

    async def delete_breakpoint(self, bp_id: str) -> None:
        """Delete a breakpoint."""
        raise NotImplementedError("Use WebSocket client for breakpoint operations")

    # =========================================================================
    # Debug session operations
    # =========================================================================

    async def listen(self, *, timeout: int = 60, terminal_id: str = "") -> DebugSession:
        """Start listening for a debug event (breakpoint hit).

        Args:
            timeout: Listen timeout in seconds.
            terminal_id: Optional terminal ID override.

        Returns:
            DebugSession if a breakpoint was hit.
        """
        raise NotImplementedError("Use WebSocket client for debug listening")

    async def attach(self, session_id: str) -> DebugSession:
        """Attach to a stopped debug session."""
        raise NotImplementedError("Use WebSocket client for debug attaching")

    async def detach(self) -> None:
        """Detach from the current debug session."""
        raise NotImplementedError("Use WebSocket client for debug detaching")

    async def step(self, step_type: str = "into") -> Optional[StackFrame]:
        """Step in the debugger.

        Args:
            step_type: Step type: into, over, out, continue.

        Returns:
            New stack frame after stepping.
        """
        raise NotImplementedError("Use WebSocket client for debug stepping")

    async def get_stack(self) -> list[StackFrame]:
        """Get the current call stack."""
        raise NotImplementedError("Use WebSocket client for debug stack")

    async def get_variables(self, *, scope: str = "local") -> list[DebuggerVariable]:
        """Get variables in the current scope.

        Args:
            scope: Variable scope: local, global, all.
        """
        raise NotImplementedError("Use WebSocket client for debug variables")
