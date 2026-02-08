"""Partial overrides for custom control signals (20-signal set)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass
class ControlCache:
    mtime: Optional[float] = None
    payload: Dict[str, object] = field(default_factory=dict)


_CACHE = ControlCache()


def _load_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _select_custom_block(data: Dict[str, object]) -> Dict[str, object]:
    custom = data.get("custom")
    if isinstance(custom, dict):
        return custom
    return data


def read_overrides(control_path: Path | str, allowed_keys: Iterable[str]) -> Dict[str, float]:
    """Return partial overrides from control.json (custom block or root).

    Best-effort:
    - Returns {} if file missing or unreadable.
    - Uses mtime cache to avoid reloading when unchanged.
    - Filters to allowed_keys and numeric (float-castable) values only.
    """
    try:
        path = Path(control_path)
        if not path.exists():
            return {}

        mtime = path.stat().st_mtime
        if _CACHE.mtime != mtime:
            try:
                _CACHE.payload = _load_json(path)
                _CACHE.mtime = mtime
            except Exception:
                _CACHE.payload = {}
                _CACHE.mtime = mtime

        data = _CACHE.payload if isinstance(_CACHE.payload, dict) else {}
        src = _select_custom_block(data)

        overrides: Dict[str, float] = {}
        allowed_set = set(allowed_keys)
        if isinstance(src, dict):
            for k, v in src.items():
                if k not in allowed_set:
                    continue
                try:
                    overrides[k] = float(v)
                except Exception:
                    continue
        return overrides
    except Exception:
        return {}
