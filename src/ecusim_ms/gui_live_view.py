"""Live telemetry view using ttk.Treeview."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Iterable


class LiveView(ttk.Frame):
    def __init__(self, master: tk.Misc, signals: Iterable[str]):
        super().__init__(master, padding=6)
        self.tree = ttk.Treeview(
            self, columns=("signal", "value", "flag"), show="headings", height=20
        )
        self.tree.heading("signal", text="Signal")
        self.tree.heading("value", text="Value")
        self.tree.heading("flag", text="Flag")
        self.tree.column("signal", width=180, anchor="w")
        self.tree.column("value", width=140, anchor="w")
        self.tree.column("flag", width=80, anchor="w")
        self.tree_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.tree_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree_scroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        for sig in signals:
            self.tree.insert("", "end", iid=sig, values=(sig, "?", ""))

    def update_view(
        self, values: Dict[str, float], clamped: Dict[str, Dict[str, object]] = None, faults=None
    ) -> None:
        clamped = clamped or {}
        fault_set = set(faults or [])
        for sig in self.tree.get_children():
            val = values.get(sig, None)
            flag = ""
            if sig in clamped:
                flag = "CLAMP"
            elif sig in fault_set:
                flag = "ERR"
            if val is None:
                self.tree.set(sig, "value", "?")
            else:
                try:
                    self.tree.set(sig, "value", f"{float(val):.2f}")
                except Exception:
                    self.tree.set(sig, "value", str(val))
            self.tree.set(sig, "flag", flag)
