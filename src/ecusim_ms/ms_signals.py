"""Canonical MegaSquirt simplified dash message and signal lists."""

from __future__ import annotations

from typing import Set

MS_MESSAGES = [
    "megasquirt_dash0",
    "megasquirt_dash1",
    "megasquirt_dash2",
    "megasquirt_dash3",
    "megasquirt_dash4",
]

# Order must stay stable for UI/control/telemetry consumers; keys must match DBC signal names.
# Order must stay stable for UI/control/telemetry consumers; keys must match DBC signal names.
MS_SIGNAL_LIST = [
    "map",
    "rpm",
    "clt",
    "tps",
    "pw1",
    "pw2",
    "mat",
    "adv_deg",
    "afrtgt1",
    "AFR1",
    "egocor1",
    "egt1",
    "pwseq1",
    "batt",
    "sensors1",
    "sensors2",
    "knk_rtd",
    "VSS1",
    "tc_retard",
    "launch_timing",
]

MS_SIGNAL_SET: Set[str] = set(MS_SIGNAL_LIST)
MS_MESSAGE_SET: Set[str] = set(MS_MESSAGES)


def assert_ms_signals_in_dbc(db) -> None:
    """Validate that the required messages/signals exist in the provided DBC.

    Raises RuntimeError with a clear list of missing entries.
    """
    missing_msgs = [name for name in MS_MESSAGES if not _has_message(db, name)]
    if missing_msgs:
        raise RuntimeError(f"DBC missing expected messages: {missing_msgs}")

    present_signals = _all_signal_names(db)
    missing_sigs = [name for name in MS_SIGNAL_LIST if name not in present_signals]
    if missing_sigs:
        raise RuntimeError(f"DBC missing expected signals: {missing_sigs}")


def _has_message(db, name: str) -> bool:
    try:
        return db.get_message_by_name(name) is not None
    except Exception:
        return False


def _all_signal_names(db) -> Set[str]:
    names: Set[str] = set()
    try:
        for msg in db.messages:
            for sig in msg.signals:
                names.add(sig.name)
    except Exception:
        return set()
    return names
