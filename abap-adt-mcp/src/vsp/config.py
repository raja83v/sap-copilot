"""Configuration system for VSP.

Priority: CLI flags > environment variables > .env file > defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SessionType(str, Enum):
    """ADT session types."""
    STATEFUL = "stateful"
    STATELESS = "stateless"
    KEEP = "keep"


class ToolMode(str, Enum):
    """Tool visibility mode."""
    FOCUSED = "focused"
    EXPERT = "expert"


class FeatureMode(str, Enum):
    """Feature toggle mode."""
    AUTO = "auto"
    ON = "on"
    OFF = "off"


# Operation type codes (single characters)
OP_READ = "R"
OP_SEARCH = "S"
OP_QUERY = "Q"
OP_FREE_SQL = "F"
OP_CREATE = "C"
OP_UPDATE = "U"
OP_WRITE = "U"  # Alias for OP_UPDATE
OP_DELETE = "D"
OP_ACTIVATE = "A"
OP_TEST = "T"
OP_LOCK = "L"
OP_INTELLIGENCE = "I"
OP_WORKFLOW = "W"
OP_TRANSPORT = "X"
OP_DEBUG = "B"
OP_INSTALL = "N"


@dataclass
class SafetyConfig:
    """Safety and protection configuration."""

    read_only: bool = False
    block_free_sql: bool = False
    allowed_ops: str = ""
    disallowed_ops: str = ""
    allowed_packages: list[str] = field(default_factory=list)
    dry_run: bool = False
    allow_transportable_edits: bool = False
    enable_transports: bool = True
    transport_read_only: bool = False
    allowed_transports: list[str] = field(default_factory=list)


@dataclass
class FeatureConfig:
    """Feature detection configuration."""

    abapgit: FeatureMode = FeatureMode.AUTO
    rap: FeatureMode = FeatureMode.AUTO
    amdp: FeatureMode = FeatureMode.AUTO
    ui5: FeatureMode = FeatureMode.AUTO
    transport: FeatureMode = FeatureMode.AUTO
    hana: FeatureMode = FeatureMode.AUTO


@dataclass
class Config:
    """VSP configuration.

    All fields support override via CLI flags, environment variables, or .env file.
    """

    # Connection
    base_url: str = ""
    username: str = ""
    password: str = ""
    client: str = "001"
    language: str = "EN"
    insecure: bool = False
    timeout: float = 60.0

    # Cookie authentication (alternative to user/password)
    cookie_file: Optional[str] = None
    cookie_string: Optional[str] = None

    # Tool mode
    mode: ToolMode = ToolMode.FOCUSED
    disabled_groups: str = ""

    # Session
    session_type: SessionType = SessionType.STATELESS

    # Debugger
    terminal_id: str = ""

    # Logging
    verbose: bool = False

    # Nested configs
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)

    @property
    def uses_cookie_auth(self) -> bool:
        """Whether cookie-based authentication is configured."""
        return bool(self.cookie_file or self.cookie_string)

    @property
    def uses_basic_auth(self) -> bool:
        """Whether basic authentication is configured."""
        return bool(self.username and self.password)

    def validate(self) -> list[str]:
        """Validate configuration, returning list of error messages."""
        errors: list[str] = []

        if not self.base_url:
            errors.append("SAP URL is required (--url or SAP_URL)")

        # Auth: must have exactly one method
        has_basic = self.uses_basic_auth
        has_cookie = self.uses_cookie_auth
        if not has_basic and not has_cookie:
            errors.append("Authentication required: provide user/password or cookie-file/cookie-string")
        if has_basic and has_cookie:
            errors.append("Cannot use both basic auth and cookie auth simultaneously")

        # URL should not have trailing slash
        if self.base_url.endswith("/"):
            self.base_url = self.base_url.rstrip("/")

        return errors

    @classmethod
    def from_env(cls) -> Config:
        """Build config from environment variables (includes .env via python-dotenv)."""
        from dotenv import load_dotenv

        load_dotenv()

        safety = SafetyConfig(
            read_only=_env_bool("SAP_READ_ONLY", False),
            block_free_sql=_env_bool("SAP_BLOCK_FREE_SQL", False),
            allowed_ops=os.getenv("SAP_ALLOWED_OPS", ""),
            disallowed_ops=os.getenv("SAP_DISALLOWED_OPS", ""),
            allowed_packages=_env_list("SAP_ALLOWED_PACKAGES"),
            allow_transportable_edits=_env_bool("SAP_ALLOW_TRANSPORTABLE_EDITS", False),
        )

        features = FeatureConfig(
            abapgit=FeatureMode(os.getenv("SAP_FEATURE_ABAPGIT", "auto").lower()),
            rap=FeatureMode(os.getenv("SAP_FEATURE_RAP", "auto").lower()),
            amdp=FeatureMode(os.getenv("SAP_FEATURE_AMDP", "auto").lower()),
            ui5=FeatureMode(os.getenv("SAP_FEATURE_UI5", "auto").lower()),
            transport=FeatureMode(os.getenv("SAP_FEATURE_TRANSPORT", "auto").lower()),
            hana=FeatureMode(os.getenv("SAP_FEATURE_HANA", "auto").lower()) if os.getenv("SAP_FEATURE_HANA") else FeatureMode.AUTO,
        )

        return cls(
            base_url=os.getenv("SAP_URL", ""),
            username=os.getenv("SAP_USER", ""),
            password=os.getenv("SAP_PASSWORD", ""),
            client=os.getenv("SAP_CLIENT", "001"),
            language=os.getenv("SAP_LANGUAGE", "EN"),
            insecure=_env_bool("SAP_INSECURE", False),
            timeout=float(os.getenv("SAP_TIMEOUT", "60.0")),
            cookie_file=os.getenv("SAP_COOKIE_FILE"),
            cookie_string=os.getenv("SAP_COOKIE_STRING"),
            mode=ToolMode(os.getenv("SAP_MODE", "focused").lower()),
            disabled_groups=os.getenv("SAP_DISABLED_GROUPS", ""),
            terminal_id=os.getenv("SAP_TERMINAL_ID", ""),
            verbose=_env_bool("SAP_VERBOSE", False),
            safety=safety,
            features=features,
        )

    def override_with(self, **kwargs: object) -> Config:
        """Return a new Config with the given fields overridden (non-None values only)."""
        import dataclasses

        changes: dict[str, object] = {}
        for k, v in kwargs.items():
            if v is not None and hasattr(self, k):
                changes[k] = v
        return dataclasses.replace(self, **changes)


def _env_bool(key: str, default: bool) -> bool:
    """Read a boolean from an environment variable."""
    val = os.getenv(key, "").lower()
    if not val:
        return default
    return val in ("true", "1", "yes", "on")


def _env_list(key: str) -> list[str]:
    """Read a comma-separated list from an environment variable."""
    val = os.getenv(key, "")
    if not val:
        return []
    return [item.strip() for item in val.split(",") if item.strip()]
