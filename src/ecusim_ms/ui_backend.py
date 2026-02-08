"""UI backend API for mobile/desktop views (no CAN logic in UI)."""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ecusim_ms import dbc_loader, models, paths, validate
from ecusim_ms.control_io import load_control_safe
from ecusim_ms.gui_control_writer import ControlWriter
from ecusim_ms.ms_signals import MS_SIGNAL_LIST
from ecusim_ms.runner_process import RunnerProcess
from ecusim_ms.stop_flag import ensure_not_set


@dataclass(frozen=True)
class SignalSchema:
    name: str
    frame_id: Optional[int]
    default_period_ms: float
    value_type: str
    unit: Optional[str]
    min_value: Optional[float]
    max_value: Optional[float]
    default_value: float


class UiBackend:
    """Backend API used by UI (no direct CAN send)."""

    def __init__(self) -> None:
        cfg = load_control_safe(paths.control_path())
        self._control_path = paths.control_path()
        self._telemetry_path = paths.telemetry_path()
        self._stop_path = paths.stop_flag_path()
        self._writer = ControlWriter(self._control_path)
        self._runner = RunnerProcess()

        self._backend = cfg.backend or "pythoncan"
        self._iface = cfg.iface or "gs_usb"
        self._channel = int(cfg.channel)
        self._port = cfg.port or ""
        self._serial_baud = int(cfg.serial_baud)
        self._skip_bitrate = bool(cfg.skip_bitrate)
        self._bitrate = int(cfg.bitrate)
        self._hz = float(cfg.hz)
        self._mode = cfg.mode or "idle"
        self._custom_values = dict(cfg.custom or models.DEFAULT_SIGNAL_VALUES)
        self._custom_enabled = {k: True for k in MS_SIGNAL_LIST}
        self._custom_period_ms = {
            k: (1000.0 / self._hz if self._hz else 0.0) for k in MS_SIGNAL_LIST
        }
        self._schemas = self._load_signal_schema()
        self._schema_by_name = {schema.name: schema for schema in self._schemas}
        self._last_error: Optional[str] = None
        self._warned_ranges: set[str] = set()
        self._apply_error_count = 0
        self._parse_error_count = 0
        self._telemetry_lock = threading.Lock()
        self._telemetry_snapshot: Dict[str, object] = {
            "timestamp_ms": 0,
            "running": False,
            "error_count_total": 0,
            "signals": [],
        }
        self._telemetry_last_error: Optional[str] = None
        self._telemetry_thread = threading.Thread(target=self._telemetry_poll_loop, daemon=True)
        self._telemetry_thread.start()

    def get_available_modes(self) -> list[str]:
        preferred = ["idle", "pull", "loop", "koeo", "custom", "silent"]
        modes = list(getattr(validate, "VALID_MODES", [])) or preferred
        ordered = [m for m in preferred if m in modes]
        for m in modes:
            if m not in ordered:
                ordered.append(m)
        return ordered

    def set_mode(self, mode: str) -> None:
        if mode not in self.get_available_modes():
            raise ValueError(f"Unsupported mode: {mode}")
        self._mode = mode
        self._write_control()

    def get_custom_signals_schema(self) -> list[SignalSchema]:
        return list(self._schemas)

    def get_custom_signals_schema_ui(self) -> list[dict]:
        payload: list[dict] = []
        for schema in self._schemas:
            min_v, max_v, step_v, default_v = self._normalize_range(schema)
            payload.append(
                {
                    "name": schema.name,
                    "key": schema.name,
                    "min": min_v,
                    "max": max_v,
                    "step": step_v,
                    "default": default_v,
                    "unit": schema.unit,
                    "frame_id": schema.frame_id,
                    "default_period_ms": schema.default_period_ms,
                }
            )
        return payload

    def apply_custom_payload(self, updates) -> Tuple[bool, Optional[str]]:
        items = self._normalize_updates(updates)
        if not items:
            self._apply_error_count += 1
            return False, "No updates provided"
        sanitized: Dict[str, dict] = {}
        for name, update in items.items():
            schema = self._schema_by_name.get(name)
            if schema is None:
                self._apply_error_count += 1
                return False, f"Unknown signal: {name}"
            if "value" not in update:
                self._apply_error_count += 1
                return False, f"Missing value for {name}"
            try:
                value = float(update.get("value"))
            except Exception:
                self._apply_error_count += 1
                return False, f"Invalid value for {name}"
            if not math.isfinite(value):
                self._apply_error_count += 1
                return False, f"Non-finite value for {name}"
            min_v, max_v, _, _ = self._normalize_range(schema)
            if value < min_v or value > max_v:
                self._apply_error_count += 1
                return False, f"Value out of range for {name} ({min_v}..{max_v})"
            enabled = update.get("enabled")
            period_ms = update.get("period_ms")
            if period_ms is not None:
                try:
                    period_ms = float(period_ms)
                except Exception:
                    self._apply_error_count += 1
                    return False, f"Invalid period for {name}"
                if period_ms <= 0:
                    self._apply_error_count += 1
                    return False, f"Invalid period for {name}"
            sanitized[name] = {
                "value": value,
                "enabled": bool(enabled) if enabled is not None else None,
                "period_ms": period_ms,
            }
        try:
            self.apply_custom_signal_updates(sanitized)
        except Exception as exc:
            self._last_error = str(exc)
            self._apply_error_count += 1
            return False, str(exc)
        return True, None

    def apply_custom_signal_updates(self, updates) -> None:
        items = self._normalize_updates(updates)
        for name, update in items.items():
            if name not in MS_SIGNAL_LIST:
                continue
            if "enabled" in update and update["enabled"] is not None:
                self._custom_enabled[name] = bool(update["enabled"])
            if "period_ms" in update and update["period_ms"] is not None:
                try:
                    self._custom_period_ms[name] = float(update["period_ms"])
                except Exception:
                    pass
            if "value" in update and update["value"] is not None:
                try:
                    self._custom_values[name] = float(update["value"])
                except Exception:
                    pass
        self._write_control()

    def start(self) -> None:
        ensure_not_set(self._stop_path)
        self._write_control()
        try:
            self._runner.start(
                control_path=self._control_path,
                telemetry_path=self._telemetry_path,
                stop_path=self._stop_path,
                extra_args=[],
            )
            self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            raise

    def stop(self) -> None:
        try:
            self._runner.stop()
        except Exception as exc:
            self._last_error = str(exc)
            raise

    def get_status(self) -> dict:
        device_present, device_ready, port, device_error = self._device_status()
        last_error = device_error or self._last_error or self._telemetry_last_error
        return {
            "running": self._runner.is_running(),
            "backend": self._backend,
            "port": port,
            "bitrate": self._bitrate,
            "mode": self._mode,
            "device_present": device_present,
            "device_ready": device_ready,
            "last_error": last_error,
            "hot_apply_supported": True,
        }

    def get_telemetry(self) -> dict:
        with self._telemetry_lock:
            return dict(self._telemetry_snapshot)

    def _control_payload(self) -> dict:
        custom_payload: Dict[str, object] = {}
        for key in MS_SIGNAL_LIST:
            if self._custom_enabled.get(key, True):
                custom_payload[key] = self._custom_values.get(key, 0.0)
            else:
                custom_payload[key] = None
        return {
            "profile_id": "ms_simplified",
            "backend": self._backend,
            "iface": self._iface,
            "channel": int(self._channel),
            "port": self._port,
            "serial_baud": int(self._serial_baud),
            "skip_bitrate": bool(self._skip_bitrate),
            "bitrate": int(self._bitrate),
            "hz": float(self._hz),
            "mode": self._mode,
            "custom": custom_payload,
            "hard_test": {},
        }

    def _write_control(self) -> None:
        self._writer.write(self._control_payload())

    def _normalize_updates(self, updates) -> Dict[str, dict]:
        if updates is None:
            return {}
        if isinstance(updates, dict):
            result = {}
            for name, update in updates.items():
                if isinstance(update, dict):
                    result[name] = update
                else:
                    result[name] = {"value": update}
            return result
        if isinstance(updates, list):
            result = {}
            for item in updates:
                if isinstance(item, dict) and "name" in item:
                    name = item.get("name")
                    result[name] = {
                        "value": item.get("value"),
                        "enabled": item.get("enabled"),
                        "period_ms": item.get("period_ms"),
                    }
            return result
        return {}

    def _normalize_range(self, schema: SignalSchema) -> Tuple[float, float, float, float]:
        min_v = schema.min_value
        max_v = schema.max_value
        if min_v is None or max_v is None or min_v >= max_v:
            if schema.name not in self._warned_ranges:
                logging.warning(
                    "Custom signal %s missing min/max range; using fallback 0..100",
                    schema.name,
                )
                self._warned_ranges.add(schema.name)
            min_v = 0.0
            max_v = 100.0

        default_v = float(schema.default_value) if schema.default_value is not None else min_v
        if not math.isfinite(default_v):
            default_v = min_v
        if default_v < min_v:
            default_v = min_v
        if default_v > max_v:
            default_v = max_v

        span = max_v - min_v
        if span <= 0:
            step_v = 1.0
        elif span <= 20:
            step_v = 0.1
        elif span <= 200:
            step_v = 1.0
        elif span <= 2000:
            step_v = 10.0
        else:
            step_v = 50.0
        return float(min_v), float(max_v), float(step_v), float(default_v)

    def _telemetry_poll_loop(self) -> None:
        while True:
            try:
                snapshot = self._build_telemetry_snapshot()
                with self._telemetry_lock:
                    self._telemetry_snapshot = snapshot
                last_error = snapshot.get("last_error")
                if isinstance(last_error, str) and last_error:
                    self._telemetry_last_error = last_error
            except Exception:
                pass
            time.sleep(0.5)

    def _read_telemetry_file(self) -> Dict[str, object]:
        try:
            path = self._telemetry_path
            if not path.exists():
                return {}
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
            self._parse_error_count += 1
            return {}
        except Exception:
            self._parse_error_count += 1
            return {}

    def _build_telemetry_snapshot(self) -> Dict[str, object]:
        raw = self._read_telemetry_file()
        now_ms = int(time.time() * 1000)
        ts = raw.get("ts") if isinstance(raw, dict) else None
        try:
            ts_val = float(ts) if ts is not None else 0.0
        except Exception:
            ts_val = 0.0
        timestamp_ms = int(ts_val * 1000) if ts_val > 0 else now_ms
        counters = raw.get("counters") if isinstance(raw, dict) else None
        if not isinstance(counters, dict):
            counters = {}
        tx_errors = 0
        try:
            tx_errors = int(counters.get("tx_errors", 0))
        except Exception:
            tx_errors = 0
        # error_count_total = CAN tx_errors (send failures) + apply_errors (invalid custom payloads)
        device_present, device_ready, _port, _device_error = self._device_status()
        errors_device = 0 if (device_present and device_ready) else 1
        errors_send = tx_errors
        errors_apply = int(self._apply_error_count)
        errors_parse = int(self._parse_error_count)
        error_count_total = errors_send + errors_apply + errors_parse + errors_device
        signals_raw = raw.get("signals") if isinstance(raw, dict) else None
        if not isinstance(signals_raw, dict):
            signals_raw = {}
        signal_meta = raw.get("signal_meta") if isinstance(raw, dict) else None
        if not isinstance(signal_meta, dict):
            signal_meta = {}
        last_error = raw.get("last_error") if isinstance(raw, dict) else None
        if not isinstance(last_error, str) or not last_error:
            last_error = None

        items: List[Dict[str, object]] = []
        for name in MS_SIGNAL_LIST:
            schema = self._schema_by_name.get(name)
            frame_id = schema.frame_id if schema else None
            try:
                value = float(signals_raw.get(name)) if name in signals_raw else None
            except Exception:
                value = None
            meta = signal_meta.get(name) if isinstance(signal_meta, dict) else None
            if not isinstance(meta, dict):
                meta = {}
            last_sent_ms = meta.get("last_sent_ms")
            try:
                last_sent_ms = int(last_sent_ms) if last_sent_ms else None
            except Exception:
                last_sent_ms = None
            raw_payload = meta.get("raw") if isinstance(meta, dict) else None
            age_ms = None
            if last_sent_ms:
                age_ms = max(0, now_ms - last_sent_ms)
            else:
                age_ms = max(0, now_ms - timestamp_ms)
            items.append(
                {
                    "name": name,
                    "key": name,
                    "arbitration_id": f"0x{frame_id:X}" if frame_id is not None else None,
                    "value": value,
                    "raw": raw_payload,
                    "period_ms": int(schema.default_period_ms) if schema else None,
                    "enabled": bool(self._custom_enabled.get(name, True)),
                    "last_sent_ms": last_sent_ms,
                    "age_ms": age_ms,
                }
            )

        def _sort_key(item: Dict[str, object]) -> tuple:
            enabled = 0 if item.get("enabled") else 1
            age_val = item.get("age_ms")
            try:
                age_val = float(age_val)
            except Exception:
                age_val = 1e12
            name = item.get("key") or item.get("name") or ""
            return (enabled, age_val, str(name))

        items = sorted(items, key=_sort_key)[:20]

        return {
            "timestamp_ms": timestamp_ms,
            "running": self._runner.is_running(),
            "error_count_total": error_count_total,
            "errors_send": errors_send,
            "errors_apply": errors_apply,
            "errors_parse": errors_parse,
            "errors_device": errors_device,
            "signals": items,
            "last_error": last_error,
        }

    def _device_status(self) -> Tuple[bool, bool, str, Optional[str]]:
        if self._backend != "slcan":
            port = self._port or "auto"
            return True, True, port, None

        port = self._port or self._auto_detect_port()
        if not port:
            return False, False, "auto", "No SLCAN device detected"
        present, error = self._check_port_exists(port)
        if error:
            return False, False, port, error
        if not present:
            return False, False, port, f"Port not found: {port}"
        return True, True, port, None

    def _auto_detect_port(self) -> Optional[str]:
        try:
            import os
            import sys

            if sys.platform.startswith("win"):
                try:
                    from serial.tools import list_ports
                except Exception:
                    return None
                candidates = list(list_ports.comports())
                preferred = None
                fallback = None
                for port in candidates:
                    desc = (port.description or "").lower()
                    hwid = (port.hwid or "").lower()
                    if "usb serial device" in desc:
                        preferred = port.device
                        break
                    if "vid:pid" in hwid or "usb" in desc:
                        fallback = fallback or port.device
                return preferred or fallback

            for dev in ("/dev/ttyACM0", "/dev/ttyACM1"):
                if os.path.exists(dev):
                    return dev
        except Exception:
            return None
        return None

    def _check_port_exists(self, port: str) -> Tuple[bool, Optional[str]]:
        try:
            import os
            import sys

            if sys.platform.startswith("win"):
                try:
                    from serial.tools import list_ports
                except Exception:
                    return False, "pyserial not installed"
                return any(p.device == port for p in list_ports.comports()), None
            return os.path.exists(port), None
        except Exception as exc:
            return False, str(exc)

    def _load_signal_schema(self) -> List[SignalSchema]:
        info = {}
        units = {}
        mins = {}
        maxs = {}
        try:
            db = dbc_loader.load_db(paths.dbc_path())
            info = dbc_loader.extract_signal_info(db)
            for msg in db.messages:
                for sig in msg.signals:
                    units[sig.name] = sig.unit
                    mins[sig.name] = getattr(sig, "minimum", None)
                    maxs[sig.name] = getattr(sig, "maximum", None)
        except Exception:
            info = {}

        period_ms = 1000.0 / self._hz if self._hz else 0.0
        schemas: List[SignalSchema] = []
        for name in MS_SIGNAL_LIST:
            meta = info.get(name, {})
            schemas.append(
                SignalSchema(
                    name=name,
                    frame_id=meta.get("frame_id"),
                    default_period_ms=period_ms,
                    value_type="float",
                    unit=units.get(name),
                    min_value=mins.get(name),
                    max_value=maxs.get(name),
                    default_value=float(self._custom_values.get(name, 0.0)),
                )
            )
        return schemas
