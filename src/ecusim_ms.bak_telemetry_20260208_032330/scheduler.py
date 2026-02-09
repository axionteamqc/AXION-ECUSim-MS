"""Fixed-rate scheduler using a monotonic clock."""

from __future__ import annotations

import time
from typing import Optional


class FixedRateScheduler:
    def __init__(self, hz: float) -> None:
        if hz <= 0:
            raise ValueError("hz must be positive")
        self.hz = hz
        self.dt = 1.0 / hz
        self._start: Optional[float] = None
        self._next: Optional[float] = None

    def start(self) -> None:
        now = time.monotonic()
        self._start = now
        self._next = now + self.dt

    def wait_next(self) -> float:
        if self._start is None or self._next is None:
            self.start()

        while True:
            now = time.monotonic()
            sleep_time = self._next - now
            if sleep_time > 0:
                time.sleep(sleep_time)
                now = time.monotonic()
            else:
                # late: do not sleep; realign next tick to current time
                self._next = now
            # schedule next tick
            self._next += self.dt
            return now - (self._start or now)
