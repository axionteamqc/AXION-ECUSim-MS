"""Telemetry writer with fixed-rate, best-effort persistence."""

from __future__ import annotations

import time
from typing import Any

from ecusim_ms.control_io import save_telemetry_safe


class TelemetryWriter:
    def __init__(self, path, hz: float = 5.0) -> None:
        if hz <= 0:
            raise ValueError("hz must be positive")
        self.path = path
        self.hz = hz
        self.dt = 1.0 / hz
        self._next = time.monotonic()

    def maybe_write(self, snapshot: Any) -> None:
        """Persist telemetry at the configured rate; never raise."""
        try:
            now = time.monotonic()
            if now < self._next:
                return

            # align next write slot
            while self._next <= now:
                self._next += self.dt

            save_telemetry_safe(self.path, snapshot)
        except Exception:
            return
