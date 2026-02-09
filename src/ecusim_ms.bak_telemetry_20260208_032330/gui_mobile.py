"""Mobile-first Tkinter UI with full/minimal toggle."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Iterable

from ecusim_ms.ms_signals import MS_SIGNAL_LIST
from ecusim_ms.ui_backend import UiBackend


class MobileApp(ttk.Frame):
    def __init__(self, master: tk.Tk, controller: UiBackend) -> None:
        super().__init__(master, padding=8)
        self.controller = controller
        self.master = master

        self.grid(row=0, column=0, sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        self.view_mode = "minimal"
        self._full_built = False
        self._schemas = {s.name: s for s in self.controller.get_custom_signals_schema()}
        self._mode_options = self.controller.get_available_modes()
        default_mode = self._mode_options[0] if self._mode_options else "idle"
        current_mode = self.controller.get_status().get("mode", default_mode)
        self.mode_var = tk.StringVar(value=current_mode)
        self.status_var = tk.StringVar(value="")
        self._running = False
        self.custom_vars = {}
        for key in MS_SIGNAL_LIST:
            schema = self._schemas.get(key)
            default_value = schema.default_value if schema else 0.0
            self.custom_vars[key] = tk.StringVar(value=str(default_value))
        self.custom_enabled: Dict[str, tk.BooleanVar] = {
            key: tk.BooleanVar(value=True) for key in MS_SIGNAL_LIST
        }
        self._signal_rows: Dict[str, Dict[str, object]] = {}
        self._filter_var = tk.StringVar(value="")
        self.mode_var.trace_add(
            "write",
            lambda *_: self.controller.set_mode(self.mode_var.get()),
        )

        self._build_layout()
        self._update_status()

    def _build_layout(self) -> None:
        toggle = ttk.Frame(self)
        toggle.grid(row=0, column=0, sticky="ew")
        toggle.columnconfigure(0, weight=1)
        self.toggle_btn = ttk.Button(
            toggle,
            text="Visuel complet",
            command=self._toggle_view,
        )
        self.toggle_btn.grid(row=0, column=0, sticky="e")

        self._build_scroll()
        self._build_views()
        self._show_view(self.view_mode)

    def _build_scroll(self) -> None:
        self.container = ttk.Frame(self)
        self.container.grid(row=1, column=0, sticky="nsew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self.container, highlightthickness=0)
        self.vscroll = ttk.Scrollbar(self.container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)

        self.body = ttk.Frame(self.canvas, padding=6)
        self.body_id = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        def _on_frame_configure(_event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def _on_canvas_configure(event):
            self.canvas.itemconfigure(self.body_id, width=event.width)

        self.body.bind("<Configure>", _on_frame_configure)
        self.canvas.bind("<Configure>", _on_canvas_configure)

    def _build_views(self) -> None:
        self.full_frame = ttk.Frame(self.body)
        self.min_frame = ttk.Frame(self.body)
        self.full_frame.columnconfigure(0, weight=1)
        self.min_frame.columnconfigure(0, weight=1)

        self._build_min_view(self.min_frame)

    def _ensure_full_view(self) -> None:
        if self._full_built:
            return
        self._build_full_view(self.full_frame)
        self._full_built = True

    def _toggle_view(self) -> None:
        if self.view_mode == "full":
            self.view_mode = "minimal"
        else:
            self.view_mode = "full"
        self._show_view(self.view_mode)

    def _show_view(self, view: str) -> None:
        if view == "full":
            self._ensure_full_view()
            self.min_frame.grid_remove()
            self.full_frame.grid(row=0, column=0, sticky="nsew")
            self.toggle_btn.config(text="Visuel minimal")
        else:
            self.full_frame.grid_remove()
            self.min_frame.grid(row=0, column=0, sticky="nsew")
            self.toggle_btn.config(text="Visuel complet")

    def _build_title(self, parent: ttk.Frame, text: str) -> None:
        ttk.Label(parent, text=text, style="Title.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

    def _build_connection_full(self, parent: ttk.Frame, start_row: int) -> int:
        frame = ttk.LabelFrame(parent, text="Connection", padding=6)
        frame.grid(row=start_row, column=0, sticky="ew", pady=(0, 6))
        frame.columnconfigure(1, weight=1)

        def add_row(row: int, label: str, value: str) -> None:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
            entry = ttk.Entry(frame)
            entry.insert(0, value)
            entry.configure(state="readonly")
            entry.grid(row=row, column=1, sticky="ew", padx=4, pady=2)

        add_row(0, "Backend", str(self.controller.backend))
        add_row(1, "Iface", str(self.controller.iface))
        add_row(2, "Port", str(self.controller.port))
        add_row(3, "Channel", str(self.controller.channel))
        add_row(4, "Bitrate", str(self.controller.bitrate))
        add_row(5, "Hz", str(self.controller.hz))
        add_row(6, "Serial baud", str(self.controller.serial_baud))
        add_row(7, "Skip bitrate", str(self.controller.skip_bitrate))
        return start_row + 1

    def _build_mode(self, parent: ttk.Frame, start_row: int) -> int:
        frame = ttk.LabelFrame(parent, text="Mode", padding=6)
        frame.grid(row=start_row, column=0, sticky="ew", pady=(0, 6))
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Mode").grid(row=0, column=0, sticky="w")
        mode_box = ttk.Combobox(
            frame,
            textvariable=self.mode_var,
            values=self._mode_options,
        )
        mode_box.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        return start_row + 1

    def _build_actions(self, parent: ttk.Frame, start_row: int) -> int:
        frame = ttk.Frame(parent)
        frame.grid(row=start_row, column=0, sticky="ew", pady=(0, 6))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        ttk.Button(
            frame,
            text="Start",
            style="Big.TButton",
            command=self._on_start,
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=6)
        ttk.Button(
            frame,
            text="Stop",
            style="Big.TButton",
            command=self._on_stop,
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=6)
        return start_row + 1

    def _build_custom_full(self, parent: ttk.Frame, start_row: int) -> int:
        frame = ttk.LabelFrame(parent, text="Custom Signals", padding=6)
        frame.grid(row=start_row, column=0, sticky="ew", pady=(0, 6))
        frame.columnconfigure(1, weight=1)

        row = 0
        for key in MS_SIGNAL_LIST:
            ttk.Label(frame, text=key).grid(row=row, column=0, sticky="w", pady=1)
            ttk.Entry(frame, textvariable=self.custom_vars[key]).grid(
                row=row, column=1, sticky="ew", padx=4
            )
            row += 1

        ttk.Button(frame, text="Apply Custom", command=self._apply_custom_all).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(6, 2)
        )
        return start_row + 1

    def _build_custom_min(self, parent: ttk.Frame, start_row: int) -> int:
        frame = ttk.LabelFrame(parent, text="Custom signals", padding=6)
        frame.grid(row=start_row, column=0, sticky="ew", pady=(0, 6))
        frame.columnconfigure(0, weight=1)

        filter_frame = ttk.Frame(frame)
        filter_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        filter_frame.columnconfigure(1, weight=1)
        ttk.Label(filter_frame, text="Filter signals").grid(row=0, column=0, sticky="w")
        filter_entry = ttk.Entry(filter_frame, textvariable=self._filter_var)
        filter_entry.grid(row=0, column=1, sticky="ew", padx=4)

        self._filter_var.trace_add("write", lambda *_: self._apply_filter())

        list_container = ttk.Frame(frame)
        list_container.grid(row=1, column=0, sticky="ew")
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(list_container, highlightthickness=0, height=320)
        vscroll = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=canvas.yview,
        )
        canvas.configure(yscrollcommand=vscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")

        body = ttk.Frame(canvas)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_frame_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfigure(body_id, width=event.width)

        body.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        for idx, key in enumerate(MS_SIGNAL_LIST):
            item = ttk.Frame(body, padding=(4, 2))
            item.grid(row=idx, column=0, sticky="ew", pady=(0, 6))
            item.columnconfigure(0, weight=1)
            item.columnconfigure(1, weight=0)

            name_label = ttk.Label(item, text=key, wraplength=260)
            name_label.grid(row=0, column=0, sticky="w")

            meta_label = ttk.Label(item, text="", wraplength=260)
            meta_label.grid(row=1, column=0, sticky="w", pady=(0, 2))

            entry = ttk.Entry(item, textvariable=self.custom_vars[key])
            entry.grid(row=2, column=0, sticky="ew", padx=(0, 6))
            entry.bind("<Return>", lambda _e, k=key: self._apply_custom_keys([k]))
            entry.bind("<FocusOut>", lambda _e, k=key: self._apply_custom_keys([k]))

            toggle = ttk.Checkbutton(
                item,
                text="Enable",
                variable=self.custom_enabled[key],
            )
            toggle.grid(row=2, column=1, sticky="e")

            self._signal_rows[key] = {
                "frame": item,
                "name": name_label,
                "meta": meta_label,
                "entry": entry,
                "toggle": toggle,
            }
            self._update_signal_row(key)

        return start_row + 1

    def _build_status(self, parent: ttk.Frame, start_row: int) -> int:
        status = ttk.Label(
            parent,
            textvariable=self.status_var,
            wraplength=300,
            justify="left",
        )
        status.grid(row=start_row, column=0, sticky="w")
        return start_row + 1

    def _build_full_view(self, parent: ttk.Frame) -> None:
        row = 0
        self._build_title(parent, "ECU Simulator (Full)")
        row += 1
        row = self._build_connection_full(parent, row)
        row = self._build_mode(parent, row)
        row = self._build_actions(parent, row)
        row = self._build_custom_full(parent, row)
        self._build_status(parent, row)

    def _build_min_view(self, parent: ttk.Frame) -> None:
        row = 0
        self._build_title(parent, "ECU Simulator (Minimal)")
        row += 1
        row = self._build_mode(parent, row)
        row = self._build_custom_min(parent, row)
        row = self._build_actions(parent, row)
        self._build_status(parent, row)

    def _apply_custom_all(self) -> None:
        self._apply_custom_keys(MS_SIGNAL_LIST)

    def _apply_custom_quick(self) -> None:
        self._apply_custom_keys(["map", "rpm", "tps"])

    def _apply_custom_keys(self, keys: Iterable[str]) -> None:
        updates = {}
        for key in keys:
            if key not in self.custom_vars:
                continue
            enabled = True
            if key in self.custom_enabled:
                enabled = bool(self.custom_enabled.get(key).get())
            updates[key] = {
                "value": self.custom_vars[key].get(),
                "enabled": enabled,
            }
        try:
            self.controller.apply_custom_signal_updates(updates)
            self._update_status("custom updated")
        except Exception as exc:
            self._update_status(f"custom update failed: {exc}")

    def _on_start(self) -> None:
        try:
            self.controller.start()
            self._running = True
            self._update_status("running")
        except Exception as exc:
            self._update_status(f"start failed: {exc}")

    def _on_stop(self) -> None:
        try:
            self.controller.stop()
            self._running = False
            self._update_status("stopped")
        except Exception as exc:
            self._update_status(f"stop failed: {exc}")

    def _signal_meta_text(self, key: str) -> str:
        schema = self._schemas.get(key)
        if schema is None:
            return "CAN ID: n/a | Period: n/a"
        if schema.frame_id is not None:
            fid_text = f"0x{int(schema.frame_id):X}"
        else:
            fid_text = "n/a"
        if schema.default_period_ms > 0:
            period_text = f"{schema.default_period_ms:.1f} ms"
        else:
            period_text = "n/a"
        return f"CAN ID: {fid_text} | Period: {period_text}"

    def _update_signal_row(self, key: str) -> None:
        row = self._signal_rows.get(key)
        if not row:
            return
        meta_label = row.get("meta")
        if isinstance(meta_label, ttk.Label):
            meta_label.config(text=self._signal_meta_text(key))

    def _apply_filter(self) -> None:
        query = (self._filter_var.get() or "").strip().lower()
        for key, row in self._signal_rows.items():
            frame = row.get("frame")
            if not isinstance(frame, ttk.Frame):
                continue
            if not query or query in key.lower():
                frame.grid()
            else:
                frame.grid_remove()

    def _update_status(self, msg: str | None = None) -> None:
        status = self.controller.get_status()
        self._running = bool(status.get("running", False))
        state = "running" if self._running else "stopped"
        backend = status.get("backend", "?")
        port = status.get("port", "auto")
        bitrate = status.get("bitrate", "?")
        suffix = f" | {msg}" if msg else ""
        self.status_var.set(f"{state} | backend={backend} port={port} bitrate={bitrate}{suffix}")


def _setup_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure("Title.TLabel", font=("Segoe UI", 16, "bold"))
    style.configure("TLabel", font=("Segoe UI", 12))
    style.configure("TEntry", font=("Segoe UI", 12))
    style.configure("TButton", font=("Segoe UI", 12), padding=6)
    style.configure("Big.TButton", font=("Segoe UI", 14, "bold"), padding=10)


def main() -> None:
    root = tk.Tk()
    root.title("ECU Simulator - Mobile")
    root.geometry("380x720")
    root.minsize(320, 480)
    _setup_style(root)
    MobileApp(root, UiBackend())
    root.mainloop()


if __name__ == "__main__":
    main()
