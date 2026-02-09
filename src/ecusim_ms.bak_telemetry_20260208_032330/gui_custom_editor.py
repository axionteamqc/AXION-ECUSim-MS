"""Custom signal editor with sliders and numeric entries."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict

from ecusim_ms import models
from ecusim_ms.ms_signals import MS_SIGNAL_LIST


class CustomEditor(ttk.LabelFrame):
    def __init__(
        self,
        master: tk.Misc,
        defaults: Dict[str, float] | None = None,
        on_change: Callable[[str, float, bool], None] | None = None,
    ):
        super().__init__(master, text="Custom signals", padding=6)
        self.defaults = defaults or dict(models.DEFAULT_SIGNAL_VALUES)
        self.vars: Dict[str, tk.DoubleVar] = {}
        self._on_change = on_change

        label_units = {
            "map": "kPa",
            "clt": "deg F",
            "mat": "deg F",
            "egt1": "deg F",
            "VSS1": "m/s",
            "batt": "V",
            "AFR1": "AFR",
            "pw1": "ms",
            "pw2": "ms",
            "pwseq1": "ms",
            "adv_deg": "deg",
            "tc_retard": "deg",
        }

        common = [
            ("rpm", "RPM", 0, 8000, 50),
            ("tps", "TPS (%)", 0, 100, 1),
            ("map", "MAP (kPa)", 10, 250, 1),
            ("clt", "CLT (deg F)", 0, 250, 1),
            ("mat", "MAT (deg F)", 0, 250, 1),
            ("AFR1", "AFR1 (AFR)", 8, 20, 0.1),
            ("batt", "Batt (V)", 9, 16, 0.1),
            ("VSS1", "VSS1 (m/s)", 0, 80, 0.5),
        ]
        ttk.Label(self, text="Common").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        row = 1
        for key, label, lo, hi, res in common:
            row = self._add_slider_with_entry(row, key, label, lo, hi, res)

        ttk.Label(self, text="Advanced").grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(8, 4)
        )
        row += 1
        advanced_keys = [k for k in MS_SIGNAL_LIST if k not in [c[0] for c in common]]
        for idx, key in enumerate(advanced_keys):
            unit = label_units.get(key)
            label = f"{key}" if not unit else f"{key} ({unit})"
            self._add_entry(row + idx, key, label, width=14)

    def _add_slider_with_entry(
        self, row: int, key: str, label: str, lo: float, hi: float, res: float
    ) -> int:
        value_var = tk.DoubleVar(value=self.defaults.get(key, 0.0))
        slider_var = tk.DoubleVar(value=self._clamp(value_var.get(), lo, hi))
        self.vars[key] = value_var

        lbl = ttk.Label(self, text=label)
        lbl.grid(row=row, column=0, sticky="w")

        entry = ttk.Entry(self, textvariable=value_var, width=10)
        entry.grid(row=row, column=1, sticky="ew", padx=4)
        entry.bind(
            "<FocusOut>",
            lambda e, k=key, v=value_var, sv=slider_var: self._on_entry_commit(
                k, v, sv, lo, hi, entry
            ),
        )
        entry.bind(
            "<Return>",
            lambda e, k=key, v=value_var, sv=slider_var: self._on_entry_commit(
                k, v, sv, lo, hi, entry
            ),
        )

        scale = tk.Scale(
            self,
            from_=lo,
            to=hi,
            orient=tk.HORIZONTAL,
            resolution=res,
            variable=slider_var,
            length=180,
            command=lambda v, k=key, sv=slider_var, vv=value_var: self._on_slider_move(
                k, float(v), sv, vv, entry, lo, hi
            ),
        )
        scale.grid(row=row, column=2, sticky="ew", padx=4)

        # initial state
        self._update_entry_style(entry, value_var.get(), lo, hi)
        return row + 1

    def _add_entry(self, row: int, key: str, label: str, width: int = 10) -> None:
        var = tk.DoubleVar(value=self.defaults.get(key, 0.0))
        self.vars[key] = var
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w")
        entry = ttk.Entry(self, textvariable=var, width=width)
        entry.grid(row=row, column=1, sticky="ew", padx=4, pady=1)
        entry.bind(
            "<FocusOut>",
            lambda e, k=key, v=var: self._notify_change(k, v.get(), debounced=True),
        )
        entry.bind(
            "<Return>", lambda e, k=key, v=var: self._notify_change(k, v.get(), debounced=True)
        )

    def _notify_change(self, key: str, value: float, debounced: bool = False) -> None:
        if self._on_change:
            try:
                self._on_change(key, value, debounced)
            except Exception:
                pass

    @staticmethod
    def _clamp(val: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, val))

    def _on_slider_move(
        self,
        key: str,
        slider_val: float,
        slider_var: tk.DoubleVar,
        value_var: tk.DoubleVar,
        entry: ttk.Entry | None,
        lo: float,
        hi: float,
    ) -> None:
        slider_var.set(slider_val)
        value_var.set(slider_val)
        if entry is not None:
            self._update_entry_style(entry, slider_val, lo, hi)
        self._notify_change(key, slider_val, debounced=True)

    def _on_entry_commit(
        self,
        key: str,
        value_var: tk.DoubleVar,
        slider_var: tk.DoubleVar,
        lo: float,
        hi: float,
        entry: ttk.Entry,
    ) -> None:
        try:
            val = float(value_var.get())
        except Exception:
            val = 0.0
            value_var.set(val)
        slider_var.set(self._clamp(val, lo, hi))
        self._notify_change(key, val, debounced=True)
        self._update_entry_style(entry, val, lo, hi)

    def _update_entry_style(self, entry: ttk.Entry, val: float, lo: float, hi: float) -> None:
        try:
            if val < lo or val > hi:
                entry.configure(style="OutOfRange.TEntry")
            else:
                entry.configure(style="TEntry")
        except Exception:
            pass

    def get_values(self) -> Dict[str, float]:
        values: Dict[str, float] = {}
        for key, var in self.vars.items():
            try:
                values[key] = float(var.get())
            except Exception:
                values[key] = 0.0
        return values

    def set_defaults(self, defaults: Dict[str, float]) -> None:
        """Update defaults and set current values accordingly."""
        if defaults is None:
            return
        self.defaults = dict(defaults)
        for key, var in self.vars.items():
            try:
                var.set(float(self.defaults.get(key, 0.0)))
            except Exception:
                var.set(0.0)

    def reset_defaults(self) -> None:
        for key, var in self.vars.items():
            var.set(self.defaults.get(key, 0.0))
