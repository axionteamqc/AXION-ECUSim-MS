"""Safe encoding helpers for MegaSquirt simplified dash messages."""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, Tuple

from cantools.database import Message, Signal

_warned_keys: set[Tuple[str, str]] = set()
_encode_error_stats: Dict[str, Dict[str, float]] = {}
_encode_error_total = 0


def raw_limits(sig: Signal) -> Tuple[int, int]:
    """Return raw integer limits based on signal length and signedness."""
    bits = sig.length
    if sig.is_signed:
        lo = -(1 << (bits - 1))
        hi = (1 << (bits - 1)) - 1
    else:
        lo = 0
        hi = (1 << bits) - 1
    return lo, hi


def to_raw(sig: Signal, phys: float) -> int:
    """Convert physical value to raw integer (unclamped)."""
    return round((phys - sig.offset) / sig.scale)


def to_phys(sig: Signal, raw: int) -> float:
    """Convert raw integer back to physical value."""
    return raw * sig.scale + sig.offset


def _log_encode_error(msg: Message, exc: Exception) -> None:
    global _encode_error_total
    _encode_error_total += 1
    stats = _encode_error_stats.setdefault(msg.name, {"count": 0, "last_summary": 0.0})
    stats["count"] += 1
    count = int(stats["count"])
    now = time.time()
    if count <= 3:
        logging.error("Encoding failed for %s: %s", msg.name, exc)
        return
    if now - stats["last_summary"] >= 1.0:
        logging.error("Encoding failures for %s: count=%d latest=%s", msg.name, count, exc)
        stats["last_summary"] = now


def _warn_clamp_once(msg: Message, sig: Signal, requested: Any, sent: Any) -> None:
    key = (msg.name, sig.name)
    if key in _warned_keys:
        return
    _warned_keys.add(key)
    logging.warning(
        "Clamp applied for %s.%s: requested=%s sent=%s",
        msg.name,
        sig.name,
        requested,
        sent,
    )


def _clamp_raw(sig: Signal, raw_val: int) -> Tuple[int, bool]:
    lo, hi = raw_limits(sig)
    if raw_val < lo:
        return lo, True
    if raw_val > hi:
        return hi, True
    return raw_val, False


def encode_message_safe(
    msg: Message, desired_phys: Dict[str, Any]
) -> Tuple[bytes, Dict[str, float], Dict[str, Dict[str, Any]]]:
    """Encode a message with clamping to prevent cantools errors.

    Returns: (payload_bytes, used_phys, clamped_info)
    - used_phys: the physical values corresponding to the clamped raw.
    - clamped_info: entries for signals that were clamped with requested/sent.
    """
    used_phys: Dict[str, float] = {}
    clamped: Dict[str, Dict[str, Any]] = {}

    for sig in msg.signals:
        requested = desired_phys.get(sig.name, 0)
        try:
            phys_val = float(requested)
        except Exception:
            logging.warning(
                "Non-numeric value for %s.%s: %r (using 0.0)", msg.name, sig.name, requested
            )
            phys_val = 0.0

        if not math.isfinite(phys_val):
            logging.error(
                "Non-finite value before encoding for %s.%s: %s (using 0.0)",
                msg.name,
                sig.name,
                requested,
            )
            phys_val = 0.0

        try:
            raw = to_raw(sig, phys_val)
        except Exception:
            raw = 0

        raw_clamped, was_clamped = _clamp_raw(sig, raw)
        phys_used = to_phys(sig, raw_clamped)

        used_phys[sig.name] = phys_used
        if was_clamped:
            clamped[sig.name] = {"requested": requested, "sent": phys_used}
            _warn_clamp_once(msg, sig, requested, phys_used)

    try:
        payload = msg.encode(used_phys)
    except Exception as exc:
        _log_encode_error(msg, exc)
        raise
    return payload, used_phys, clamped


def reset_encode_error_stats() -> None:
    """Reset encode error counters (for tests)."""
    global _encode_error_total
    _encode_error_stats.clear()
    _encode_error_total = 0


def get_encode_error_count() -> int:
    return int(_encode_error_total)
