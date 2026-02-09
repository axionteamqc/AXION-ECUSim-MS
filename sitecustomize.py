"""Ensure src/ is on sys.path for local CLI use without installation."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent / "src"

if SRC_PATH.exists():
    sys.path.insert(0, str(SRC_PATH))
