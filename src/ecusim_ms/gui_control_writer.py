"""Atomic writer for control.json used by the GUI with optional debouncing."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional


class Debouncer:
    """Simple thread-based debouncer to coalesce rapid events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def schedule(self, delay_s: float, fn, *args, **kwargs) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
            timer = threading.Timer(delay_s, self._run, args=(fn, args, kwargs))
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _run(self, fn, args, kwargs) -> None:
        try:
            fn(*args, **kwargs)
        finally:
            with self._lock:
                self._timer = None

    def cancel(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None


class ControlWriter:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._debouncer = Debouncer()

    def write(self, control_dict: Dict[str, Any]) -> None:
        """Write control data atomically to avoid partial reads."""
        try:
            target = self.path
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = target.with_suffix(target.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(control_dict, handle, indent=2)
            tmp_path.replace(target)
        except Exception:
            return

    def write_debounced(self, control_dict: Dict[str, Any], delay_ms: int = 200) -> None:
        """Coalesce rapid writes; only the latest payload after delay is written."""
        try:
            payload = dict(control_dict)
        except Exception:
            payload = control_dict
        self._debouncer.schedule(delay_ms / 1000.0, self.write, payload)
