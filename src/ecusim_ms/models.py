"""Data models for control and telemetry I/O."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, Optional

from ecusim_ms.ms_signals import MS_SIGNAL_LIST

DEFAULT_SIGNAL_VALUES: Dict[str, float] = {name: 0.0 for name in MS_SIGNAL_LIST}
DEFAULT_SIGNAL_VALUES.update(
    {
        "rpm": 900.0,
        "map": 45.0,
        "tps": 2.0,
        "clt": 185.0,
        "pw1": 2.5,
        "pw2": 2.5,
        "mat": 86.0,
        "adv_deg": 10.0,
        "afrtgt1": 14.7,
        "AFR1": 14.7,
        "egocor1": 100.0,
        "egt1": 500.0,
        "pwseq1": 2.5,
        "batt": 12.5,
        "sensors1": 0.0,
        "sensors2": 0.0,
        "knk_rtd": 0.0,
        "VSS1": 0.0,
        "tc_retard": 0.0,
        "launch_timing": 0.0,
    }
)


@dataclass
class HardTestConfig:
    """Placeholder for deterministic stress test profile."""

    note: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlConfig:
    profile_id: str = "ms_simplified"
    backend: str = "pythoncan"
    iface: str = "gs_usb"
    channel: int = 0
    port: str = ""
    serial_baud: int = 115200
    skip_bitrate: bool = False
    bitrate: int = 500_000
    hz: float = 50.0
    mode: str = "loop"
    custom: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SIGNAL_VALUES))
    hard_test: HardTestConfig = field(default_factory=HardTestConfig)


@dataclass
class TelemetrySnapshot:
    ts: float = 0.0
    iface: str = ""
    bitrate: int = 0
    hz: float = 0.0
    mode: str = ""
    last_error: Optional[str] = None
    signals: Dict[str, float] = field(
        default_factory=lambda: {name: 0.0 for name in MS_SIGNAL_LIST}
    )
    signal_meta: Dict[str, Any] = field(default_factory=dict)
    clamped: Dict[str, Any] = field(default_factory=dict)
    faults: Dict[str, Any] = field(default_factory=dict)
    counters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        if is_dataclass(self):
            return asdict(self)
        raise TypeError("TelemetrySnapshot must be a dataclass instance")
