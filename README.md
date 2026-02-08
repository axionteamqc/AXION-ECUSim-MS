# CAN Gauge – ECU Simulator (MegaSquirt)

Version: v1.00

Python-based ECU simulator for the MegaSquirt Simplified Dash broadcast (IDs 1512–1516). Includes CLI runner, DBC loader, CAN abstraction (gs_usb/virtual), fixed-rate scheduler, telemetry writer, scenario generator, and a Tkinter GUI to drive the runner.


## Media / hardware
This repository focuses on the simulator software only. Hardware renders and PCB/schematic review assets are published in the **firmware** repository under `media/` and `hardware_review/`.

## Prerequisites
- Python 3.11+ on Windows.
- For gs_usb hardware: install WinUSB driver via Zadig (WinUSB backend required).

## Setup
```powershell
.\scripts\setup.ps1
```

## Run (GUI recommandé)
```powershell
.\ui.ps1
```

## Run (CLI - debug/CI)
```powershell
.\.venv\Scripts\python.exe -m ecusim_ms.cli_runner --iface virtual --mode loop
```
# By default hz comes from control.json (50.0); override with --hz if needed.

## Stop
- GUI: bouton Stop.
- CLI: `.\scripts\stop.ps1` (crée `data/stop.flag`).

## Custom mode
- Edit `data/control.json.custom` (partial overrides of the 20 signals) and run with `--mode custom` (overrides applied on top of scenarios).

## Telemetry
- Written best-effort to `data/telemetry.json` at ~5 Hz (signals, clamped info, counters).

## Helpful scripts
- `.\scripts\check.ps1` — Ruff/Black/isort + CLI sanity.
- `.\scripts\format.ps1` — auto-format.

## Android / Termux usage (headless)
This project can run on Android via **Termux** (not a native Android app).

Typical flow:
1) Install Termux
2) Install Python + deps
3) Run the web UI / runner
4) Use your phone browser to open the local web UI

Exact commands can vary by Termux version/device; keep this section minimal and add a tested recipe when you publish.

## License
- **Code:** GNU GPLv3 (see `LICENSE`)
- **Documentation / media:** All rights reserved unless stated otherwise (see `NOTICE.md`)
