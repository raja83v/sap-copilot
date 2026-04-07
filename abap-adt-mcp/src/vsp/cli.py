"""CLI entry point for VSP using click.

Priority: CLI flags > env vars > .env > defaults.
"""

from __future__ import annotations

import asyncio
import sys

import click

from vsp.config import Config, FeatureMode, SafetyConfig, FeatureConfig, ToolMode


@click.command(context_settings={"auto_envvar_prefix": "SAP"})
@click.option("--url", envvar="SAP_URL", help="SAP system URL (e.g., http://host:50000)")
@click.option("--user", envvar="SAP_USER", help="SAP username")
@click.option("--password", envvar="SAP_PASSWORD", help="SAP password")
@click.option("--client", envvar="SAP_CLIENT", default=None, help="SAP client number (default: 001)")
@click.option("--language", envvar="SAP_LANGUAGE", default=None, help="SAP language (default: EN)")
@click.option("--insecure", envvar="SAP_INSECURE", is_flag=True, default=False, help="Skip TLS verification")
@click.option("--timeout", envvar="SAP_TIMEOUT", type=float, default=None, help="HTTP timeout in seconds (default: 60)")
@click.option("--cookie-file", envvar="SAP_COOKIE_FILE", default=None, help="Path to Netscape-format cookie file")
@click.option("--cookie-string", envvar="SAP_COOKIE_STRING", default=None, help="Cookie string (key=val; ...)")
@click.option(
    "--mode",
    envvar="SAP_MODE",
    type=click.Choice(["focused", "expert"], case_sensitive=False),
    default=None,
    help="Tool mode: focused (52 tools) or expert (99 tools)",
)
@click.option("--disabled-groups", envvar="SAP_DISABLED_GROUPS", default=None, help="Disable tool groups (5/U, T, H, D, C, G, R, I, X)")
@click.option("--terminal-id", envvar="SAP_TERMINAL_ID", default=None, help="SAP GUI terminal ID for breakpoint sharing")
@click.option("--verbose", envvar="SAP_VERBOSE", is_flag=True, default=False, help="Enable verbose logging to stderr")
# Safety options
@click.option("--read-only", envvar="SAP_READ_ONLY", is_flag=True, default=False, help="Block all write operations")
@click.option("--block-free-sql", envvar="SAP_BLOCK_FREE_SQL", is_flag=True, default=False, help="Block RunQuery execution")
@click.option("--allowed-ops", envvar="SAP_ALLOWED_OPS", default=None, help='Whitelist operation types (e.g., "RSQ")')
@click.option("--disallowed-ops", envvar="SAP_DISALLOWED_OPS", default=None, help='Blacklist operation types (e.g., "CDUA")')
@click.option("--allowed-packages", envvar="SAP_ALLOWED_PACKAGES", default=None, help='Restrict to packages (supports wildcards: "Z*")')
@click.option("--allow-transportable-edits", envvar="SAP_ALLOW_TRANSPORTABLE_EDITS", is_flag=True, default=False, help="Allow editing objects in transportable packages")
# Feature options
@click.option("--feature-abapgit", envvar="SAP_FEATURE_ABAPGIT", type=click.Choice(["auto", "on", "off"]), default=None)
@click.option("--feature-rap", envvar="SAP_FEATURE_RAP", type=click.Choice(["auto", "on", "off"]), default=None)
@click.option("--feature-amdp", envvar="SAP_FEATURE_AMDP", type=click.Choice(["auto", "on", "off"]), default=None)
@click.option("--feature-ui5", envvar="SAP_FEATURE_UI5", type=click.Choice(["auto", "on", "off"]), default=None)
@click.option("--feature-transport", envvar="SAP_FEATURE_TRANSPORT", type=click.Choice(["auto", "on", "off"]), default=None)
def main(
    url: str | None,
    user: str | None,
    password: str | None,
    client: str | None,
    language: str | None,
    insecure: bool,
    timeout: float | None,
    cookie_file: str | None,
    cookie_string: str | None,
    mode: str | None,
    disabled_groups: str | None,
    terminal_id: str | None,
    verbose: bool,
    read_only: bool,
    block_free_sql: bool,
    allowed_ops: str | None,
    disallowed_ops: str | None,
    allowed_packages: str | None,
    allow_transportable_edits: bool,
    feature_abapgit: str | None,
    feature_rap: str | None,
    feature_amdp: str | None,
    feature_ui5: str | None,
    feature_transport: str | None,
) -> None:
    """VSP - Python MCP server for SAP ABAP Development Tools (ADT).

    Provides 52 essential tools (focused mode) or 99 complete tools (expert mode)
    for use with Claude and other MCP-compatible LLMs.
    """
    # Start from .env defaults, then override with CLI args
    config = Config.from_env()

    # Override connection settings
    if url is not None:
        config.base_url = url
    if user is not None:
        config.username = user
    if password is not None:
        config.password = password
    if client is not None:
        config.client = client
    if language is not None:
        config.language = language
    if insecure:
        config.insecure = True
    if timeout is not None:
        config.timeout = timeout
    if cookie_file is not None:
        config.cookie_file = cookie_file
    if cookie_string is not None:
        config.cookie_string = cookie_string
    if mode is not None:
        config.mode = ToolMode(mode.lower())
    if disabled_groups is not None:
        config.disabled_groups = disabled_groups
    if terminal_id is not None:
        config.terminal_id = terminal_id
    if verbose:
        config.verbose = True

    # Override safety settings
    if read_only:
        config.safety.read_only = True
    if block_free_sql:
        config.safety.block_free_sql = True
    if allowed_ops is not None:
        config.safety.allowed_ops = allowed_ops
    if disallowed_ops is not None:
        config.safety.disallowed_ops = disallowed_ops
    if allowed_packages is not None:
        config.safety.allowed_packages = [p.strip() for p in allowed_packages.split(",") if p.strip()]
    if allow_transportable_edits:
        config.safety.allow_transportable_edits = True

    # Override feature settings
    if feature_abapgit is not None:
        config.features.abapgit = FeatureMode(feature_abapgit)
    if feature_rap is not None:
        config.features.rap = FeatureMode(feature_rap)
    if feature_amdp is not None:
        config.features.amdp = FeatureMode(feature_amdp)
    if feature_ui5 is not None:
        config.features.ui5 = FeatureMode(feature_ui5)
    if feature_transport is not None:
        config.features.transport = FeatureMode(feature_transport)

    # Validate
    errors = config.validate()
    if errors:
        for err in errors:
            click.echo(f"Error: {err}", err=True)
        sys.exit(1)

    if config.verbose:
        click.echo(f"VSP starting: {config.base_url} (mode={config.mode.value})", err=True)

    # Run the MCP server
    from vsp.server import VspServer

    server = VspServer(config)
    asyncio.run(server.run_stdio())


if __name__ == "__main__":
    main()
