"""Tiny in-memory counters, exposed on the /health endpoint."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Stats:
    started_at: float = field(default_factory=time.time)
    downloads_ok: int = 0
    downloads_failed: int = 0

    def record_success(self) -> None:
        self.downloads_ok += 1

    def record_failure(self) -> None:
        self.downloads_failed += 1

    def snapshot(self) -> dict:
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - self.started_at),
            "downloads_ok": self.downloads_ok,
            "downloads_failed": self.downloads_failed,
        }


stats = Stats()
