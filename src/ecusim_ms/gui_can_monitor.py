"""GUI component to tail can_monitor.jsonl with basic filtering."""

from __future__ import annotations

import json
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk


class CanMonitorView(ttk.Frame):
    def __init__(self, master: tk.Misc, log_path: Path, poll_ms: int = 200) -> None:
        super().__init__(master)
        self.log_path = Path(log_path)
        self.poll_ms = poll_ms
        self._offset = 0
        self._file_mtime = 0.0

        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, sticky="w")

        self.show_rx = tk.BooleanVar(value=False)
        self.show_tx_ok = tk.BooleanVar(value=False)
        self.show_errors = tk.BooleanVar(value=True)

        ttk.Checkbutton(controls, text="Show RX", variable=self.show_rx).grid(
            row=0, column=0, padx=(0, 6)
        )
        ttk.Checkbutton(controls, text="Show TX OK", variable=self.show_tx_ok).grid(
            row=0, column=1, padx=(0, 6)
        )
        ttk.Checkbutton(controls, text="Show Errors/State", variable=self.show_errors).grid(
            row=0, column=2, padx=(0, 6)
        )
        ttk.Button(controls, text="Open Log", command=self._open_log).grid(
            row=0, column=3, padx=(10, 0)
        )

        text_frame = ttk.Frame(self)
        text_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.text = tk.Text(text_frame, wrap="none", height=20)
        self.text.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=yscroll.set, state="disabled")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def _open_log(self) -> None:
        try:
            import os

            if self.log_path.exists():
                os.startfile(self.log_path)  # type: ignore[attr-defined]
            else:
                os.startfile(self.log_path.parent)  # type: ignore[attr-defined]
        except Exception:
            pass

    def _append_line(self, line: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", line + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _format_event(self, evt: dict) -> str | None:
        etype = evt.get("type", "")
        ts = evt.get("ts", time.time())
        ts_s = time.strftime("%H:%M:%S", time.localtime(ts))
        if etype == "rx":
            if not self.show_rx.get():
                return None
            return f"[{ts_s}] RX id=0x{evt.get('id', 0):X} dlc={evt.get('dlc', '')} data={evt.get('data_hex','')} err={evt.get('is_error', False)}"
        if etype == "tx_ok":
            if not self.show_tx_ok.get():
                return None
            return f"[{ts_s}] TX_OK id=0x{evt.get('id', 0):X} tx={evt.get('tx_frames','')}"
        if etype in {
            "tx_fail",
            "bus_state",
            "reopen_begin",
            "reopen_ok",
            "reopen_fail",
            "start",
            "stop",
            "rate",
        }:
            if not self.show_errors.get():
                return None
            if etype == "tx_fail":
                return f"[{ts_s}] TX_FAIL id=0x{evt.get('id',0):X} consec={evt.get('consec_fail','?')} err={evt.get('error','')}"
            if etype == "bus_state":
                return f"[{ts_s}] BUS_STATE {evt.get('state','')}"
            if etype.startswith("reopen"):
                return f"[{ts_s}] {etype.upper()} {evt.get('error','')}"
            if etype == "start":
                return f"[{ts_s}] START iface={evt.get('iface','')} bitrate={evt.get('bitrate','')} mode={evt.get('mode','')}"
            if etype == "stop":
                return f"[{ts_s}] STOP"
            if etype == "rate":
                return (
                    f"[{ts_s}] RATE tx/s={evt.get('tx_per_s',0):.1f} "
                    f"rx/s={evt.get('rx_per_s',0):.1f} err/s={evt.get('err_per_s',0):.1f} state={evt.get('state','')}"
                )
        return None

    def poll(self) -> None:
        try:
            if not self.log_path.exists():
                return
            mtime = self.log_path.stat().st_mtime
            if mtime < self._file_mtime:
                self._offset = 0
            self._file_mtime = mtime
            with self.log_path.open("r", encoding="utf-8") as handle:
                handle.seek(self._offset)
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except Exception:
                        continue
                    formatted = self._format_event(evt)
                    if formatted:
                        self._append_line(formatted)
                self._offset = handle.tell()
        except Exception:
            pass
