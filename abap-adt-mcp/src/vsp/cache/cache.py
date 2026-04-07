"""Cache module — SQLite-backed async cache for ADT responses.

Caches expensive reads (package content, search results, system info)
to reduce round-trips to the SAP system.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("vsp.cache")

# Default TTL (5 minutes)
DEFAULT_TTL = 300


@dataclass
class CacheEntry:
    """A single cache entry."""

    key: str
    value: str
    created_at: float
    ttl: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl


class MemoryCache:
    """In-memory LRU cache with TTL support.

    Suitable for single-session use; data is lost on restart.
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = DEFAULT_TTL):
        self._store: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    @staticmethod
    def _make_key(namespace: str, *parts: str) -> str:
        """Create a cache key from namespace and parts."""
        raw = f"{namespace}:" + ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()

    async def get(self, namespace: str, *parts: str) -> Optional[str]:
        """Get a value from cache. Returns None if missing or expired."""
        key = self._make_key(namespace, *parts)
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._store[key]
                return None
            entry.hits += 1
            return entry.value

    async def set(
        self,
        namespace: str,
        *parts: str,
        value: str,
        ttl: Optional[float] = None,
    ) -> None:
        """Store a value in cache."""
        key = self._make_key(namespace, *parts)
        async with self._lock:
            if len(self._store) >= self._max_size:
                self._evict()
            self._store[key] = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl or self._default_ttl,
            )

    async def invalidate(self, namespace: str, *parts: str) -> None:
        """Remove a specific entry."""
        key = self._make_key(namespace, *parts)
        async with self._lock:
            self._store.pop(key, None)

    async def invalidate_namespace(self, namespace: str) -> int:
        """Remove all entries in a namespace. Returns count of removed entries."""
        prefix = hashlib.md5(f"{namespace}:".encode()).hexdigest()[:8]
        async with self._lock:
            # Since keys are hashed, we need to track namespace separately
            # For now, clear everything (simple approach)
            count = len(self._store)
            self._store.clear()
            return count

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._store.clear()

    async def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        async with self._lock:
            total = len(self._store)
            expired = sum(1 for e in self._store.values() if e.is_expired)
            total_hits = sum(e.hits for e in self._store.values())
            return {
                "entries": total,
                "expired": expired,
                "total_hits": total_hits,
                "max_size": self._max_size,
            }

    def _evict(self) -> None:
        """Evict expired and least-used entries to make space."""
        # First remove expired
        expired_keys = [k for k, v in self._store.items() if v.is_expired]
        for k in expired_keys:
            del self._store[k]

        # If still over limit, remove least recently used (lowest hits)
        if len(self._store) >= self._max_size:
            sorted_entries = sorted(
                self._store.items(),
                key=lambda kv: (kv[1].hits, kv[1].created_at),
            )
            to_remove = len(self._store) - self._max_size + 1
            for k, _ in sorted_entries[:to_remove]:
                del self._store[k]


class SQLiteCache:
    """SQLite-backed persistent cache using aiosqlite.

    Falls back to MemoryCache if aiosqlite is not available.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        default_ttl: float = DEFAULT_TTL,
    ):
        self._db_path = str(db_path)
        self._default_ttl = default_ttl
        self._db: Any = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Open database and create tables."""
        try:
            import aiosqlite
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    ttl REAL NOT NULL,
                    hits INTEGER DEFAULT 0
                )
            """)
            await self._db.commit()
            logger.debug("SQLite cache initialized at %s", self._db_path)
        except ImportError:
            logger.warning("aiosqlite not available, cache disabled")
            self._db = None

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @staticmethod
    def _make_key(namespace: str, *parts: str) -> str:
        raw = f"{namespace}:" + ":".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()

    async def get(self, namespace: str, *parts: str) -> Optional[str]:
        if not self._db:
            return None
        key = self._make_key(namespace, *parts)
        async with self._lock:
            cursor = await self._db.execute(
                "SELECT value, created_at, ttl FROM cache WHERE key = ?",
                (key,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            value, created_at, ttl = row
            if time.time() - created_at > ttl:
                await self._db.execute("DELETE FROM cache WHERE key = ?", (key,))
                await self._db.commit()
                return None
            await self._db.execute(
                "UPDATE cache SET hits = hits + 1 WHERE key = ?", (key,)
            )
            await self._db.commit()
            return value

    async def set(
        self,
        namespace: str,
        *parts: str,
        value: str,
        ttl: Optional[float] = None,
    ) -> None:
        if not self._db:
            return
        key = self._make_key(namespace, *parts)
        async with self._lock:
            await self._db.execute(
                """INSERT OR REPLACE INTO cache (key, value, created_at, ttl, hits)
                   VALUES (?, ?, ?, ?, 0)""",
                (key, value, time.time(), ttl or self._default_ttl),
            )
            await self._db.commit()

    async def invalidate(self, namespace: str, *parts: str) -> None:
        if not self._db:
            return
        key = self._make_key(namespace, *parts)
        async with self._lock:
            await self._db.execute("DELETE FROM cache WHERE key = ?", (key,))
            await self._db.commit()

    async def clear(self) -> None:
        if not self._db:
            return
        async with self._lock:
            await self._db.execute("DELETE FROM cache")
            await self._db.commit()

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        if not self._db:
            return 0
        async with self._lock:
            cursor = await self._db.execute(
                "DELETE FROM cache WHERE (? - created_at) > ttl",
                (time.time(),),
            )
            await self._db.commit()
            return cursor.rowcount or 0
