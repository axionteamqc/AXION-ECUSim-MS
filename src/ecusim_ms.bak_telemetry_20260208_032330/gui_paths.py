"""Path picker helpers for the GUI."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, ttk


class PathPicker(ttk.Frame):
    def __init__(self, master: tk.Misc, label: str, default: str):
        super().__init__(master)
        ttk.Label(self, text=label).pack(side=tk.LEFT, padx=(0, 6))
        self.var = tk.StringVar(value=default)
        entry = ttk.Entry(self, textvariable=self.var, width=50)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(self, text="Browse", command=self._browse).pack(side=tk.LEFT)

    def _browse(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self.var.set(path)

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)


def open_folder(folder: str) -> None:
    try:
        os.startfile(folder)
    except Exception:
        return
