"""Optional CAN sniffer with CSV logging and DBC decode (best effort)."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from cantools.database import Database

from ecusim_ms.can_bus import CanBus


def sniff_loop(
    bus: CanBus,
    stop_file: Path,
    log_path: Optional[Path],
    db: Optional[Database],
    decode: bool,
) -> None:
    log_file = None
    try:
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("a", encoding="utf-8")
            log_file.write("ts,dir,id,dlc,data_hex,decoded\n")

        while True:
            if stop_file.exists():
                break

            msg = bus.recv(timeout_s=0.1)
            if msg is None:
                continue

            decoded = ""
            if decode and db:
                try:
                    dbc_msg = db.get_message_by_frame_id(msg.arbitration_id)
                    if dbc_msg:
                        decoded = dbc_msg.decode(msg.data)
                except Exception:
                    decoded = ""

            line = f"{time.time():.3f},RX,{hex(msg.arbitration_id)},${msg.dlc},{msg.data.hex()},{decoded}"
            logging.info("RX %s", line)
            if log_file:
                log_file.write(line + "\n")
                log_file.flush()
    finally:
        if log_file:
            log_file.close()
