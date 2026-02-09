"""Simple GUI logger writing to a Tkinter Text widget."""

from __future__ import annotations

import datetime
import tkinter as tk
from tkinter import ttk


class GuiLogger(ttk.Frame):
    def __init__(self, master: tk.Misc, height: int = 8):
        super().__init__(master, padding=4)
        self.text = tk.Text(self, height=height, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _append(self, level: str, msg: str) -> None:
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {level}: {msg}\n"
            self.text.configure(state="normal")
            self.text.insert("end", line)
            self.text.see("end")
            self.text.configure(state="disabled")
        except Exception:
            return

    def info(self, msg: str) -> None:
        self._append("INFO", msg)

    def warn(self, msg: str) -> None:
        self._append("WARN", msg)

    def error(self, msg: str) -> None:
        self._append("ERROR", msg)
