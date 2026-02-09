"""Background CAN monitor to log RX (including error frames if available)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

from ecusim_ms.can_bus import CanBus


class CanMonitor:
    def __init__(self, bus: CanBus, log_path: Path, max_events_per_sec: int = 50) -> None:
        self.bus = bus
        self.log_path = log_path
        self.max_events_per_sec = max_events_per_sec
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._file = None
        self._last_bucket = 0
        self._bucket_count = 0

    def start(self) -> None:
        if self._thread is not None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.log_path.open("a", encoding="utf-8")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._file:
            try:
                self._file.close()
            except Exception:
                pass
        self._thread = None
        self._file = None

    def _emit(self, evt: dict) -> None:
        if not self._file:
            return
        evt = dict(evt)
        evt.setdefault("ts", time.time())
        try:
            self._file.write(json.dumps(evt, separators=(",", ":")) + "\n")
            self._file.flush()
        except Exception:
            pass

    def _run(self) -> None:
        while not self._stop_evt.is_set():
            msg = self.bus.recv(timeout_s=0.05)
            if msg is None:
                continue
            now = time.time()
            bucket = int(now * 10)  # 100ms buckets
            if bucket != self._last_bucket:
                self._last_bucket = bucket
                self._bucket_count = 0
            self._bucket_count += 1
            is_error = getattr(msg, "is_error_frame", False)
            if not is_error and self._bucket_count > self.max_events_per_sec / 10:
                continue
            evt = {
                "type": "rx",
                "id": msg.arbitration_id,
                "dlc": getattr(msg, "dlc", len(msg.data)),
                "data_hex": msg.data.hex(),
                "is_error": bool(is_error),
                "is_rtr": bool(getattr(msg, "is_remote_frame", False)),
            }
            self._emit(evt)
