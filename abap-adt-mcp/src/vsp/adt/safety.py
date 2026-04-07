"""Safety and protection system for ADT operations.

Enforces read-only mode, operation whitelists/blacklists,
package restrictions, and transportable edit protection.
"""

from __future__ import annotations

import fnmatch
import logging
from typing import Optional

from vsp.config import (
    SafetyConfig,
    OP_ACTIVATE,
    OP_CREATE,
    OP_DELETE,
    OP_FREE_SQL,
    OP_INTELLIGENCE,
    OP_LOCK,
    OP_QUERY,
    OP_READ,
    OP_SEARCH,
    OP_TEST,
    OP_TRANSPORT,
    OP_UPDATE,
    OP_WORKFLOW,
)

logger = logging.getLogger("vsp.adt.safety")

# Write operations that are blocked in read-only mode
WRITE_OPS = {OP_CREATE, OP_UPDATE, OP_DELETE, OP_ACTIVATE, OP_LOCK, OP_WORKFLOW}


class SafetyError(Exception):
    """Raised when a safety check fails."""

    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        super().__init__(f"Safety check failed for operation '{operation}': {reason}")


def check_operation(op: str, config: SafetyConfig) -> None:
    """Check if an operation is allowed by the safety configuration.

    Args:
        op: Single-character operation code (R, S, Q, F, C, U, D, A, T, L, I, W, X).
        config: Safety configuration.

    Raises:
        SafetyError: If the operation is blocked.
    """
    # Read-only mode blocks all write operations
    if config.read_only and op in WRITE_OPS:
        raise SafetyError(op, "read-only mode is enabled")

    # Block free SQL if configured
    if config.block_free_sql and op == OP_FREE_SQL:
        raise SafetyError(op, "free SQL execution is blocked")

    # Allowed ops whitelist (if set, only these ops are allowed)
    if config.allowed_ops:
        if op not in config.allowed_ops:
            raise SafetyError(op, f"operation not in allowed list: {config.allowed_ops}")

    # Disallowed ops blacklist
    if config.disallowed_ops:
        if op in config.disallowed_ops:
            raise SafetyError(op, f"operation is in disallowed list: {config.disallowed_ops}")

    # Transport-specific checks
    if op == OP_TRANSPORT:
        if config.transport_read_only:
            raise SafetyError(op, "transport operations are read-only")


def check_package(package: str, config: SafetyConfig) -> None:
    """Check if operations are allowed on the given package.

    Args:
        package: Package name to check.
        config: Safety configuration.

    Raises:
        SafetyError: If the package is not in the allowed list.
    """
    if not config.allowed_packages:
        return  # No restrictions

    if not package:
        return  # No package specified, skip check

    # Check against wildcard patterns
    for pattern in config.allowed_packages:
        if fnmatch.fnmatch(package.upper(), pattern.upper()):
            return

    raise SafetyError(
        "package_check",
        f"package '{package}' is not in allowed packages: {config.allowed_packages}",
    )


def check_transportable(package: str, config: SafetyConfig) -> None:
    """Check if editing transportable packages is allowed.

    Local packages ($TMP, $*) are always allowed.
    Transportable packages (Z*, Y*, etc.) require explicit permission.

    Args:
        package: Package name to check.
        config: Safety configuration.

    Raises:
        SafetyError: If editing transportable packages is not allowed.
    """
    if config.allow_transportable_edits:
        return  # Explicitly allowed

    if not package:
        return  # No package info

    # Local packages are always OK
    if package.startswith("$"):
        return

    raise SafetyError(
        "transportable_check",
        f"editing objects in transportable package '{package}' requires --allow-transportable-edits",
    )


def check_transport_id(transport_id: str, config: SafetyConfig) -> None:
    """Check if a transport ID is in the allowed list.

    Args:
        transport_id: Transport request ID to check.
        config: Safety configuration.

    Raises:
        SafetyError: If the transport is not in the allowed list.
    """
    if not config.allowed_transports:
        return  # No restrictions

    if not transport_id:
        return

    if transport_id.upper() in [t.upper() for t in config.allowed_transports]:
        return

    raise SafetyError(
        "transport_id_check",
        f"transport '{transport_id}' is not in allowed transports: {config.allowed_transports}",
    )


def is_read_operation(op: str) -> bool:
    """Check if an operation type is read-only."""
    return op in {OP_READ, OP_SEARCH, OP_QUERY, OP_INTELLIGENCE}


def safety_check(op: str, config: SafetyConfig, package: Optional[str] = None) -> None:
    """Combined safety check for operation + package.

    Convenience function that runs all applicable checks.

    Args:
        op: Operation code.
        config: Safety configuration.
        package: Optional package name for package-level checks.

    Raises:
        SafetyError: If any check fails.
    """
    check_operation(op, config)

    if package:
        check_package(package, config)
        if op in WRITE_OPS:
            check_transportable(package, config)
