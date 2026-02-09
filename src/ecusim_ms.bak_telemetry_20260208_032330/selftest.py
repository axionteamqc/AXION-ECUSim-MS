"""Self-test runner for CI/local validation without hardware."""

from __future__ import annotations

import logging
import sys
import time

from ecusim_ms import dbc_loader, paths
from ecusim_ms.bitrate import DEFAULT_BITRATE
from ecusim_ms.can_bus import CanBus
from ecusim_ms.control_override import read_overrides
from ecusim_ms.dbc_codec import (
    encode_message_safe,
    get_encode_error_count,
    reset_encode_error_stats,
)
from ecusim_ms.ms_signals import MS_SIGNAL_LIST
from ecusim_ms.scenarios import scenario_values
from ecusim_ms.scheduler import FixedRateScheduler


def _build_payloads(dbc_db, scenario):
    payloads = {}
    used_per_msg = {}
    for msg in dbc_db.messages:
        desired = {}
        seen_bits = set()
        for sig in msg.signals:
            key = (sig.start, sig.length, getattr(sig, "byte_order", "big_endian"))
            if key in seen_bits:
                continue
            seen_bits.add(key)
            desired[sig.name] = scenario.get(sig.name, 0.0)
        payload, used, _ = encode_message_safe(msg, desired)
        payloads[msg.name] = payload
        used_per_msg[msg.name] = used
    return payloads, used_per_msg


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    dbc_db = dbc_loader.load_db(paths.dbc_path())
    dbc_loader.assert_expected_layout(dbc_db)
    reset_encode_error_stats()

    # Endianness sanity: RPM 0x1234 should yield bytes ...12 34... (big endian)
    dash0 = dbc_db.get_message_by_name("megasquirt_dash0")
    if dash0:
        desired = {sig.name: 0 for sig in dash0.signals}
        desired["rpm"] = 0x1234
        try:
            payload, used, _ = encode_message_safe(dash0, desired)
        except Exception as exc:
            logging.error("Endianness encode failed: %s", exc)
            return 1
        if payload.hex() != "0000123400000000":
            logging.error(
                "Endianness check failed: got %s expected %s", payload.hex(), "0000123400000000"
            )
            return 1

    bus = CanBus(iface="virtual", channel=0, bitrate=DEFAULT_BITRATE)
    bus.open()
    try:
        rx_bus = CanBus(iface="virtual", channel=0, bitrate=DEFAULT_BITRATE)
        rx_bus.open()
    except Exception:
        rx_bus = None

    hz = 50.0
    scheduler = FixedRateScheduler(hz)
    scheduler.start()

    start = time.perf_counter()
    duration = 5.0
    tx_frames = 0
    rx_seen = False

    try:
        while True:
            now = time.perf_counter()
            if now - start >= duration:
                break

            scenario = scenario_values("loop", now - start)
            overrides = read_overrides(paths.control_path(), MS_SIGNAL_LIST)
            scenario.update(overrides)

            try:
                payloads, used_per_msg = _build_payloads(dbc_db, scenario)
            except Exception as exc:
                logging.error("Selftest encode failed: %s", exc)
                return 1
            for msg in dbc_db.messages:
                data = payloads.get(msg.name)
                if data is None:
                    continue
                if bus.send(
                    msg.frame_id, data, is_extended=getattr(msg, "is_extended_frame", False)
                ):
                    tx_frames += 1

            # roundtrip decode check on dash0 if available
            dash0 = dbc_db.get_message_by_name("megasquirt_dash0")
            if dash0 and "megasquirt_dash0" in payloads and "megasquirt_dash0" in used_per_msg:
                try:
                    decoded = dash0.decode(payloads["megasquirt_dash0"])
                    used = used_per_msg["megasquirt_dash0"]
                    for sig in dash0.signals:
                        sent_val = used.get(sig.name, 0.0)
                        decoded_val = decoded.get(sig.name, 0.0)
                        tol = max(abs(sig.scale), 1e-6)
                        if abs(sent_val - decoded_val) > tol + 1e-6:
                            logging.error(
                                "Selftest decode mismatch for %s: sent=%s decoded=%s tol=%s",
                                sig.name,
                                sent_val,
                                decoded_val,
                                tol,
                            )
                            return 1
                except Exception as exc:
                    logging.error("Selftest decode failed: %s", exc)
                    return 1

            if rx_bus and not rx_seen:
                msg = rx_bus.recv(timeout_s=0.05)
                if msg is not None:
                    rx_seen = True

            scheduler.wait_next()
    finally:
        bus.close()
        if rx_bus:
            rx_bus.close()

    if tx_frames <= 0:
        logging.error("Selftest failed: no frames sent")
        return 1
    if rx_bus and not rx_seen:
        logging.error("Selftest failed: no RX observed on virtual bus")
        return 1
    encode_errors = get_encode_error_count()
    if encode_errors > 0:
        logging.error("Selftest failed: encode errors encountered (%d)", encode_errors)
        return 1

    logging.info("Selftest passed: tx_frames=%d rx_seen=%s", tx_frames, rx_seen)
    return 0


if __name__ == "__main__":
    sys.exit(main())
