"""DBC loader for the MegaSquirt Simplified Dash broadcast frames."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Dict, Tuple

import cantools
from cantools.database import Database, Message

from ecusim_ms import paths

EXPECTED_IDS = {1512, 1513, 1514, 1515, 1516}
EXPECTED_NAMES = {
    1512: "megasquirt_dash0",
    1513: "megasquirt_dash1",
    1514: "megasquirt_dash2",
    1515: "megasquirt_dash3",
    1516: "megasquirt_dash4",
}
EXPECTED_DLC = 8

# expected signals per frame_id (sets)
EXPECTED_SIGNALS = {
    1512: {"map", "rpm", "clt", "tps"},
    1513: {"pw1", "pw2", "mat", "adv_deg"},
    1514: {"AFR1", "afrtgt1", "egocor1", "egt1", "pwseq1"},
    1515: {"batt", "sensors1", "sensors2", "knk_rtd"},
    1516: {"VSS1", "tc_retard", "launch_timing"},
}
# expected signal metadata per frame_id
EXPECTED_SIGNAL_META = {
    1512: {
        "map": {
            "start": 7,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
        "rpm": {
            "start": 23,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": False,
            "scale": 1,
            "offset": 0,
        },
        "clt": {
            "start": 39,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
        "tps": {
            "start": 55,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
    },
    1513: {
        "pw1": {
            "start": 7,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": False,
            "scale": 0.001,
            "offset": 0,
        },
        "pw2": {
            "start": 23,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": False,
            "scale": 0.001,
            "offset": 0,
        },
        "mat": {
            "start": 39,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
        "adv_deg": {
            "start": 55,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
    },
    1514: {
        "AFR1": {
            "start": 15,
            "length": 8,
            "byte_order": "big_endian",
            "is_signed": False,
            "scale": 0.1,
            "offset": 0,
        },
        "afrtgt1": {
            "start": 7,
            "length": 8,
            "byte_order": "big_endian",
            "is_signed": False,
            "scale": 0.1,
            "offset": 0,
        },
        "egocor1": {
            "start": 23,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
        "egt1": {
            "start": 39,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
        "pwseq1": {
            "start": 55,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.001,
            "offset": 0,
        },
    },
    1515: {
        "batt": {
            "start": 7,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
        "sensors1": {
            "start": 23,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.01,
            "offset": 0,
        },
        "sensors2": {
            "start": 39,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.01,
            "offset": 0,
        },
        "knk_rtd": {
            "start": 55,
            "length": 8,
            "byte_order": "big_endian",
            "is_signed": False,
            "scale": 0.1,
            "offset": 0,
        },
    },
    1516: {
        "VSS1": {
            "start": 7,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": False,
            "scale": 0.1,
            "offset": 0,
        },
        "tc_retard": {
            "start": 23,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
        "launch_timing": {
            "start": 39,
            "length": 16,
            "byte_order": "big_endian",
            "is_signed": True,
            "scale": 0.1,
            "offset": 0,
        },
    },
}
DBC_SHA256 = "791E994238CF0E79F6A100E9550E32F3B3399C8ABF8B4FF22A36E90FFD6DC693"


def verify_hash(path: Path, enforce: bool = False) -> None:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        h.update(handle.read())
    digest = h.hexdigest().upper()
    if digest != DBC_SHA256:
        msg = f"DBC hash mismatch: {digest} (expected {DBC_SHA256})"
        if enforce:
            raise RuntimeError(msg)
        logging.warning(msg)


def load_db(dbc_path: Path | str | None = None, enforce_hash: bool = True) -> Database:
    """Load the MegaSquirt Simplified Dash DBC from assets/dbc."""
    path = Path(dbc_path) if dbc_path else paths.dbc_path()
    if not path.exists():
        raise RuntimeError(f"DBC file not found at {path}")
    verify_hash(path, enforce=enforce_hash)
    db = cantools.database.load_file(path, strict=True)
    assert_expected_layout(db)
    return db


def build_message_map(db: Database) -> Tuple[Dict[str, Message], Dict[int, Message]]:
    """Return message maps by name and by frame_id."""
    by_name = {msg.name: msg for msg in db.messages}
    by_id = {msg.frame_id: msg for msg in db.messages}
    return by_name, by_id


def extract_signal_info(db: Database) -> Dict[str, Dict[str, object]]:
    """Return metadata for signals: owning message, frame_id, unit, scale, offset."""
    info: Dict[str, Dict[str, object]] = {}
    for msg in db.messages:
        for sig in msg.signals:
            info[sig.name] = {
                "message": msg.name,
                "frame_id": msg.frame_id,
                "unit": sig.unit,
                "scale": sig.scale,
                "offset": sig.offset,
                "start": sig.start,
                "length": sig.length,
            }
    return info


def assert_expected_layout(db: Database) -> None:
    """Validate the DBC matches the simplified dash broadcast layout."""
    ids = {msg.frame_id for msg in db.messages}
    if ids != EXPECTED_IDS:
        raise RuntimeError(
            f"Unexpected frame IDs: found {sorted(ids)}, expected {sorted(EXPECTED_IDS)}"
        )

    for msg in db.messages:
        dlc = getattr(msg, "dlc", None)
        if dlc is None:
            dlc = getattr(msg, "length", None)
        if dlc != EXPECTED_DLC:
            raise RuntimeError(f"Unexpected DLC for {msg.name}: {dlc} (expected {EXPECTED_DLC})")
        expected_name = EXPECTED_NAMES.get(msg.frame_id)
        if msg.name != expected_name:
            raise RuntimeError(
                f"Unexpected name for frame {msg.frame_id}: {msg.name!r} (expected {expected_name!r})"
            )
        expected_signals = EXPECTED_SIGNALS.get(msg.frame_id, set())
        found = {sig.name for sig in msg.signals}
        if expected_signals and found != expected_signals:
            raise RuntimeError(
                f"Unexpected signals for frame {msg.frame_id} ({msg.name}): found {sorted(found)}, expected {sorted(expected_signals)}"
            )

        # bit-level validation
        expected_meta = EXPECTED_SIGNAL_META.get(msg.frame_id, {})
        for sig in msg.signals:
            exp = expected_meta.get(sig.name)
            if not exp:
                continue
            diff = []
            if sig.start != exp["start"]:
                diff.append(f"start {sig.start} != {exp['start']}")
            if sig.length != exp["length"]:
                diff.append(f"len {sig.length} != {exp['length']}")
            byte_order = getattr(sig, "byte_order", "big_endian")
            if byte_order != exp["byte_order"]:
                diff.append(f"byte_order {byte_order} != {exp['byte_order']}")
            if sig.is_signed != exp["is_signed"]:
                diff.append(f"signed {sig.is_signed} != {exp['is_signed']}")
            if sig.scale != exp["scale"]:
                diff.append(f"scale {sig.scale} != {exp['scale']}")
            if sig.offset != exp["offset"]:
                diff.append(f"offset {sig.offset} != {exp['offset']}")
            if diff:
                raise RuntimeError(
                    f"Signal layout mismatch for {msg.name}.{sig.name}: {', '.join(diff)}"
                )
