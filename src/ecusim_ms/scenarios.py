"""Scenario generators for the MegaSquirt simplified dash signals (DBC-aligned).

Outputs are in DBC units (temperatures in deg F, VSS1 in m/s)."""

from __future__ import annotations

import logging
import math
from typing import Dict

from ecusim_ms.ms_signals import MS_SIGNAL_LIST

MAP_MIN = 10.0
MAP_MAX = 260.0
MAP_FALLBACK = 100.0


def _base_signals() -> Dict[str, float]:
    """Return a dict with all signals initialized to 0.0 in canonical order."""
    return {name: 0.0 for name in MS_SIGNAL_LIST}


def _sanitize_map(val: float, ctx: str) -> float:
    """Clamp MAP to realistic bounds and warn on non-finite inputs."""
    if not math.isfinite(val):
        logging.warning("MAP non-finite in %s: %r -> %.1f kPa", ctx, val, MAP_FALLBACK)
        val = MAP_FALLBACK
    clamped = max(MAP_MIN, min(MAP_MAX, val))
    if clamped != val:
        logging.debug("MAP clamped in %s: %.1f -> %.1f kPa", ctx, val, clamped)
    return clamped


def _ordered(signals: Dict[str, float], ctx: str) -> Dict[str, float]:
    """Apply overrides while preserving MS_SIGNAL_LIST order and finite values."""
    out = _base_signals()
    for k, v in signals.items():
        try:
            val = float(v)
        except Exception:
            val = 0.0
        if k == "map":
            val = _sanitize_map(val, ctx)
        elif math.isnan(val) or math.isinf(val):
            val = 0.0
        if k in out:
            out[k] = val
    return out


def enforce_map_bounds(signals: Dict[str, float], ctx: str = "runtime") -> float:
    """Ensure signals['map'] exists, is finite, and clamped; returns sanitized value."""
    raw = signals.get("map", MAP_FALLBACK)
    try:
        val = float(raw)
    except Exception:
        logging.warning("MAP non-numeric in %s: %r -> %.1f kPa", ctx, raw, MAP_FALLBACK)
        val = MAP_FALLBACK
    sanitized = _sanitize_map(val, ctx)
    signals["map"] = sanitized
    return sanitized


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def scenario_koeo() -> Dict[str, float]:
    signals = {
        "map": 100.0,
        "rpm": 0.0,
        "clt": 70.0,
        "tps": 0.5,
        "pw1": 0.0,
        "pw2": 0.0,
        "mat": 70.0,
        "adv_deg": 0.0,
        "afrtgt1": 14.7,
        "AFR1": 14.7,
        "egocor1": 100.0,
        "egt1": 200.0,
        "pwseq1": 0.0,
        "batt": 12.2,
        "sensors1": 0.0,
        "sensors2": 0.0,
        "knk_rtd": 0.0,
        "VSS1": 0.0,
        "tc_retard": 0.0,
        "launch_timing": 0.0,
    }
    return _ordered(signals, "scenario_koeo")


def scenario_idle(t: float) -> Dict[str, float]:
    s_rpm = math.sin(2 * math.pi * 0.5 * t)
    s_tps = math.sin(2 * math.pi * 0.2 * t)
    s_map = math.sin(2 * math.pi * 0.3 * t)
    s_batt = math.sin(2 * math.pi * 0.1 * t)
    s_adv = math.sin(2 * math.pi * 0.25 * t)
    s_pw = math.sin(2 * math.pi * 0.4 * t)
    s_clt = math.sin(2 * math.pi * 0.03 * t)
    s_mat = math.sin(2 * math.pi * 0.05 * t)
    s_egt = math.sin(2 * math.pi * 0.2 * t)
    s_knk = math.sin(2 * math.pi * 0.15 * t)

    signals = {
        "map": 100.0 + 1.0 * s_map,  # keep near baro for demo
        "rpm": 900.0 + 40.0 * s_rpm,
        "clt": 185.0 + 2.0 * s_clt,  # deg F
        "tps": 1.5 + 0.2 * s_tps,
        "pw1": 2.5 + 0.15 * s_pw,
        "pw2": 2.5 + 0.15 * s_pw,
        "mat": 86.0 + 1.0 * s_mat,  # deg F
        "adv_deg": 12.0 + 2.0 * s_adv,
        "afrtgt1": 14.7,
        "AFR1": 14.7,
        "egocor1": 100.0,
        "egt1": 500.0 + 30.0 * s_egt,  # deg F
        "pwseq1": 2.5 + 0.15 * s_pw,
        "batt": 14.0 - 0.05 * s_batt,
        "sensors1": 280.0 + 10.0 * s_map,
        "sensors2": 90.0 + 2.0 * s_mat,
        "knk_rtd": max(0.0, 0.5 * s_knk),
        "VSS1": 0.0,
        "tc_retard": 0.0,
        "launch_timing": 0.0,
    }
    return _ordered(signals, "scenario_idle")


def scenario_pull(t: float) -> Dict[str, float]:
    ramp = _clamp(t / 5.0, 0.0, 1.0)
    afr1 = 14.7 - 2.2 * ramp
    signals = {
        "map": 100.0 + 10.0 * ramp,  # ~0-10 kPa above baro for demo
        "rpm": 1000.0 + 7000.0 * ramp,
        "clt": 185.0 + 5.0 * ramp,
        "tps": 2.0 + 93.0 * ramp,
        "pw1": 3.0 + 8.0 * ramp,
        "pw2": 3.0 + 8.0 * ramp,
        "mat": 86.0 + 10.0 * ramp,
        "adv_deg": 12.0 - 6.0 * ramp,
        "afrtgt1": afr1,
        "AFR1": afr1,
        "egocor1": 100.0,
        "egt1": 520.0 + 650.0 * ramp,  # deg F
        "pwseq1": 3.0 + 8.0 * ramp,
        "batt": 14.0 - 0.2 * ramp,
        "sensors1": 300.0 + 220.0 * ramp,
        "sensors2": 95.0 + 15.0 * ramp,
        "knk_rtd": 0.0,
        "VSS1": 35.0 * ramp,  # m/s
        "tc_retard": 0.0,
        "launch_timing": 0.0,
    }
    return _ordered(signals, "scenario_pull")


def scenario_loop(t: float) -> Dict[str, float]:
    t15 = t % 15.0
    if t15 < 5.0:
        return scenario_koeo()
    if 5.0 <= t15 < 10.0:
        return scenario_idle(t15 - 5.0)
    return scenario_pull(t15 - 10.0)


def scenario_values(mode: str, t: float) -> Dict[str, float]:
    mode_l = (mode or "").lower()
    if mode_l == "loop":
        return scenario_loop(t)
    if mode_l == "koeo":
        return scenario_koeo()
    if mode_l == "idle":
        return scenario_idle(t)
    if mode_l == "pull":
        return scenario_pull(t)
    if mode_l == "custom":
        return scenario_idle(t)
    if mode_l == "silent":
        return scenario_loop(t)
    # default fallback
    return scenario_idle(t)
