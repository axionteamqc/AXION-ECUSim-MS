"""Transport backends for CAN send/recv."""

from __future__ import annotations

import logging
from typing import Optional

import can
from ecusim_ms.transports.termux_libusb_slcan import TermuxUsbSlcan

SLCAN_BITRATE_MAP = {
    10_000: "S0",
    20_000: "S1",
    50_000: "S2",
    100_000: "S3",
    125_000: "S4",
    250_000: "S5",
    500_000: "S6",
    800_000: "S7",
    1_000_000: "S8",
}


def _state_to_str(state: object | None) -> str | None:
    if state is None:
        return None
    if hasattr(state, "name"):
        return str(getattr(state, "name", ""))
    return str(state)


class CanTransport:
    """Minimal transport interface."""

    tx_errors: int = 0

    def open(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def send(self, frame_id: int, payload: bytes, is_extended: bool = False) -> bool:
        raise NotImplementedError

    def recv(self, timeout_s: float | None = 1.0) -> Optional[can.Message]:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def get_state(self) -> str | None:
        return None


class TermuxUsbSlcanTransport(CanTransport):
    """Android/Termux USB backend using libusb + SLCAN ASCII."""

    def __init__(self, bitrate: int = 500_000) -> None:
        self.bitrate = bitrate
        self.dev: Optional[TermuxUsbSlcan] = None
        self.tx_errors = 0

    def open(self) -> None:
        import os
        if self.dev is not None:
            return
        if not os.environ.get("TERMUX_USB_FD"):
            raise RuntimeError("TERMUX_USB_FD not set. Launch via: termux-usb -r -E -e ... <device>")
        self.dev = TermuxUsbSlcan()
        cmd = SLCAN_BITRATE_MAP.get(int(self.bitrate), "S6")
        self.dev.init_slcan(cmd)

    def send(self, frame_id: int, payload: bytes, is_extended: bool = False) -> bool:
        if self.dev is None:
            raise RuntimeError("termux-usb device not open")
        dlc = len(payload)
        if is_extended:
            frame = "T%08X%1X%s\r" % (frame_id, dlc, payload.hex().upper())
        else:
            frame = "t%03X%1X%s\r" % (frame_id & 0x7FF, dlc, payload.hex().upper())
        try:
            self.dev.write_ascii(frame)
            return True
        except Exception:
            self.tx_errors += 1
            raise

    def recv(self, timeout_s: float | None = 1.0) -> Optional[can.Message]:
        # Not implemented yet (requires parsing SLCAN receive frames)
        return None

    def close(self) -> None:
        if self.dev is not None:
            self.dev.close()
            self.dev = None

    def get_state(self) -> str | None:
        return "OPEN" if self.dev is not None else "CLOSED"


class PythonCanTransport(CanTransport):
    """Python-can backend (gs_usb/virtual)."""

    def __init__(self, iface: str, channel: int, bitrate: int) -> None:
        self.iface = iface
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional[can.BusABC] = None
        self.termux_usb = None  # Termux USB/libusb SLCAN transport
        self.tx_errors = 0

    def open(self) -> None:
        if self.bus is not None:
            return

        if self.iface == "gs_usb":
            try:
                from ecusim_ms.usb_backend import ensure_backend

                backend = ensure_backend(verbose=False)
                logging.info("USB backend forced OK: %s", backend)
            except Exception as exc:
                raise RuntimeError(
                    "gs_usb backend unavailable: "
                    f"{exc}. Install libusb-package/pyusb "
                    "and ensure drivers are present. "
                    "On Windows, install driver via Zadig (libusbK)."
                ) from exc
            try:
                # --- Termux Android USB (libusb) backend ---
                if getattr(self, "backend", None) == "termux-usb":
                    import os
                    if not os.environ.get("TERMUX_USB_FD"):
                        raise RuntimeError("TERMUX_USB_FD not set. Launch via: termux-usb -r -E -e ... <device>")
                    self.termux_usb = TermuxUsbSlcan()
                    br = int(getattr(self, "bitrate", 500000) or 500000)
                    br_map = {10000:"S0",20000:"S1",50000:"S2",100000:"S3",125000:"S4",250000:"S5",500000:"S6",800000:"S7",1000000:"S8"}
                    self.termux_usb.init_slcan(br_map.get(br, "S6"))
                    self.bus = None
                    return
                # ----------------------------------------------

                self.bus = can.Bus(
                    interface="gs_usb",
                    channel=self.channel,
                    bitrate=self.bitrate,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to open gs_usb channel={self.channel} "
                    f"bitrate={self.bitrate}: {exc}. "
                    "On Windows, install driver via Zadig (libusbK)."
                ) from exc
        elif self.iface == "virtual":
            try:
                self.bus = can.Bus(
                    interface="virtual",
                    channel=self.channel,
                    bitrate=self.bitrate,
                )
                return
            except Exception:
                try:
                    self.bus = can.Bus(interface="virtual", channel=self.channel)
                except Exception as exc:
                    raise RuntimeError(
                        "Failed to open virtual CAN bus (with bitrate then without). "
                        f"Last error: {exc}"
                    ) from exc
        else:
            raise ValueError(f"Unsupported CAN interface: {self.iface}")

    def send(self, frame_id: int, payload: bytes, is_extended: bool = False) -> bool:
        if self.bus is None:
            raise RuntimeError("CAN bus is not open")
        msg = can.Message(
            arbitration_id=frame_id,
            is_extended_id=is_extended,
            data=payload,
        )
        try:
            if getattr(self, "backend", None) == "termux-usb":
                if not self.termux_usb:
                    raise RuntimeError("termux-usb transport not initialized")
                arbid = msg.arbitration_id
                data = msg.data or b""
                dlc = len(data)
                if getattr(msg, "is_extended_id", False):
                    frame = "T%08X%1X%s\r" % (arbid, dlc, data.hex().upper())
                else:
                    frame = "t%03X%1X%s\r" % (arbid & 0x7FF, dlc, data.hex().upper())
                self.termux_usb.write_ascii(frame)
                return True
            

            self.bus.send(msg)
            return True
        except can.CanError as exc:
            self.tx_errors += 1
            logging.warning(
                "CAN send failed (iface=%s id=0x%x): %s",
                self.iface,
                frame_id,
                exc,
            )
            return False

    def recv(self, timeout_s: float | None = 1.0) -> Optional[can.Message]:
        if self.bus is None:
            return None
        try:
            return self.bus.recv(timeout=timeout_s)
        except can.CanError as exc:
            logging.warning("CAN recv failed (iface=%s): %s", self.iface, exc)
            return None

    def close(self) -> None:
        if self.bus is None:
            return
        try:
            shutdown = getattr(self.bus, "shutdown", None)
            if callable(shutdown):
                shutdown()
        except Exception:
            pass
        try:
            self.bus.close()
        except Exception:
            pass
        self.bus = None

    def get_state(self) -> str | None:
        if self.bus is None:
            return None
        try:
            return _state_to_str(getattr(self.bus, "state", None))
        except Exception:
            return None


class SlcanSerialTransport(CanTransport):
    """Lawicel SLCAN transport over serial (pyserial)."""

    def __init__(
        self,
        port: str,
        bitrate: int,
        serial_baud: int = 115200,
        skip_bitrate: bool = False,
    ) -> None:
        self.port = port
        self.bitrate = bitrate
        self.serial_baud = serial_baud
        self.skip_bitrate = skip_bitrate
        self.ser = None
        self.tx_errors = 0

    @staticmethod
    def format_frame(frame_id: int, payload: bytes, is_extended: bool = False) -> str:
        payload = payload or b""
        dlc = len(payload)
        if dlc > 8:
            raise ValueError(f"SLCAN payload too long: {dlc}")
        if is_extended:
            if frame_id > 0x1FFFFFFF or frame_id < 0:
                raise ValueError(f"SLCAN extended ID out of range: {frame_id}")
            cmd = "T"
            id_hex = f"{frame_id:08X}"
        else:
            if frame_id > 0x7FF or frame_id < 0:
                raise ValueError(f"SLCAN standard ID out of range: {frame_id}")
            cmd = "t"
            id_hex = f"{frame_id:03X}"
        data_hex = payload.hex().upper()
        return f"{cmd}{id_hex}{dlc:X}{data_hex}"

    def _read_response(self, timeout_s: float = 0.05) -> bytes:
        if self.ser is None:
            return b""
        prev_timeout = getattr(self.ser, "timeout", None)
        try:
            self.ser.timeout = timeout_s
            return self.ser.read_until(b"\r", size=32)
        except Exception:
            return b""
        finally:
            try:
                self.ser.timeout = prev_timeout
            except Exception:
                pass

    def _write_cmd(self, cmd: str, expect_ack: bool = True) -> None:
        if self.ser is None:
            raise RuntimeError("Serial port not open")
        payload = cmd.encode("ascii") + b"\r"
        self.ser.write(payload)
        self.ser.flush()
        resp = self._read_response(0.05) if expect_ack else self._read_response(0.01)
        if b"\x07" in resp:
            raise RuntimeError(f"SLCAN error response to {cmd}")

    def open(self) -> None:
        if self.ser is not None:
            return
        try:
            import serial
        except Exception as exc:
            raise RuntimeError("pyserial is required for SLCAN backend. Install pyserial.") from exc
        try:
            self.ser = serial.Serial(
                self.port,
                baudrate=self.serial_baud,
                timeout=0.1,
                write_timeout=0.5,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to open SLCAN port {self.port}: {exc}") from exc
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception:
            pass

        cmd = SLCAN_BITRATE_MAP.get(int(self.bitrate))
        if not cmd:
            if self.skip_bitrate:
                logging.warning(
                    "Unsupported SLCAN bitrate %s; skipping bitrate setup",
                    self.bitrate,
                )
            else:
                raise ValueError(
                    f"Unsupported SLCAN bitrate {self.bitrate}. "
                    f"Supported: {sorted(SLCAN_BITRATE_MAP.keys())}"
                )
        self._write_cmd("C", expect_ack=False)
        if cmd:
            self._write_cmd(cmd)
        self._write_cmd("O")

    def send(self, frame_id: int, payload: bytes, is_extended: bool = False) -> bool:
        if self.ser is None:
            raise RuntimeError("Serial port not open")
        frame = self.format_frame(frame_id, payload, is_extended=is_extended)
        try:
            self._write_cmd(frame, expect_ack=False)
            return True
        except Exception as exc:
            self.tx_errors += 1
            logging.warning(
                "SLCAN send failed (port=%s id=0x%x): %s",
                self.port,
                frame_id,
                exc,
            )
            return False

    def recv(self, timeout_s: float | None = 1.0) -> Optional[can.Message]:
        if self.ser is None:
            return None
        timeout = 0.0 if timeout_s is None else max(float(timeout_s), 0.0)
        prev_timeout = getattr(self.ser, "timeout", None)
        try:
            self.ser.timeout = timeout
            raw = self.ser.read_until(b"\r", size=96)
        finally:
            try:
                self.ser.timeout = prev_timeout
            except Exception:
                pass
        if not raw:
            return None
        if b"\x07" in raw:
            logging.warning("SLCAN error response while receiving")
            return None
        line = raw.strip()
        if not line:
            return None
        try:
            prefix = chr(line[0])
        except Exception:
            return None
        if prefix not in {"t", "T"}:
            return None
        try:
            if prefix == "t":
                if len(line) < 5:
                    return None
                frame_id = int(line[1:4].decode("ascii"), 16)
                dlc = int(chr(line[4]), 16)
                data_hex = line[5 : 5 + dlc * 2].decode("ascii")
            else:
                if len(line) < 10:
                    return None
                frame_id = int(line[1:9].decode("ascii"), 16)
                dlc = int(chr(line[9]), 16)
                data_hex = line[10 : 10 + dlc * 2].decode("ascii")
            payload = bytes.fromhex(data_hex) if data_hex else b""
            return can.Message(
                arbitration_id=frame_id,
                is_extended_id=(prefix == "T"),
                data=payload,
            )
        except Exception:
            return None

    def close(self) -> None:
        if self.ser is None:
            return
        try:
            self._write_cmd("C", expect_ack=False)
        except Exception:
            pass
        try:
            self.ser.close()
        except Exception:
            pass
        self.ser = None

    def get_state(self) -> str | None:
        if self.ser is None:
            return None
        return "SLCAN"
