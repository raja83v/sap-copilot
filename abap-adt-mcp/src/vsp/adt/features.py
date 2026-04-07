"""Feature detection for SAP system capabilities.

Probes the SAP system to detect available features (abapGit, RAP, AMDP, etc.)
with caching. Supports auto/on/off modes per feature.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from vsp.config import FeatureConfig, FeatureMode

if TYPE_CHECKING:
    from vsp.adt.http import Transport

logger = logging.getLogger("vsp.adt.features")

# Probe endpoints — OPTIONS request to check if the API exists
FEATURE_PROBE_ENDPOINTS: dict[str, str] = {
    "abapgit": "/sap/bc/adt/abapgit/repos",
    "rap": "/sap/bc/adt/ddic/ddl/sources",
    "amdp": "/sap/bc/adt/debugger/amdp/sessions",
    "ui5": "/sap/bc/adt/filestore/ui5-bsp",
    "transport": "/sap/bc/adt/cts/transports",
    "hana": "/sap/bc/adt/debugger/amdp/sessions",
}

# Cache TTL for probe results (5 minutes)
PROBE_CACHE_TTL = 300.0


@dataclass
class FeatureStatus:
    """Status of a detected feature."""
    id: str
    available: bool
    mode: FeatureMode
    message: str = ""
    probed_at: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "available": self.available,
            "mode": self.mode.value,
            "message": self.message,
        }


class FeatureProber:
    """Probes SAP system to detect available features.

    Results are cached with TTL. Each feature can be set to auto (probe),
    on (force available), or off (force unavailable).
    """

    def __init__(self, transport: Transport, config: FeatureConfig, verbose: bool = False):
        self._transport = transport
        self._config = config
        self._verbose = verbose
        self._cache: dict[str, FeatureStatus] = {}
        self._lock = asyncio.Lock()

    async def is_available(self, feature_id: str) -> bool:
        """Check if a feature is available.

        Args:
            feature_id: Feature identifier (abapgit, rap, amdp, ui5, transport, hana).

        Returns:
            True if the feature is available.
        """
        status = await self.get_status(feature_id)
        return status.available

    async def get_status(self, feature_id: str) -> FeatureStatus:
        """Get the status of a specific feature.

        Args:
            feature_id: Feature identifier.

        Returns:
            FeatureStatus with availability and mode information.
        """
        mode = self._get_mode(feature_id)

        # Force on/off
        if mode == FeatureMode.ON:
            return FeatureStatus(id=feature_id, available=True, mode=mode, message="forced on")
        if mode == FeatureMode.OFF:
            return FeatureStatus(id=feature_id, available=False, mode=mode, message="forced off")

        # Auto: probe with cache
        return await self._probe(feature_id)

    async def get_all_features(self) -> list[FeatureStatus]:
        """Get status of all known features."""
        features = []
        for feature_id in FEATURE_PROBE_ENDPOINTS:
            status = await self.get_status(feature_id)
            features.append(status)
        return features

    def _get_mode(self, feature_id: str) -> FeatureMode:
        """Get the configured mode for a feature."""
        return getattr(self._config, feature_id, FeatureMode.AUTO)

    async def _probe(self, feature_id: str) -> FeatureStatus:
        """Probe the SAP system for a feature's availability."""
        async with self._lock:
            # Check cache
            cached = self._cache.get(feature_id)
            if cached and (time.monotonic() - cached.probed_at) < PROBE_CACHE_TTL:
                return cached

            # Probe
            endpoint = FEATURE_PROBE_ENDPOINTS.get(feature_id)
            if not endpoint:
                status = FeatureStatus(
                    id=feature_id, available=False, mode=FeatureMode.AUTO,
                    message=f"unknown feature: {feature_id}",
                )
                self._cache[feature_id] = status
                return status

            try:
                resp = await self._transport.options(endpoint)
                available = resp.status_code < 400
                message = "detected" if available else f"not available (HTTP {resp.status_code})"
            except Exception as e:
                available = False
                message = f"probe failed: {e}"

            if self._verbose:
                logger.info("Feature probe %s: %s (%s)", feature_id, available, message)

            status = FeatureStatus(
                id=feature_id,
                available=available,
                mode=FeatureMode.AUTO,
                message=message,
                probed_at=time.monotonic(),
            )
            self._cache[feature_id] = status
            return status
