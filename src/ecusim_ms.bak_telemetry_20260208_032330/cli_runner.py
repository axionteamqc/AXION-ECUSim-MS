"""CLI runner for the ECU Simulator (MegaSquirt simplified dash)."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Tuple

from ecusim_ms import __version__, dbc_loader, paths
from ecusim_ms.bitrate import BITRATE_PRESETS, validate_bitrate
from ecusim_ms.can_bus import CanBus
from ecusim_ms.can_monitor import CanMonitor
from ecusim_ms.config_merge import merge_control_with_args
from ecusim_ms.control_io import load_control_safe
from ecusim_ms.control_override import read_overrides
from ecusim_ms.dbc_codec import encode_message_safe
from ecusim_ms.models import TelemetrySnapshot
from ecusim_ms.ms_signals import MS_SIGNAL_LIST
from ecusim_ms.paths import can_monitor_path
from ecusim_ms.scenarios import enforce_map_bounds, scenario_values
from ecusim_ms.scheduler import FixedRateScheduler
from ecusim_ms.stop_flag import ensure_not_set, is_set
from ecusim_ms.telemetry import TelemetryWriter
from ecusim_ms.transport import SLCAN_BITRATE_MAP
from ecusim_ms.tx_log import TxLogger
from ecusim_ms.usb_backend import hard_reset_gsusb
from ecusim_ms.validate import validate_startup

DEFAULT_HZ = 50.0
TELEMETRY_HZ = 5.0
DEFAULT_BITRATE = 500_000
SUPPORTED_BITRATES = set(BITRATE_PRESETS)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ECU Simulator - MegaSquirt Simplified Dash (broadcast only)."
    )
    parser.add_argument("--iface", default=None, help="CAN interface (gs_usb, virtual, termux-usb).")
    parser.add_argument("--channel", type=int, default=None, help="CAN channel/index.")
    parser.add_argument(
        "--backend",
        choices=["pythoncan", "slcan"],
        default=None,
        help="CAN backend (pythoncan=gs_usb/virtual, slcan=serial Lawicel).",
    )
    parser.add_argument("--port", default=None, help="SLCAN serial port (COM12, /dev/ttyACM0).")
    parser.add_argument(
        "--serial-baud",
        type=int,
        default=None,
        help="Serial baud rate for SLCAN (default 115200).",
    )
    parser.add_argument(
        "--custom-file",
        type=Path,
        default=None,
        help="Custom frame schedule JSON (list of {id,extended,data,period_ms}).",
    )
    parser.add_argument(
        "--skip-bitrate",
        action="store_true",
        default=None,
        help="Skip SLCAN bitrate setup if adapter does not support Sx commands.",
    )
    parser.add_argument("--bitrate", type=int, default=None, help="CAN bitrate (bit/s).")
    parser.add_argument("--hz", type=float, default=None, help="Broadcast frequency (Hz).")
    parser.add_argument(
        "--mode",
        choices=["loop", "koeo", "idle", "pull", "custom", "silent"],
        default=None,
        help="Operating mode (silent = no TX).",
    )
    parser.add_argument(
        "--stop-file", type=Path, default=paths.stop_flag_path(), help="Stop flag path."
    )
    parser.add_argument(
        "--control", type=Path, default=paths.control_path(), help="control.json path."
    )
    parser.add_argument(
        "--telemetry", type=Path, default=paths.telemetry_path(), help="telemetry.json path."
    )
    parser.add_argument("--dbc", type=Path, default=paths.dbc_path(), help="DBC path.")
    parser.add_argument("--log", type=Path, default=None, help="Optional CSV log of RX frames.")
    parser.add_argument("--tx-log", type=Path, default=None, help="Optional CSV log of TX frames.")
    parser.add_argument(
        "--decode", action="store_true", help="Decode RX frames when logging/monitoring."
    )
    parser.add_argument(
        "--can-monitor-log",
        type=Path,
        default=can_monitor_path(),
        help="Path to JSONL CAN monitor log.",
    )
    parser.add_argument(
        "--monitor-only", action="store_true", help="Do not TX; only listen/log until stop flag."
    )
    parser.add_argument("--tx-debug", action="store_true", help="Log TX frames at 1 Hz.")
    parser.add_argument(
        "--tx-stats",
        action="store_true",
        help="Log per-ID TX counts/rate and last MAP value every second.",
    )
    parser.add_argument(
        "--sniff-stats",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Listen only for N seconds and print ID histogram/rates and 0x5E8 inter-arrival stats.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional duration in seconds to auto-stop (smoke tests).",
    )
    parser.add_argument(
        "--hardkill-on-stall",
        action="store_true",
        help="Attempt USB reset of gs_usb device if send errors persist (best effort).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _auto_detect_port() -> str | None:
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

        # Linux/Android
        for dev in ("/dev/ttyACM0", "/dev/ttyACM1"):
            if os.path.exists(dev):
                return dev
    except Exception:
        return None
    return None


def _validate_settings(
    backend: str,
    iface: str,
    bitrate: int,
    port: str | None,
    skip_bitrate: bool,
) -> None:
    if backend == "pythoncan":
        if iface not in {"gs_usb", "virtual", "termux-usb"}:
            raise ValueError(f"Unsupported interface: {iface}")
        validate_bitrate(bitrate)
        return
    if backend == "slcan":
        if not port:
            raise ValueError("SLCAN backend requires --port")
        if int(bitrate) not in SLCAN_BITRATE_MAP and not skip_bitrate:
            raise ValueError(
                f"Unsupported SLCAN bitrate: {bitrate}. Supported: {sorted(SLCAN_BITRATE_MAP)}"
            )
        return
    raise ValueError(f"Unsupported CAN backend: {backend}")


def _resolve_settings(
    args: argparse.Namespace,
) -> Tuple[str, int, int, str, float, str, str | None, int | None, bool]:
    control_cfg = load_control_safe(args.control)
    merged = merge_control_with_args(control_cfg, args)
    iface = merged.iface
    channel = merged.channel
    bitrate = merged.bitrate
    backend = merged.backend
    port = merged.port or _auto_detect_port()
    serial_baud = merged.serial_baud
    skip_bitrate = merged.skip_bitrate
    hz = merged.hz or DEFAULT_HZ
    mode = merged.mode or "loop"
    _validate_settings(backend, iface, bitrate, port, skip_bitrate)
    return iface, channel, bitrate, mode, hz, backend, port, serial_baud, skip_bitrate


def _stop_requested(stop_path: Path) -> bool:
    try:
        return stop_path.exists()
    except Exception:
        return False


def _sniffer(
    stop_evt: threading.Event,
    bus: CanBus,
    log_path: Path | None,
    decode: bool,
    dbc_db,
    msg_by_id,
    quiet: bool = False,
    rx_counter: Dict[str, int] | None = None,
):
    log_file = None
    try:
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("a", encoding="utf-8")
            log_file.write("ts,arbitration_id,data_hex,decoded\n")

        while not stop_evt.is_set():
            msg = bus.recv(timeout_s=0.5)
            if msg is None:
                continue
            if rx_counter is not None:
                rx_counter["rx"] = rx_counter.get("rx", 0) + 1
            decoded = ""
            if decode and dbc_db and msg_by_id and msg.arbitration_id in msg_by_id:
                try:
                    decoded = msg_by_id[msg.arbitration_id].decode(msg.data)
                except Exception:
                    decoded = ""
            line = f"{time.time():.3f},{hex(msg.arbitration_id)},{msg.data.hex()},{decoded}"
            if not quiet:
                logging.debug("RX %s", line)
            if log_file:
                log_file.write(line + "\n")
                log_file.flush()
    finally:
        if log_file:
            log_file.close()


def _build_payloads(
    dbc_db, scenario: Dict[str, float]
) -> Tuple[Dict[str, bytes], Dict[str, float], Dict[str, Dict[str, object]]]:
    payloads: Dict[str, bytes] = {}
    used_all: Dict[str, float] = {}
    clamped_all: Dict[str, Dict[str, object]] = {}
    for msg in dbc_db.messages:
        desired: Dict[str, float] = {}
        seen_bits = set()
        for sig in msg.signals:
            key = (sig.start, sig.length, getattr(sig, "byte_order", "big_endian"))
            if key in seen_bits:
                continue
            seen_bits.add(key)
            desired[sig.name] = scenario.get(sig.name, 0.0)
        payload, used, clamped = encode_message_safe(msg, desired)
        payloads[msg.name] = payload
        used_all.update(used)
        if clamped:
            clamped_all[msg.name] = clamped
    return payloads, used_all, clamped_all


def _parse_custom_frames(path: Path) -> list[dict]:
    import json

    if path is None:
        return []
    if not path.exists():
        raise RuntimeError(f"custom file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise RuntimeError("custom file must be a list of frame objects")
    frames: list[dict] = []
    for idx, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise RuntimeError(f"custom frame #{idx} must be an object")
        raw_id = raw.get("id")
        if isinstance(raw_id, str):
            raw_id = raw_id.strip()
            if raw_id.lower().startswith("0x"):
                frame_id = int(raw_id, 16)
            else:
                frame_id = int(raw_id)
        else:
            frame_id = int(raw_id)
        extended = bool(raw.get("extended", False))
        data_hex = raw.get("data", "")
        if not isinstance(data_hex, str):
            raise RuntimeError(f"custom frame #{idx} data must be hex string")
        data_hex = data_hex.strip()
        if len(data_hex) % 2 != 0:
            raise RuntimeError(f"custom frame #{idx} data hex length must be even")
        payload = bytes.fromhex(data_hex) if data_hex else b""
        period_ms = float(raw.get("period_ms", 0))
        if period_ms <= 0:
            raise RuntimeError(f"custom frame #{idx} period_ms must be > 0")
        frames.append(
            {
                "id": frame_id,
                "extended": extended,
                "data": payload,
                "period_s": period_ms / 1000.0,
            }
        )
    return frames


class _CustomFrameScheduler:
    def __init__(self, bus: CanBus, frames: list[dict]) -> None:
        self.bus = bus
        self.frames = frames
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._tx_frames = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, timeout_s: float = 2.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout_s)

    def tx_frames(self) -> int:
        with self._lock:
            return self._tx_frames

    def _inc_tx(self) -> None:
        with self._lock:
            self._tx_frames += 1

    def _loop(self) -> None:
        schedule = []
        now = time.monotonic()
        for frame in self.frames:
            schedule.append(
                {
                    "frame": frame,
                    "next": now + frame["period_s"],
                }
            )
        while not self._stop.is_set():
            now = time.monotonic()
            next_due = None
            for item in schedule:
                if now >= item["next"]:
                    frame = item["frame"]
                    try:
                        ok = self.bus.send(
                            frame["id"],
                            frame["data"],
                            is_extended=frame["extended"],
                        )
                        if ok:
                            self._inc_tx()
                    except Exception:
                        pass
                    item["next"] = now + frame["period_s"]
                if next_due is None or item["next"] < next_due:
                    next_due = item["next"]
            if next_due is None:
                time.sleep(0.05)
            else:
                sleep_s = max(0.001, min(0.05, next_due - time.monotonic()))
                time.sleep(sleep_s)


def _sniff_stats(bus: CanBus, duration: float, focus_id: int = 1512) -> None:
    """Passive sniff for a fixed duration; logs ID histogram and focus inter-arrival stats."""
    if duration <= 0:
        logging.error("sniff duration must be positive")
        return

    counts: Dict[int, int] = {}
    focus_prev_ts: float | None = None
    focus_deltas: list[float] = []
    start_ts = time.time()
    end_ts = start_ts + duration

    while time.time() < end_ts:
        msg = bus.recv(timeout_s=0.2)
        if msg is None:
            continue
        now = time.time()
        fid = int(msg.arbitration_id)
        counts[fid] = counts.get(fid, 0) + 1
        if fid == focus_id:
            if focus_prev_ts is not None:
                focus_deltas.append(now - focus_prev_ts)
            focus_prev_ts = now

    elapsed = max(time.time() - start_ts, 1e-6)
    total = sum(counts.values())
    logging.info("SNIFF_SUMMARY duration=%.2fs frames=%d ids=%d", elapsed, total, len(counts))
    for fid in sorted(counts):
        cnt = counts[fid]
        freq = cnt / elapsed
        logging.info("ID 0x%x count=%d freq=%.2f/s", fid, cnt, freq)

    if focus_deltas:
        mn = min(focus_deltas)
        mx = max(focus_deltas)
        avg = sum(focus_deltas) / len(focus_deltas)
        logging.info(
            "ID 0x%x inter-arrival (s): min=%.4f max=%.4f avg=%.4f samples=%d",
            focus_id,
            mn,
            mx,
            avg,
            len(focus_deltas),
        )
    else:
        logging.warning("ID 0x%x not observed; no inter-arrival stats", focus_id)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        iface, channel, bitrate, mode, hz, backend, port, serial_baud, skip_bitrate = (
            _resolve_settings(args)
        )
    except Exception as exc:
        logging.error("Invalid settings: %s", exc)
        return 1
    control_cfg = load_control_safe(args.control)
    merged_cfg = merge_control_with_args(control_cfg, args)
    dbc_db = dbc_loader.load_db(args.dbc)
    msg_by_name, msg_by_id = dbc_loader.build_message_map(dbc_db)
    mode = validate_startup(dbc_db, merged_cfg)

    bitrate_label = (
        f"{bitrate} (standard)" if bitrate in SUPPORTED_BITRATES else f"{bitrate} (custom)"
    )
    logging.info(
        "RUN profile=%s backend=%s iface=%s channel=%s port=%s baud=%s bitrate=%s hz=%.2f mode=%s control=%s stop=%s",
        merged_cfg.profile_id,
        backend,
        iface,
        channel,
        port or "",
        serial_baud if serial_baud else "",
        bitrate_label,
        hz,
        mode,
        args.control,
        args.stop_file,
    )
    if backend == "slcan" and port:
        logging.info("SLCAN port selected: %s", port)
    if args.custom_file and mode.lower() != "custom":
        logging.warning("custom-file provided but mode=%s; ignoring custom schedule", mode)

    ensure_not_set(args.stop_file)
    bus = CanBus(
        iface=iface,
        channel=channel,
        bitrate=bitrate,
        backend=backend,
        port=port,
        serial_baud=serial_baud,
        slcan_skip_bitrate=skip_bitrate,
    )
    bus.open()

    if args.sniff_stats is not None:
        logging.info("Starting sniff-stats for %.2fs (focus 0x5e8)", args.sniff_stats)
        try:
            _sniff_stats(bus, args.sniff_stats, focus_id=1512)
        finally:
            bus.close()
        return 0

    # One-shot sample payload log for quick comparison/debug
    try:
        sample_signals = scenario_values(mode, 0.0)
        payloads, _, _ = _build_payloads(dbc_db, sample_signals)
        for msg in dbc_db.messages:
            data = payloads.get(msg.name)
            if data is None:
                continue
            logging.info("TX_SAMPLE id=0x%x dlc=%d data=%s", msg.frame_id, len(data), data.hex())
    except Exception as exc:
        logging.warning("Unable to log TX sample: %s", exc)

    stop_evt = threading.Event()
    sniffer_thread = None
    rx_counter: Dict[str, int] = {"rx": 0}
    sniffer_thread = threading.Thread(
        target=_sniffer,
        args=(
            stop_evt,
            bus,
            args.log,
            args.decode,
            dbc_db if args.decode else None,
            msg_by_id if args.decode else None,
            not (args.monitor_only or args.log or args.decode),
            rx_counter,
        ),
        daemon=True,
    )
    sniffer_thread.start()

    can_monitor = CanMonitor(bus, args.can_monitor_log)
    can_monitor.start()

    if args.monitor_only:
        logging.info("Monitor-only mode; waiting for stop flag at %s", args.stop_file)
        try:
            while not stop_evt.is_set():
                if is_set(args.stop_file):
                    stop_evt.set()
                    break
                time.sleep(0.5)
        finally:
            stop_evt.set()
            if sniffer_thread:
                sniffer_thread.join(timeout=2.0)
            bus.close()
        return 0

    custom_scheduler: _CustomFrameScheduler | None = None
    custom_frames: list[dict] = []
    if mode.lower() == "custom" and args.custom_file:
        try:
            custom_frames = _parse_custom_frames(args.custom_file)
            custom_scheduler = _CustomFrameScheduler(bus, custom_frames)
            custom_scheduler.start()
            logging.info("Custom scheduler started with %d frames", len(custom_frames))
        except Exception as exc:
            logging.error("Failed to load custom frames: %s", exc)
            stop_evt.set()
            bus.close()
            return 1

    scheduler = FixedRateScheduler(hz if hz > 0 else DEFAULT_HZ)
    scheduler.start()
    start = time.perf_counter()
    last_debug = start
    telem_writer = TelemetryWriter(args.telemetry, TELEMETRY_HZ)
    tx_logger = TxLogger(args.tx_log) if args.tx_log else None
    tx_frames = 0
    rx_frames = 0
    consec_errors = 0
    backoff = 0.5
    exit_code = 0
    last_state = None
    hardkill_enabled = bool(args.hardkill_on_stall and iface == "gs_usb")
    can_monitor_file = None
    last_tx_ok_event_ts = 0.0
    last_rate = {"ts": time.time(), "tx": 0, "rx": 0, "err": 0}
    session_id = 1
    tx_counts_by_id = {msg.frame_id: 0 for msg in dbc_db.messages}
    last_tx_counts = dict(tx_counts_by_id)
    last_tx_stats_ts = time.time()
    last_map_value: float | None = None
    last_sent_ms_by_signal = {name: 0 for name in MS_SIGNAL_LIST}
    last_raw_by_signal = {name: "" for name in MS_SIGNAL_LIST}
    send_exception_count = 0
    last_error_msg: str | None = None
    # jitter tracking
    last_send_ts = start
    jitter = {"min": None, "max": None, "sum": 0.0, "count": 0, "late": 0}
    last_mode = None

    def _short_error(message: object, limit: int = 120) -> str:
        msg = str(message)
        if len(msg) <= limit:
            return msg
        return msg[: max(0, limit - 3)] + "..."

    def emit_can_event(evt: Dict[str, object]) -> None:
        nonlocal can_monitor_file
        if can_monitor_file is None:
            try:
                args.can_monitor_log.parent.mkdir(parents=True, exist_ok=True)
                can_monitor_file = args.can_monitor_log.open("a", encoding="utf-8")
            except Exception as exc:
                logging.warning("Cannot open CAN monitor log %s: %s", args.can_monitor_log, exc)
                return

        def to_jsonable(obj: Any):
            if isinstance(obj, dict):
                return {to_jsonable(k): to_jsonable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [to_jsonable(v) for v in obj]
            if isinstance(obj, Enum):
                return obj.name
            if isinstance(obj, bytes):
                return obj.hex()
            if isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            return str(obj)

        evt = to_jsonable(dict(evt))
        evt.setdefault("ts", time.time())
        try:
            import json

            can_monitor_file.write(json.dumps(evt, separators=(",", ":"), default=str) + "\n")
            can_monitor_file.flush()
        except Exception as exc:
            logging.warning("Failed to write CAN monitor event: %s", exc)

    try:
        emit_can_event(
            {
                "type": "start",
                "session_id": session_id,
                "label": "SESSION_START",
                "iface": iface,
                "channel": channel,
                "bitrate": bitrate,
                "hz": hz,
                "mode": mode,
            }
        )
        # initial mode snapshot
        emit_can_event(
            {
                "type": "mode_change",
                "from": None,
                "to": mode,
                "frames": len(dbc_db.messages),
                "hz": hz,
            }
        )
        while not stop_evt.is_set():
            now = time.perf_counter()
            t = now - start

            if args.duration is not None and t >= args.duration:
                logging.info("Duration reached (%.2fs); stopping", args.duration)
                stop_evt.set()
                break

            scenario = scenario_values(mode, t)
            overrides = read_overrides(args.control, MS_SIGNAL_LIST)
            if mode.lower() == "custom":
                scenario.update(overrides)
            enforce_map_bounds(scenario, f"{mode}_runtime")
            if mode != last_mode:
                emit_can_event(
                    {
                        "type": "mode_change",
                        "from": last_mode,
                        "to": mode,
                        "frames": len(dbc_db.messages),
                        "hz": hz,
                    }
                )
                last_mode = mode

            used_phys: Dict[str, float] = dict(scenario)
            clamped_agg: Dict[str, Dict[str, object]] = {}

            if mode.lower() == "custom" and custom_scheduler:
                tx_frames = custom_scheduler.tx_frames()
            elif mode.lower() != "silent":
                try:
                    payloads, used_phys_encoded, clamped = _build_payloads(dbc_db, scenario)
                except Exception as exc:
                    logging.error("Encoding failed, stopping runner: %s", exc)
                    exit_code = 1
                    break
                used_phys.update(used_phys_encoded)
                for msg_name, info in clamped.items():
                    clamped_agg[msg_name] = info

                for msg in dbc_db.messages:
                    data = payloads.get(msg.name)
                    if data is None:
                        continue
                    now_ms = int(time.time() * 1000)
                    payload_hex = data.hex()
                    for sig in msg.signals:
                        key = sig.name
                        last_sent_ms_by_signal[key] = now_ms
                        last_raw_by_signal[key] = payload_hex
                    now_send = time.perf_counter()
                    dt = now_send - last_send_ts
                    last_send_ts = now_send
                    jitter["min"] = dt if jitter["min"] is None else min(jitter["min"], dt)
                    jitter["max"] = dt if jitter["max"] is None else max(jitter["max"], dt)
                    jitter["sum"] += dt
                    jitter["count"] += 1
                    if dt > (1.0 / hz) * 1.5:
                        jitter["late"] += 1
                    send_error_reason = None
                    try:
                        ok = bus.send(
                            msg.frame_id,
                            data,
                            is_extended=getattr(msg, "is_extended_frame", False),
                        )
                    except Exception as exc:
                        send_error_reason = f"exception: {exc}"
                        logging.warning("Send error (iface=%s): %s", iface, exc)
                        emit_can_event(
                            {
                                "type": "tx_fail",
                                "id": msg.frame_id,
                                "dlc": len(data) if data else 0,
                                "mode": mode,
                                "hz": hz,
                                "error": str(exc),
                            }
                        )
                        ok = False

                    if ok:
                        tx_frames += 1
                        tx_counts_by_id[msg.frame_id] = tx_counts_by_id.get(msg.frame_id, 0) + 1
                        if msg.frame_id == 1512:
                            last_map_value = used_phys.get("map", last_map_value)
                        consec_errors = 0
                        backoff = 0.5
                        now_ts = time.time()
                        if now_ts - last_tx_ok_event_ts >= 1.0:
                            emit_can_event(
                                {
                                    "type": "tx_ok",
                                    "id": msg.frame_id,
                                    "dlc": len(data),
                                    "mode": mode,
                                    "hz": hz,
                                    "tx_frames": tx_frames,
                                }
                            )
                            last_tx_ok_event_ts = now_ts
                        if tx_logger:
                            used_subset = {
                                sig.name: used_phys.get(sig.name, 0.0) for sig in msg.signals
                            }
                            tx_logger.write_line(
                                time.time(), msg.frame_id, msg.length, data.hex(), used_subset
                            )
                    else:
                        if send_error_reason:
                            last_error_msg = _short_error(
                                f"send error id=0x{msg.frame_id:x}: {send_error_reason}"
                            )
                            send_exception_count += 1
                        else:
                            last_error_msg = _short_error(f"send failed id=0x{msg.frame_id:x}")
                        consec_errors += 1
                        emit_can_event(
                            {
                                "type": "tx_fail",
                                "id": msg.frame_id,
                                "dlc": len(data) if data else 0,
                                "mode": mode,
                                "hz": hz,
                                "consec_fail": consec_errors,
                            }
                        )

                        if consec_errors >= 50:
                            logging.warning(
                                "Too many send errors (%s); attempting bus reopen",
                                consec_errors,
                            )
                            emit_can_event({"type": "reopen_begin"})
                            bus.close()
                            reopened = False
                            if hardkill_enabled:
                                try:
                                    logging.warning(
                                        "Attempting USB hard reset (gs_usb) after stall"
                                    )
                                    hard_reset_gsusb()
                                    time.sleep(1.0)
                                except Exception as exc:
                                    logging.error("USB hard reset failed: %s", exc)
                            while not stop_evt.is_set():
                                if is_set(args.stop_file):
                                    stop_evt.set()
                                    break
                                try:
                                    bus.open()
                                    logging.info("Bus reopen successful")
                                    consec_errors = 0
                                    backoff = 0.5
                                    reopened = True
                                    emit_can_event({"type": "reopen_ok"})
                                    break
                                except Exception as exc:
                                    logging.error("Bus reopen failed: %s", exc)
                                    emit_can_event({"type": "reopen_fail", "error": str(exc)})
                                    time.sleep(backoff)
                                    backoff = min(backoff * 2, 2.0)
                            if not reopened:
                                break
            else:
                payloads = {}

            state_str = bus.get_state() or ""
            if state_str and state_str != last_state:
                logging.warning("CAN state changed: %s", state_str)
                last_state = state_str
                emit_can_event({"type": "bus_state", "state": state_str})

            # periodic rates snapshot (1 Hz)
            now_ts = time.time()
            rx_frames = rx_counter.get("rx", rx_frames)
            if now_ts - last_rate["ts"] >= 1.0:
                dt = now_ts - last_rate["ts"]
                dtx = tx_frames - last_rate["tx"]
                drx = rx_frames - last_rate["rx"]
                derr = bus.tx_errors - last_rate["err"]
                emit_can_event(
                    {
                        "type": "rate",
                        "tx_per_s": dtx / dt if dt > 0 else 0,
                        "rx_per_s": drx / dt if dt > 0 else 0,
                        "err_per_s": derr / dt if dt > 0 else 0,
                        "state": state_str,
                    }
                )
                last_rate = {"ts": now_ts, "tx": tx_frames, "rx": rx_frames, "err": bus.tx_errors}
                if jitter["count"] > 0:
                    emit_can_event(
                        {
                            "type": "tx_timing",
                            "hz_target": hz,
                            "dt_ms_min": (jitter["min"] or 0) * 1000.0,
                            "dt_ms_max": (jitter["max"] or 0) * 1000.0,
                            "dt_ms_avg": (jitter["sum"] / max(jitter["count"], 1)) * 1000.0,
                            "late_cycles": jitter["late"],
                        }
                    )
                jitter = {"min": None, "max": None, "sum": 0.0, "count": 0, "late": 0}
                if args.tx_stats:
                    dt_stats = now_ts - last_tx_stats_ts
                    if dt_stats <= 0:
                        dt_stats = dt if dt > 0 else 1.0
                    parts = []
                    for msg in sorted(dbc_db.messages, key=lambda m: m.frame_id):
                        fid = msg.frame_id
                        delta = tx_counts_by_id.get(fid, 0) - last_tx_counts.get(fid, 0)
                        freq = delta / dt_stats if dt_stats > 0 else 0.0
                        parts.append(f"{fid}:{delta} ({freq:.1f}/s)")
                    map_str = f"{last_map_value:.3f}" if last_map_value is not None else "n/a"
                    logging.info("TX_STATS dt=%.2fs %s map=%s", dt_stats, " ".join(parts), map_str)
                    last_tx_counts = dict(tx_counts_by_id)
                    last_tx_stats_ts = now_ts

            snapshot = TelemetrySnapshot(
                ts=time.time(),
                iface=iface,
                bitrate=bitrate,
                hz=hz,
                mode=mode,
                last_error=last_error_msg,
                signals=used_phys,
                signal_meta={
                    key: {
                        **(
                            {"last_sent_ms": last_sent_ms_by_signal.get(key)}
                            if last_sent_ms_by_signal.get(key)
                            else {}
                        ),
                        **(
                            {"raw": last_raw_by_signal.get(key)}
                            if last_raw_by_signal.get(key)
                            else {}
                        ),
                    }
                    for key in MS_SIGNAL_LIST
                },
                clamped=clamped_agg,
                faults={},
                counters={
                    "tx_frames": tx_frames,
                    "tx_errors": bus.tx_errors + send_exception_count,
                    "rx_frames": rx_frames,
                    "bus_state": state_str,
                },
            )
            telem_writer.maybe_write(snapshot)

            if args.tx_debug and (now - last_debug) >= 1.0:
                clamped_keys = list(clamped_agg.keys())
                logging.info(
                    "TX mode=%s iface=%s hz=%.2f tx_frames=%d clamped=%s",
                    mode,
                    iface,
                    hz,
                    tx_frames,
                    clamped_keys[:5],
                )
                last_debug = now

            if is_set(args.stop_file):
                stop_evt.set()
                break

            scheduler.wait_next()
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt: stopping")
        stop_evt.set()
    finally:
        stop_evt.set()
        if custom_scheduler:
            custom_scheduler.stop()
        if sniffer_thread:
            sniffer_thread.join(timeout=2.0)
        can_monitor.stop()
        if tx_logger:
            tx_logger.close()
        bus.close()
        if can_monitor_file:
            try:
                emit_can_event({"type": "stop", "session_id": session_id, "label": "SESSION_STOP"})
            except Exception:
                pass
            try:
                can_monitor_file.close()
            except Exception:
                pass

    logging.info("TX summary mode=%s tx_frames=%d", mode, tx_frames)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
