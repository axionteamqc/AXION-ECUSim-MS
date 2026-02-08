"""CAN bus abstraction over selectable transport backends."""

from __future__ import annotations

from typing import Optional

import can

from ecusim_ms.transport import CanTransport, PythonCanTransport, SlcanSerialTransport


class CanBus:
    def __init__(
        self,
        iface: str,
        channel: int,
        bitrate: int,
        backend: str = "pythoncan",
        port: str | None = None,
        serial_baud: int | None = None,
        slcan_skip_bitrate: bool = False,
    ) -> None:
        self.iface = iface
        self.channel = channel
        self.bitrate = bitrate
        self.backend = backend or "pythoncan"
        self.port = port
        self.serial_baud = serial_baud or 115200
        self.slcan_skip_bitrate = slcan_skip_bitrate
        self.transport: Optional[CanTransport] = None
        self.tx_errors: int = 0

    def open(self) -> None:
        if self.transport is not None:
            return
        if self.backend == "pythoncan":
            self.transport = PythonCanTransport(self.iface, self.channel, self.bitrate)
        elif self.backend == "slcan":
            if not self.port:
                raise RuntimeError("SLCAN backend requires --port")
            self.transport = SlcanSerialTransport(
                self.port,
                self.bitrate,
                serial_baud=self.serial_baud,
                skip_bitrate=self.slcan_skip_bitrate,
            )
        else:
            raise ValueError(f"Unsupported CAN backend: {self.backend}")
        self.transport.open()
        self.tx_errors = 0

    def send(self, frame_id: int, payload: bytes, is_extended: bool = False) -> bool:
        if self.transport is None:
            raise RuntimeError("CAN bus is not open")
        ok = self.transport.send(frame_id, payload, is_extended=is_extended)
        self.tx_errors = getattr(self.transport, "tx_errors", self.tx_errors)
        return ok

    def recv(self, timeout_s: float | None = 1.0) -> Optional[can.Message]:
        if self.transport is None:
            return None
        return self.transport.recv(timeout_s=timeout_s)

    def close(self) -> None:
        if self.transport is None:
            return
        try:
            self.transport.close()
        except Exception:
            pass
        self.transport = None

    def get_state(self) -> str | None:
        if self.transport is None:
            return None
        try:
            return self.transport.get_state()
        except Exception:
            return None
