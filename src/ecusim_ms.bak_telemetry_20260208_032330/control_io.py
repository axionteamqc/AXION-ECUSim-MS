"""Loading and saving control/telemetry files with safe defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ecusim_ms import models
from ecusim_ms.ms_signals import MS_SIGNAL_LIST


def _coerce_str(value: Any, default: str) -> str:
    if isinstance(value, str) and value:
        return value
    return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        val = value.strip().lower()
        if val in {"1", "true", "yes", "y", "on"}:
            return True
        if val in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return data


def _merge_custom(raw_custom: Any) -> Dict[str, float]:
    result: Dict[str, float] = dict(models.DEFAULT_SIGNAL_VALUES)
    if isinstance(raw_custom, dict):
        for key in MS_SIGNAL_LIST:
            result[key] = _coerce_float(raw_custom.get(key), result[key])
    return result


def _build_hard_test(raw_hard: Any) -> models.HardTestConfig:
    if isinstance(raw_hard, dict):
        return models.HardTestConfig(
            note=_coerce_str(raw_hard.get("note"), ""),
            data={k: v for k, v in raw_hard.items() if k != "note"},
        )
    return models.HardTestConfig()


def _build_control(data: Dict[str, Any]) -> models.ControlConfig:
    defaults = models.ControlConfig()
    return models.ControlConfig(
        profile_id=_coerce_str(data.get("profile_id"), defaults.profile_id),
        backend=_coerce_str(data.get("backend"), defaults.backend),
        iface=_coerce_str(data.get("iface"), defaults.iface),
        channel=_coerce_int(data.get("channel"), defaults.channel),
        port=_coerce_str(data.get("port"), defaults.port),
        serial_baud=_coerce_int(data.get("serial_baud"), defaults.serial_baud),
        skip_bitrate=_coerce_bool(data.get("skip_bitrate"), defaults.skip_bitrate),
        bitrate=_coerce_int(data.get("bitrate"), defaults.bitrate),
        hz=_coerce_float(data.get("hz"), defaults.hz),
        mode=_coerce_str(data.get("mode"), defaults.mode),
        custom=_merge_custom(data.get("custom")),
        hard_test=_build_hard_test(data.get("hard_test")),
    )


def load_control(path: Path | str) -> models.ControlConfig:
    """Load control.json with defaults for missing/invalid fields; never crash."""
    try:
        data = _load_json(Path(path))
        return _build_control(data)
    except Exception:
        return models.ControlConfig()


def load_control_safe(path: Path | str) -> models.ControlConfig:
    """Wrapper around load_control with defensive fallback."""
    try:
        control_path = Path(path)
        # size guard
        try:
            if control_path.exists() and control_path.stat().st_size > 256 * 1024:
                print(f"control.json too large (>256KB), ignoring: {control_path}")
                return models.ControlConfig()
        except Exception:
            return models.ControlConfig()

        return load_control(control_path)
    except Exception:
        return models.ControlConfig()


def read_control_overrides(control_cfg: models.ControlConfig) -> Dict[str, float]:
    """Return the 20-signal override map with defaults for any missing entries."""
    overrides: Dict[str, float] = {}
    for key in MS_SIGNAL_LIST:
        overrides[key] = _coerce_float(
            control_cfg.custom.get(key) if control_cfg and control_cfg.custom else None,
            models.DEFAULT_SIGNAL_VALUES[key],
        )
    return overrides


def save_telemetry_safe(path: Path | str, snapshot: Any) -> None:
    """Persist telemetry without raising; best-effort only."""
    try:
        target = Path(path)
        payload: Dict[str, Any]

        if isinstance(snapshot, models.TelemetrySnapshot):
            payload = snapshot.to_dict()
        elif isinstance(snapshot, dict):
            payload = snapshot
        else:
            payload = {}

        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception:
        return
