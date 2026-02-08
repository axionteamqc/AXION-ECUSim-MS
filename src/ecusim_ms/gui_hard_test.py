"""Hard test configuration panel (GUI only)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict

PRESETS = ["SPIKE", "JITTER", "RAMP", "CORRUPT"]


class HardTestPanel(ttk.LabelFrame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, text="Hard test (pack 03 runtime)", padding=6)
        ttk.Label(self, text="Preset").grid(row=0, column=0, sticky="w")
        self.preset_var = tk.StringVar(value=PRESETS[0])
        self.preset_combo = ttk.Combobox(
            self, textvariable=self.preset_var, values=PRESETS, state="readonly"
        )
        self.preset_combo.grid(row=0, column=1, sticky="ew", pady=2, padx=4)

        ttk.Label(self, text="Intensity (0-100)").grid(row=1, column=0, sticky="w")
        self.intensity_var = tk.DoubleVar(value=50.0)
        self.intensity_scale = tk.Scale(
            self,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            resolution=1,
            variable=self.intensity_var,
            length=180,
        )
        self.intensity_scale.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        self.grid_columnconfigure(1, weight=1)

    def get_payload(self) -> Dict[str, object]:
        return {"preset": self.preset_var.get(), "intensity": float(self.intensity_var.get())}

    def reset(self) -> None:
        self.preset_var.set(PRESETS[0])
        self.intensity_var.set(50.0)
