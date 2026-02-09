"""Tkinter GUI skeleton for the ECU Simulator."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from ecusim_ms import models, paths
from ecusim_ms.can_bus import CanBus
from ecusim_ms.control_io import load_control_safe
from ecusim_ms.gui_can_monitor import CanMonitorView
from ecusim_ms.gui_control_writer import ControlWriter
from ecusim_ms.gui_custom_editor import CustomEditor
from ecusim_ms.gui_hard_test import HardTestPanel
from ecusim_ms.gui_live_view import LiveView
from ecusim_ms.gui_logger import GuiLogger
from ecusim_ms.gui_paths import PathPicker, open_folder
from ecusim_ms.gui_telemetry_reader import TelemetryReader
from ecusim_ms.gui_widgets import LabeledCombo, LabeledEntry
from ecusim_ms.ms_signals import MS_SIGNAL_LIST
from ecusim_ms.runner_process import RunnerProcess
from ecusim_ms.stop_flag import ensure_not_set, request_stop
from ecusim_ms.usb_backend import probe_any_gsusb

WINDOW_TITLE = "ECU Simulator - MegaSquirt (v1.00)"
BITRATE_PRESETS = ["125000", "250000", "500000", "1000000", "custom"]
HZ_PRESETS = ["20.0", "50.0", "custom"]
MODE_OPTIONS = [
    ("loop", "loop: koeo->idle->pull loop"),
    ("koeo", "KOEO: key-on engine-off"),
    ("idle", "IDLE: idle"),
    ("pull", "PULL: acceleration"),
    ("custom", "CUSTOM: manual values"),
    ("hard_test", "HARD_TEST: stress (future)"),
    ("silent", "SILENT: no TX, telemetry only"),
    ("monitor", "MONITOR: RX only"),
]


def _setup_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"))
    style.configure("ProbeOk.TLabel", foreground="green")
    style.configure("ProbeFail.TLabel", foreground="red")
    style.configure("ProbeIdle.TLabel", foreground="gray")


class MainWindow(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=10)
        self.master = master
        self.control_cfg = load_control_safe(paths.control_path())
        self.writer = ControlWriter(paths.control_path())
        self.runner = RunnerProcess()
        self.last_started_cfg: tuple[str, str, int, str, int, bool, int, bool] | None = None
        self.restart_needed = False
        self.telemetry_reader = TelemetryReader(paths.telemetry_path(), poll_hz=5.0)
        self._suppress_writes = False
        self._rate_prev: dict | None = None

        self.grid(row=0, column=0, sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        self._build_controls()
        self._build_right_pane()
        self._start_polling()

    def _build_controls(self) -> None:
        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        canvas = tk.Canvas(container, highlightthickness=0)
        vscroll = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")

        frame = ttk.LabelFrame(canvas, text="Controls")
        frame_id = canvas.create_window((0, 0), window=frame, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(frame_id, width=event.width)

        frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        frame.columnconfigure(0, weight=1)

        self.backend = LabeledCombo(
            frame,
            "Backend",
            ["pythoncan", "slcan"],
            default="pythoncan",
        )
        self.backend.grid(row=0, column=0, sticky="ew", pady=2)
        self.port = LabeledEntry(frame, "Port (SLCAN)", default="")
        self.port.grid(row=1, column=0, sticky="ew", pady=2)
        self.serial_baud = LabeledEntry(frame, "Serial baud", default="115200")
        self.serial_baud.grid(row=2, column=0, sticky="ew", pady=2)
        self.skip_bitrate_var = tk.BooleanVar(value=False)
        self.skip_bitrate = ttk.Checkbutton(
            frame,
            text="Skip bitrate (SLCAN)",
            variable=self.skip_bitrate_var,
            command=self._schedule_write,
        )
        self.skip_bitrate.grid(row=3, column=0, sticky="w", pady=(2, 2))

        self.iface = LabeledCombo(
            frame,
            "Interface (pythoncan)",
            ["virtual", "gs_usb"],
            default="virtual",
        )
        self.iface.grid(row=4, column=0, sticky="ew", pady=2)

        mode_values = [m[0] for m in MODE_OPTIONS]
        self.mode = LabeledCombo(frame, "Mode", mode_values, default="loop")
        self.mode.grid(row=5, column=0, sticky="ew", pady=2)
        self.mode_desc = ttk.Label(frame, text=dict(MODE_OPTIONS).get("loop", ""))
        self.mode_desc.grid(row=6, column=0, sticky="w", pady=(0, 4))

        self.channel = LabeledEntry(frame, "Channel", default="0")
        self.channel.grid(row=7, column=0, sticky="ew", pady=2)

        self.bitrate_preset = LabeledCombo(
            frame, "Bitrate preset", BITRATE_PRESETS, default="500000"
        )
        self.bitrate_preset.grid(row=8, column=0, sticky="ew", pady=2)
        self.bitrate_custom = LabeledEntry(frame, "Bitrate custom", default="500000")
        self.bitrate_custom.grid(row=9, column=0, sticky="ew", pady=2)

        self.hz_preset = LabeledCombo(frame, "Hz preset", HZ_PRESETS, default="50.0")
        self.hz_preset.grid(row=10, column=0, sticky="ew", pady=2)
        self.hz_custom = LabeledEntry(frame, "Hz custom", default="50.0")
        self.hz_custom.grid(row=11, column=0, sticky="ew", pady=2)

        ttk.Button(frame, text="Probe CAN", command=self._probe_can).grid(
            row=12, column=0, sticky="ew", pady=(6, 2)
        )
        self.probe_label = ttk.Label(frame, text="Probe: idle", style="ProbeIdle.TLabel")
        self.probe_label.grid(row=13, column=0, sticky="w", pady=(0, 4))

        ttk.Button(frame, text="Save control.json", command=self._write_control_immediate).grid(
            row=14, column=0, sticky="ew", pady=(8, 2)
        )
        ttk.Button(frame, text="Start runner", command=self._start_runner).grid(
            row=15, column=0, sticky="ew", pady=2
        )
        ttk.Button(frame, text="Start monitor-only", command=self._start_monitor).grid(
            row=16, column=0, sticky="ew", pady=2
        )
        ttk.Button(frame, text="Stop runner", command=self._stop_runner).grid(
            row=17, column=0, sticky="ew", pady=2
        )
        self.restart_button = ttk.Button(
            frame, text="Restart runner", command=self._restart_runner, state="disabled"
        )
        self.restart_button.grid(row=18, column=0, sticky="ew", pady=2)
        ttk.Button(frame, text="HARD KILL (force)", command=self._hard_kill_runner).grid(
            row=19, column=0, sticky="ew", pady=(2, 4)
        )
        ttk.Button(frame, text="Selftest (virtual)", command=self._selftest_async).grid(
            row=20, column=0, sticky="ew", pady=2
        )
        ttk.Button(frame, text="Quit", command=self.master.destroy).grid(
            row=21, column=0, sticky="ew", pady=(8, 2)
        )

        self.restart_label = ttk.Label(frame, text="", foreground="red")
        self.restart_label.grid(row=22, column=0, sticky="w", pady=(6, 0))
        self.state_label = ttk.Label(frame, text="State: STOPPED", foreground="red")
        self.state_label.grid(row=23, column=0, sticky="w", pady=(2, 0))
        self.status = ttk.Label(frame, text="Status: idle")
        self.status.grid(row=24, column=0, sticky="w", pady=(2, 0))

        notebook = ttk.Notebook(frame)
        notebook.grid(row=25, column=0, sticky="nsew", pady=(8, 0))
        frame.rowconfigure(25, weight=1)
        frame.columnconfigure(0, weight=1)
        notebook.rowconfigure(0, weight=1)
        notebook.columnconfigure(0, weight=1)

        tab_custom = ttk.Frame(notebook)
        tab_custom.columnconfigure(0, weight=3)
        tab_custom.columnconfigure(1, weight=0)
        tab_custom.rowconfigure(0, weight=1)
        self.custom_editor = CustomEditor(tab_custom, defaults=dict(models.DEFAULT_SIGNAL_VALUES))
        self.custom_editor.grid(row=0, column=0, sticky="nsew", pady=(4, 0), padx=(0, 6))
        custom_buttons = ttk.Frame(tab_custom)
        custom_buttons.grid(row=0, column=1, sticky="n", pady=(4, 0))
        ttk.Button(custom_buttons, text="Apply CUSTOM", command=self._apply_custom).grid(
            row=0, column=0, sticky="ew", pady=2
        )
        ttk.Button(custom_buttons, text="Reset CUSTOM", command=self._reset_custom).grid(
            row=1, column=0, sticky="ew", pady=(0, 4)
        )

        tab_hard = ttk.Frame(notebook)
        tab_hard.columnconfigure(0, weight=1)
        tab_hard.rowconfigure(0, weight=1)
        tab_hard.rowconfigure(1, weight=0)
        hard_body = ttk.Frame(tab_hard)
        hard_body.grid(row=0, column=0, sticky="nsew", pady=(4, 0))
        hard_body.columnconfigure(0, weight=1)
        hard_body.rowconfigure(0, weight=1)
        self.hard_panel = HardTestPanel(hard_body)
        self.hard_panel.grid(row=0, column=0, sticky="nsew")
        hard_buttons = ttk.Frame(tab_hard)
        hard_buttons.grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ttk.Button(hard_buttons, text="Apply HARD_TEST", command=self._apply_hard_test).grid(
            row=0, column=0, sticky="ew", pady=2
        )
        ttk.Button(hard_buttons, text="Reset HARD_TEST", command=self._reset_hard_test).grid(
            row=1, column=0, sticky="ew", pady=(0, 4)
        )

        tab_can = ttk.Frame(notebook)
        tab_can.columnconfigure(0, weight=1)
        tab_can.rowconfigure(1, weight=1)
        state_frame = ttk.LabelFrame(tab_can, text="State")
        state_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        for i in range(4):
            state_frame.columnconfigure(i, weight=1)
        self.act_iface = ttk.Label(state_frame, text="iface=?")
        self.act_iface.grid(row=0, column=0, sticky="w", padx=2)
        self.act_bitrate = ttk.Label(state_frame, text="bitrate=?")
        self.act_bitrate.grid(row=0, column=1, sticky="w", padx=2)
        self.act_state = ttk.Label(state_frame, text="state=?")
        self.act_state.grid(row=0, column=2, sticky="w", padx=2)
        ttk.Button(state_frame, text="Reset stats", command=self._reset_can_stats).grid(
            row=0, column=3, sticky="e", padx=2
        )
        self.act_tx_rate = ttk.Label(state_frame, text="tx/s=?")
        self.act_tx_rate.grid(row=1, column=0, sticky="w", padx=2)
        self.act_rx_rate = ttk.Label(state_frame, text="rx/s=?")
        self.act_rx_rate.grid(row=1, column=1, sticky="w", padx=2)
        self.act_err_rate = ttk.Label(state_frame, text="err/s=?")
        self.act_err_rate.grid(row=1, column=2, sticky="w", padx=2)

        can_stream = ttk.LabelFrame(tab_can, text="CAN Activity")
        can_stream.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))
        can_stream.columnconfigure(0, weight=1)
        can_stream.rowconfigure(0, weight=1)
        self.can_activity_monitor = CanMonitorView(
            can_stream, paths.can_monitor_path(), poll_ms=200
        )
        self.can_activity_monitor.grid(row=0, column=0, sticky="nsew")

        notebook.add(tab_custom, text="Custom")
        notebook.add(tab_hard, text="Hard Test")
        notebook.add(tab_can, text="CAN Activity")

        ttk.Label(frame, text="Paths").grid(row=30, column=0, sticky="w", pady=(8, 2))
        self.control_path_picker = PathPicker(frame, "Control", str(paths.control_path()))
        self.control_path_picker.grid(row=31, column=0, sticky="ew", pady=1)
        self.telemetry_path_picker = PathPicker(frame, "Telemetry", str(paths.telemetry_path()))
        self.telemetry_path_picker.grid(row=32, column=0, sticky="ew", pady=1)
        self.stop_path_picker = PathPicker(frame, "Stop flag", str(paths.stop_flag_path()))
        self.stop_path_picker.grid(row=33, column=0, sticky="ew", pady=1)
        ttk.Button(
            frame, text="Open Data Folder", command=lambda: open_folder(str(paths.data_dir()))
        ).grid(row=34, column=0, sticky="ew", pady=(4, 0))

        self.backend.combo.bind("<<ComboboxSelected>>", lambda e: self._on_backend_change())
        self.iface.combo.bind("<<ComboboxSelected>>", lambda e: self._schedule_write())
        self.mode.combo.bind(
            "<<ComboboxSelected>>", lambda e: (self._schedule_write(), self._update_mode_desc())
        )
        for entry in (
            self.channel.entry,
            self.port.entry,
            self.serial_baud.entry,
            self.bitrate_custom.entry,
            self.hz_custom.entry,
        ):
            entry.bind("<FocusOut>", lambda e: self._schedule_write())
            entry.bind("<Return>", lambda e: self._schedule_write())
        self.bitrate_preset.combo.bind("<<ComboboxSelected>>", lambda e: self._on_preset_change())
        self.hz_preset.combo.bind("<<ComboboxSelected>>", lambda e: self._on_preset_change())

        self._apply_control_to_widgets()
        self._on_backend_change(initial=True)
        self._update_mode_desc()
        self._update_restart_button_state()
        self.backend.combo.focus_set()

    def _build_right_pane(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=1, sticky="nsew")

        telem_frame = ttk.Frame(notebook)
        telem_frame.columnconfigure(0, weight=1)
        telem_frame.rowconfigure(2, weight=1)

        header = ttk.Label(telem_frame, text="iface=? bitrate=? hz=? mode=?")
        header.grid(row=0, column=0, sticky="w", padx=2, pady=(2, 0))
        self.telemetry_header = header

        counters_frame = ttk.Frame(telem_frame)
        counters_frame.grid(row=1, column=0, sticky="w", padx=2, pady=(2, 4))
        self.counter_tx = ttk.Label(counters_frame, text="tx=0")
        self.counter_tx.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.counter_txerr = ttk.Label(counters_frame, text="tx_err=0")
        self.counter_txerr.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.counter_rx = ttk.Label(counters_frame, text="rx=0")
        self.counter_rx.grid(row=0, column=2, sticky="w", padx=(0, 8))

        self.table = LiveView(telem_frame, MS_SIGNAL_LIST)
        self.table.grid(row=2, column=0, sticky="nsew")

        logs_frame = ttk.Frame(notebook)
        logs_frame.columnconfigure(0, weight=1)
        logs_frame.rowconfigure(0, weight=1)
        self.logger = GuiLogger(logs_frame, height=24)
        self.logger.grid(row=0, column=0, sticky="nsew")
        self.runner.set_log_callbacks(self.logger.info, self.logger.error)

        canmon_frame = ttk.Frame(notebook)
        canmon_frame.columnconfigure(0, weight=1)
        canmon_frame.rowconfigure(0, weight=1)
        self.can_monitor = CanMonitorView(canmon_frame, paths.can_monitor_path())
        self.can_monitor.grid(row=0, column=0, sticky="nsew")

        notebook.add(telem_frame, text="Telemetry")
        notebook.add(logs_frame, text="Logs")
        notebook.add(canmon_frame, text="CAN Monitor")

    def _current_bus_cfg(
        self, monitor_only_override: bool | None = None
    ) -> tuple[str, str, int, str, int, bool, int, bool]:
        payload = self._control_payload()
        monitor_only = monitor_only_override
        if monitor_only is None:
            monitor_only = (self.mode.get() or "").lower() == "monitor"
        return (
            str(payload.get("backend", "")),
            str(payload.get("iface", "")),
            int(payload.get("channel", 0)),
            str(payload.get("port", "")),
            int(payload.get("serial_baud", 0)),
            bool(payload.get("skip_bitrate", False)),
            int(payload.get("bitrate", 0)),
            bool(monitor_only),
        )

    def _update_restart_button_state(self) -> None:
        running = self.runner.is_running()
        if self.restart_needed and running:
            self.restart_button.config(state="normal")
        else:
            self.restart_button.config(state="disabled")

    def _apply_control_to_widgets(self) -> None:
        """Load control.json values into widgets without triggering writes."""
        cfg = self.control_cfg
        self._suppress_writes = True
        try:
            self.backend.set(str(getattr(cfg, "backend", "pythoncan") or "pythoncan"))
            self.iface.set(str(cfg.iface or "virtual"))
            self.mode.set(str(cfg.mode or "loop"))
            self.channel.set(str(cfg.channel))
            self.port.set(str(getattr(cfg, "port", "") or ""))
            self.serial_baud.set(str(getattr(cfg, "serial_baud", 115200) or 115200))
            self.skip_bitrate_var.set(bool(getattr(cfg, "skip_bitrate", False)))

            bitrate_str = str(cfg.bitrate)
            if bitrate_str in BITRATE_PRESETS:
                self.bitrate_preset.set(bitrate_str)
                self.bitrate_custom.set(bitrate_str)
            else:
                self.bitrate_preset.set("custom")
                self.bitrate_custom.set(bitrate_str)

            hz_val = cfg.hz if cfg.hz else 50.0
            hz_str = f"{hz_val:.1f}"
            if hz_str in HZ_PRESETS:
                self.hz_preset.set(hz_str)
                self.hz_custom.set(hz_str)
            else:
                self.hz_preset.set("custom")
                self.hz_custom.set(hz_str)

            if cfg.custom:
                self.custom_editor.set_defaults(cfg.custom)
            else:
                self.custom_editor.reset_defaults()
        finally:
            self._suppress_writes = False

    def _on_backend_change(self, initial: bool = False) -> None:
        backend = (self.backend.get() or "pythoncan").lower()
        if backend == "slcan":
            try:
                self.iface.set("virtual")
            except Exception:
                pass
            self.iface.combo.configure(state="disabled")
            self.port.entry.configure(state="normal")
            self.serial_baud.entry.configure(state="normal")
            self.skip_bitrate.configure(state="normal")
        else:
            self.iface.combo.configure(state="readonly")
            self.port.entry.configure(state="disabled")
            self.serial_baud.entry.configure(state="disabled")
            self.skip_bitrate.configure(state="disabled")
        if not initial:
            self._schedule_write()

    def _maybe_mark_restart_required(self) -> None:
        running = self.runner.is_running()
        if not running or not self.last_started_cfg:
            self.restart_needed = False
            self.restart_label.config(text="")
            self._update_restart_button_state()
            return

        if self._current_bus_cfg() != self.last_started_cfg:
            self.restart_needed = True
            self.restart_label.config(text="RESTART REQUIRED (bus settings changed)")
        else:
            self.restart_needed = False
            self.restart_label.config(text="")
        self._update_restart_button_state()

    def _stop_flag(self) -> None:
        request_stop(paths.stop_flag_path())
        self.status.config(text="Status: stop.flag set")

    def _start_runner(self) -> None:
        ensure_not_set(paths.stop_flag_path())
        self._write_control_immediate()
        try:
            self.runner.start(
                control_path=Path(self.control_path_picker.get()),
                telemetry_path=Path(self.telemetry_path_picker.get()),
                stop_path=Path(self.stop_path_picker.get()),
                extra_args=[
                    "--tx-debug",
                    "--can-monitor-log",
                    str(paths.can_monitor_path()),
                ],
            )
            self.last_started_cfg = self._current_bus_cfg(monitor_only_override=False)
            self.restart_needed = False
            self.restart_label.config(text="")
            self._update_restart_button_state()
            self.state_label.config(text="State: RUNNING", foreground="green")
            self.status.config(text="Status: runner started")
            if hasattr(self, "logger"):
                self.logger.info("Runner started")
        except Exception as exc:
            msg = str(exc)
            if hasattr(self, "logger"):
                self.logger.error(f"Start failed: {msg}")
            self.status.config(text=f"Start failed: {msg}")

    def _stop_runner(self) -> None:
        self.status.config(text="Status: stopping runner...")
        self._stop_runner_blocking()

    def _stop_runner_blocking(self) -> None:
        try:
            self.runner.stop()
        finally:
            self.state_label.config(text="State: STOPPED", foreground="red")
            self.status.config(text="Status: runner stopped")
            self.last_started_cfg = None
            self.restart_needed = False
            self.restart_label.config(text="")
            self._update_restart_button_state()
            if hasattr(self, "logger"):
                self.logger.info("Runner stopped")

    def _hard_kill_runner(self) -> None:
        self.status.config(text="Status: HARD KILL invoked")
        try:
            self.runner.force_kill()
            self.state_label.config(text="State: STOPPED", foreground="red")
            self.last_started_cfg = None
            self.restart_needed = False
            self.restart_label.config(text="")
            self._update_restart_button_state()
            if hasattr(self, "logger"):
                self.logger.warn("Runner force-killed")
        except Exception as exc:
            if hasattr(self, "logger"):
                self.logger.error(f"HARD KILL failed: {exc}")
            self.status.config(text=f"Status: HARD KILL failed: {exc}")

    def _restart_runner(self) -> None:
        self.status.config(text="Status: restarting runner...")
        self._stop_runner_blocking()
        self._start_runner()

    def _set_probe_status(self, text: str, state: str = "idle") -> None:
        style_map = {"ok": "ProbeOk.TLabel", "fail": "ProbeFail.TLabel", "idle": "ProbeIdle.TLabel"}
        style = style_map.get(state, "ProbeIdle.TLabel")
        if hasattr(self, "probe_label"):
            self.probe_label.config(text=text, style=style)

    def _probe_can(self) -> None:
        if self.runner.is_running():
            msg = "Probe blocked: runner running"
            self.status.config(text=msg)
            self._set_probe_status("Probe: blocked (runner)", "fail")
            if hasattr(self, "logger"):
                self.logger.warn(msg)
            return

        cfg = self._control_payload()
        backend = cfg.get("backend", "pythoncan")
        iface = cfg.get("iface", "virtual")
        channel = int(cfg.get("channel", 0))
        port = cfg.get("port", "")
        serial_baud = int(cfg.get("serial_baud", 115200))
        skip_bitrate = bool(cfg.get("skip_bitrate", False))
        bitrate = int(cfg.get("bitrate", 500000))

        def try_open(ch: int) -> None:
            bus = CanBus(
                iface=iface,
                channel=ch,
                bitrate=bitrate,
                backend=backend,
                port=port,
                serial_baud=serial_baud,
                slcan_skip_bitrate=skip_bitrate,
            )
            bus.open()
            bus.close()

        try:
            try_open(channel)
            port_label = f" port={port}" if port else ""
            self._set_probe_status(
                f"Probe: OK ({backend}/{iface} ch={channel} bitrate={bitrate}{port_label})",
                "ok",
            )
            self.status.config(text="Status: probe OK")
            if hasattr(self, "logger"):
                self.logger.info(
                    f"Probe OK backend={backend} iface={iface} ch={channel} "
                    f"bitrate={bitrate}{port_label}"
                )
            return
        except Exception as exc:
            last_err = str(exc)

        backend_error = "backend" in last_err.lower()

        if backend == "pythoncan" and iface == "gs_usb":
            for ch in range(0, 4):
                if ch == channel:
                    continue
                try:
                    try_open(ch)
                    self.channel.set(str(ch))
                    self._set_probe_status(f"Probe: OK (gs_usb ch={ch})", "ok")
                    self.status.config(text=f"Status: probe OK on ch={ch}")
                    if hasattr(self, "logger"):
                        self.logger.info(f"Probe OK on gs_usb channel {ch}")
                    return
                except Exception as exc:
                    last_err = str(exc)

        device_detected = False
        if backend == "pythoncan" and iface == "gs_usb":
            try:
                device_detected = probe_any_gsusb(verbose=False)
            except Exception:
                device_detected = False

        if backend == "slcan" and not port:
            msg = "Probe FAIL (slcan): missing port"
        elif backend_error:
            msg = f"Probe FAIL (USB backend): {last_err}"
        else:
            msg = f"Probe FAIL (open {backend}/{iface}): {last_err}"
        if backend == "pythoncan" and iface == "gs_usb":
            msg += f" | USB device detected: {'yes' if device_detected else 'no'}"
        self._set_probe_status("Probe: FAIL", "fail")
        self.status.config(text=msg)
        if hasattr(self, "logger"):
            self.logger.error(msg)

    def _selftest_async(self) -> None:
        threading.Thread(target=self._run_selftest, daemon=True).start()

    def _run_selftest(self) -> None:
        self.status.config(text="Status: selftest running...")
        if hasattr(self, "logger"):
            self.logger.info("Selftest starting (virtual)")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ecusim_ms.selftest"],
                capture_output=True,
                text=True,
                check=False,
            )
            ok = result.returncode == 0
            if hasattr(self, "logger"):
                if result.stdout:
                    self.logger.info(result.stdout.strip())
                if result.stderr:
                    self.logger.error(result.stderr.strip())
            if ok:
                self.status.config(text="Status: selftest PASS")
            else:
                self.status.config(text=f"Status: selftest FAIL (code {result.returncode})")
        except Exception as exc:
            if hasattr(self, "logger"):
                self.logger.error(f"Selftest failed: {exc}")
            self.status.config(text=f"Status: selftest failed: {exc}")

    def _start_monitor(self) -> None:
        ensure_not_set(paths.stop_flag_path())
        self._write_control_immediate()
        try:
            self.runner.start(
                control_path=Path(self.control_path_picker.get()),
                telemetry_path=Path(self.telemetry_path_picker.get()),
                stop_path=Path(self.stop_path_picker.get()),
                extra_args=["--monitor-only"],
            )
            self.last_started_cfg = self._current_bus_cfg(monitor_only_override=True)
            self.restart_needed = False
            self.restart_label.config(text="")
            self._update_restart_button_state()
            self.state_label.config(text="State: RUNNING (monitor-only)", foreground="green")
            self.status.config(text="Status: monitor-only started")
            if hasattr(self, "logger"):
                self.logger.info("Monitor-only started")
        except Exception as exc:
            msg = str(exc)
            if hasattr(self, "logger"):
                self.logger.error(f"Start failed: {msg}")
            self.status.config(text=f"Start failed: {msg}")

    def _control_payload(self) -> dict:
        def _safe_int(val, default=0):
            try:
                return int(val)
            except Exception:
                return default

        def _safe_str(val, default=""):
            try:
                text = str(val)
            except Exception:
                return default
            return text if text else default

        def _safe_float(val, default=0.0):
            try:
                return float(val)
            except Exception:
                return default

        bitrate_val = (
            _safe_int(self.bitrate_custom.get(), 500000)
            if self.bitrate_preset.get() == "custom"
            else _safe_int(self.bitrate_preset.get(), 500000)
        )
        hz_val = (
            _safe_float(self.hz_custom.get(), 50.0)
            if self.hz_preset.get() == "custom"
            else _safe_float(self.hz_preset.get(), 50.0)
        )

        return {
            "profile_id": "ms_simplified",
            "backend": _safe_str(self.backend.get(), "pythoncan"),
            "iface": self.iface.get() or "virtual",
            "channel": _safe_int(self.channel.get(), 0),
            "port": _safe_str(self.port.get(), ""),
            "serial_baud": _safe_int(self.serial_baud.get(), 115200),
            "skip_bitrate": bool(self.skip_bitrate_var.get()),
            "bitrate": bitrate_val,
            "hz": hz_val,
            "mode": self.mode.get() or "loop",
            "custom": self.custom_editor.get_values(),
            "hard_test": self.hard_panel.get_payload(),
        }

    def _write_control_immediate(self, status_text: str | None = None) -> None:
        if self._suppress_writes:
            return
        payload = self._control_payload()
        self.writer.write(payload)
        text = status_text or "Status: control.json saved"
        self.status.config(text=text)
        if hasattr(self, "logger"):
            self.logger.info(text)
        self._maybe_mark_restart_required()

    def _schedule_write(self, delay_ms: int = 200) -> None:
        if self._suppress_writes:
            return
        payload = self._control_payload()
        self.writer.write_debounced(payload, delay_ms=delay_ms)
        self.status.config(text="Status: control.json write queued")
        self._maybe_mark_restart_required()

    def _on_preset_change(self) -> None:
        self._schedule_write()
        self._update_mode_desc()

    def _update_mode_desc(self) -> None:
        desc = dict(MODE_OPTIONS).get(self.mode.get(), "")
        self.mode_desc.config(text=desc)

    def _apply_custom(self) -> None:
        self._write_control_immediate(status_text="Status: custom applied")

    def _reset_custom(self) -> None:
        self.custom_editor.reset_defaults()
        self._schedule_write()

    def _apply_hard_test(self) -> None:
        self._write_control_immediate(status_text="Status: hard_test applied")

    def _reset_hard_test(self) -> None:
        self.hard_panel.reset()
        self._schedule_write()

    def _start_polling(self) -> None:
        self._poll()

    def _poll(self) -> None:
        try:
            data = self.telemetry_reader.poll()
            if data:
                signals = data.get("signals", {})
                clamped = data.get("clamped", {})
                faults = data.get("faults", {})
                self.table.update_view(signals, clamped, faults)
                counters = data.get("counters", {}) or {}
                tx = counters.get("tx_frames", 0)
                txerr = counters.get("tx_errors", 0)
                rx = counters.get("rx_frames", 0)
                now_ts = time.time()
                if self._rate_prev is None:
                    self._rate_prev = {"ts": now_ts, "tx": tx, "rx": rx, "err": txerr}
                else:
                    dt = now_ts - self._rate_prev.get("ts", now_ts)
                    if dt > 0:
                        dtx = tx - self._rate_prev.get("tx", 0)
                        drx = rx - self._rate_prev.get("rx", 0)
                        derr = txerr - self._rate_prev.get("err", 0)
                        if hasattr(self, "act_tx_rate"):
                            self.act_tx_rate.config(text=f"tx/s={dtx/dt:.1f}")
                        if hasattr(self, "act_rx_rate"):
                            self.act_rx_rate.config(text=f"rx/s={drx/dt:.1f}")
                        if hasattr(self, "act_err_rate"):
                            self.act_err_rate.config(text=f"err/s={derr/dt:.1f}")
                    self._rate_prev = {"ts": now_ts, "tx": tx, "rx": rx, "err": txerr}
                if hasattr(self, "counter_tx"):
                    self.counter_tx.config(text=f"tx={tx}")
                if hasattr(self, "counter_txerr"):
                    self.counter_txerr.config(text=f"tx_err={txerr}")
                if hasattr(self, "counter_rx"):
                    self.counter_rx.config(text=f"rx={rx}")
                if hasattr(self, "telemetry_header"):
                    iface = data.get("iface", "?")
                    bitrate = data.get("bitrate", "?")
                    hz = data.get("hz", "?")
                    mode = data.get("mode", "?")
                    self.telemetry_header.config(
                        text=f"iface={iface} bitrate={bitrate} hz={hz} mode={mode}"
                    )
                if hasattr(self, "act_iface"):
                    iface = data.get("iface", "?")
                    bitrate = data.get("bitrate", "?")
                    state = counters.get("bus_state", "")
                    self.act_iface.config(text=f"iface={iface}")
                    self.act_bitrate.config(text=f"bitrate={bitrate}")
                    self.act_state.config(text=f"state={state}")
                if hasattr(self, "logger"):
                    mode = data.get("mode", "")
                    hz = data.get("hz", "")
                    self.logger.info(f"Telemetry update mode={mode} hz={hz}")
            if hasattr(self, "can_monitor"):
                self.can_monitor.poll()
            if hasattr(self, "can_activity_monitor"):
                self.can_activity_monitor.poll()
        except Exception:
            pass
        finally:
            self.master.after(200, self._poll)

    def _reset_can_stats(self) -> None:
        self._rate_prev = None
        if hasattr(self, "act_tx_rate"):
            self.act_tx_rate.config(text="tx/s=?")
        if hasattr(self, "act_rx_rate"):
            self.act_rx_rate.config(text="rx/s=?")
        if hasattr(self, "act_err_rate"):
            self.act_err_rate.config(text="err/s=?")


def main() -> None:
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.geometry("1280x850")
    root.minsize(1000, 700)
    _setup_style(root)
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
