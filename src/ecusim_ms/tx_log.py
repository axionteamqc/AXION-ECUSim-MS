"""TX logging helper (CSV) for reproducible debug."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict


class TxLogger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists() or self.path.stat().st_size == 0
        self._file = self.path.open("a", encoding="utf-8", newline="")
        self._writer = csv.writer(self._file)
        if is_new:
            self._writer.writerow(["ts", "id", "dlc", "data_hex", "used_json"])

    def write_line(
        self, ts: float, frame_id: int, dlc: int, payload_hex: str, used_subset: Dict[str, float]
    ) -> None:
        try:
            used_json = json.dumps(used_subset, separators=(",", ":"))
            self._writer.writerow([f"{ts:.3f}", hex(frame_id), dlc, payload_hex, used_json])
            self._file.flush()
        except Exception:
            return

    def close(self) -> None:
        try:
            self._file.close()
        except Exception:
            return
