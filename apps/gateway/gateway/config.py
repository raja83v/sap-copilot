"""Gateway configuration via environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


_APP_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """Gateway settings loaded from environment / .env file."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # VSP MCP server path
    vsp_command: str = "vsp"  # The CLI command to spawn MCP processes
    vsp_python: str = "python"  # Python executable for running VSP

    # LiteLLM Proxy
    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str = ""
    litellm_default_model: str = "claude-sonnet-4-6"

    # Encryption key for decrypting SAP credentials from Convex
    encryption_key: str = ""

    # Proxy (for SAP connectivity)
    http_proxy: str = ""
    # Comma-separated list of hostnames/domains that bypass the proxy.
    # Localhost entries are always added automatically.
    # Example: "internal.corp.com,.corp.example.org"
    no_proxy: str = ""

    # Timeouts (seconds)
    mcp_request_timeout_sec: int = 30
    mcp_tool_call_timeout_sec: int = 300
    test_connection_timeout_sec: int = 30
    sap_http_timeout_sec: int = 120

    model_config = {
        "env_file": [_APP_ENV_FILE, ".env"],
        "env_prefix": "GATEWAY_",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
