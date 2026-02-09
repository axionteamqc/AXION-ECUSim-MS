"""Startup validation for DBC layout and control config."""

from __future__ import annotations

import logging
from typing import Iterable

from ecusim_ms import dbc_loader
from ecusim_ms.ms_signals import MS_SIGNAL_LIST

VALID_MODES = {"loop", "koeo", "idle", "pull", "custom", "silent"}


def _warn_unknown_keys(name: str, provided: Iterable[str], allowed: Iterable[str]) -> None:
    allowed_set = set(allowed)
    unknown = [k for k in provided if k not in allowed_set]
    if unknown:
        logging.warning("%s contains unknown keys: %s", name, unknown)


def validate_startup(db, control_cfg) -> str:
    """Validate DBC layout and control config; returns possibly adjusted mode."""
    dbc_loader.assert_expected_layout(db)
    dbc_loader.extract_signal_info(db)  # ensure DBC is parsable

    # check signals exist
    present = {sig.name for msg in db.messages for sig in msg.signals}
    missing = [k for k in MS_SIGNAL_LIST if k not in present]
    if missing:
        raise RuntimeError(f"DBC missing expected signals: {missing}")

    mode = (control_cfg.mode or "loop").lower()
    if mode not in VALID_MODES:
        logging.warning("Invalid mode %r; falling back to loop", mode)
        mode = "loop"

    # warn on unknown top-level keys
    if hasattr(control_cfg, "__dict__"):
        _warn_unknown_keys(
            "control.json",
            control_cfg.__dict__.keys(),
            [
                "profile_id",
                "backend",
                "iface",
                "channel",
                "port",
                "serial_baud",
                "skip_bitrate",
                "bitrate",
                "hz",
                "mode",
                "custom",
                "hard_test",
            ],
        )

    return mode
