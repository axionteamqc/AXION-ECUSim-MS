"""Message builder for MegaSquirt simplified dash broadcast frames."""

from __future__ import annotations

from typing import Dict, List, Tuple

from cantools.database import Database, Message

from ecusim_ms.dbc_codec import encode_message_safe

# Mapping of message name to its signal list (case-sensitive, matches DBC).
MESSAGE_SIGNALS = {
    "megasquirt_dash0": ["map", "rpm", "clt", "tps"],
    "megasquirt_dash1": ["pw1", "pw2", "mat", "adv_deg"],
    "megasquirt_dash2": ["AFR1", "afrtgt1", "egocor1", "egt1", "pwseq1"],
    "megasquirt_dash3": ["batt", "sensors1", "sensors2", "knk_rtd"],
    "megasquirt_dash4": ["VSS1", "tc_retard", "launch_timing"],
}


def _get_message(db: Database, name: str) -> Message:
    msg = db.get_message_by_name(name)
    if msg is None:
        raise RuntimeError(f"DBC missing expected message {name}")
    return msg


def init_messages(db: Database) -> Dict[str, Message]:
    """Return a mapping of message name to cantools Message, validating presence."""
    return {name: _get_message(db, name) for name in MESSAGE_SIGNALS.keys()}


def build_frames(
    msg_map: Dict[str, Message], signals_phys: Dict[str, float]
) -> List[Tuple[int, bytes, bool, Dict[str, float], Dict[str, Dict[str, object]]]]:
    """Build encoded frames for all dash messages.

    Returns a list of tuples: (frame_id, payload, is_extended, used_phys, clamped_info).
    Each signal from the 20-signal set is covered in exactly one message.
    """
    frames = []
    for name, sig_list in MESSAGE_SIGNALS.items():
        msg = msg_map.get(name)
        if msg is None:
            raise RuntimeError(f"Message {name} not loaded")
        desired = {sig: signals_phys.get(sig, 0.0) for sig in sig_list}
        payload, used, clamped = encode_message_safe(msg, desired)
        frames.append((msg.frame_id, payload, msg.is_extended_frame, used, clamped))
    return frames
