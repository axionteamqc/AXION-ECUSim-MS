"""Helpers for stop.flag lifecycle."""

from __future__ import annotations

from pathlib import Path


def ensure_not_set(stop_path: Path) -> None:
    try:
        if stop_path.exists():
            stop_path.unlink()
    except Exception:
        return


def is_set(stop_path: Path) -> bool:
    try:
        return stop_path.exists()
    except Exception:
        return False


def request_stop(stop_path: Path) -> None:
    try:
        stop_path.parent.mkdir(parents=True, exist_ok=True)
        stop_path.touch()
    except Exception:
        return
