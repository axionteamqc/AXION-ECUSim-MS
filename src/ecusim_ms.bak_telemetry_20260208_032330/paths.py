"""Helpers to locate project resources for both dev and frozen builds."""

from __future__ import annotations

import sys
from pathlib import Path


def _base_dir() -> Path:
    """Return the root directory for resolving assets and data.

    - In dev (non-frozen), this is the repo root (parent of ``src``).
    - In a frozen build, prefer the PyInstaller extraction dir (``_MEIPASS``),
      otherwise fall back to the executable's parent.
    """
    if getattr(sys, "frozen", False):  # PyInstaller or similar
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def project_root() -> Path:
    """Project root for the current execution context."""
    return _base_dir()


def data_dir() -> Path:
    """Directory holding control/telemetry JSON and stop flag."""
    return project_root() / "data"


def control_path() -> Path:
    """Path to control.json."""
    return data_dir() / "control.json"


def telemetry_path() -> Path:
    """Path to telemetry.json."""
    return data_dir() / "telemetry.json"


def can_monitor_path() -> Path:
    """Path to can_monitor.jsonl (structured CAN RX log)."""
    return data_dir() / "can_monitor.jsonl"


def stop_flag_path() -> Path:
    """Path to stop.flag file (used in dev/test loops)."""
    return data_dir() / "stop.flag"


def dbc_path() -> Path:
    """Path to the MegaSquirt Simplified Dash broadcast DBC."""
    return project_root() / "assets" / "dbc" / "Megasquirt_simplified_dash_broadcast.dbc"
