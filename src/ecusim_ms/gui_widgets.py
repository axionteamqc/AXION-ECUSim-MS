"""Reusable Tkinter widgets for the ECU Simulator GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Iterable, Optional


class LabeledEntry(ttk.Frame):
    def __init__(self, master: tk.Misc, label: str, default: str = "", width: int = 12):
        super().__init__(master)
        ttk.Label(self, text=label).pack(side=tk.LEFT, padx=(0, 6))
        self.var = tk.StringVar(value=default)
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)


class LabeledCombo(ttk.Frame):
    def __init__(
        self, master: tk.Misc, label: str, values: Iterable[str], default: Optional[str] = None
    ):
        super().__init__(master)
        ttk.Label(self, text=label).pack(side=tk.LEFT, padx=(0, 6))
        self.var = tk.StringVar(value=default or "")
        self.combo = ttk.Combobox(
            self, textvariable=self.var, values=list(values), state="readonly"
        )
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        if default:
            self.combo.set(default)

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)
        self.combo.set(value)
