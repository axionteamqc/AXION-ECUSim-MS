"""Telemetry reader with mtime cache for GUI polling."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class TelemetryReader:
    def __init__(self, path: Path | str, poll_hz: float = 5.0):
        self.path = Path(path)
        self.dt = 1.0 / poll_hz if poll_hz > 0 else 0.2
        self._next = time.monotonic()
        self._last_mtime: Optional[float] = None
        self._cache: Dict[str, Any] = {}

    def poll(self) -> Dict[str, Any]:
        """Return telemetry dict if changed; otherwise empty dict."""
        now = time.monotonic()
        if now < self._next:
            return {}
        self._next = now + self.dt

        try:
            if not self.path.exists():
                return {}
            mtime = self.path.stat().st_mtime
            if self._last_mtime is not None and mtime == self._last_mtime:
                return {}
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._cache = data
                self._last_mtime = mtime
                return data
        except Exception:
            return {}
        return {}
