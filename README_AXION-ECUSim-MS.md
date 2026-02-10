# AXION-ECUSim-MS (Bench ECU Simulator)

This repository contains a **bench-only ECU CAN simulator** used during development of the **AXION Action microCANgauge**.

## Status / Scope (read this first)

- **Experimental / not cleaned**: this code is a development tool. Expect rough edges.
- **Not the main product**: the primary deliverable is the **Action microCANgauge firmware** (separate repo).
- **Bench usage only**: intended for testing UI, decoding, scaling, and CAN frame flows without requiring a real ECU.

If you're here to review the main project quality, start with:
- **AXION Action microCANgauge firmware repo** (cleaner, product-focused)

## What it does

- Generates **synthetic MegaSquirt Simplified Dash Broadcast** CAN frames (bench data).
- Provides a small **web UI** to start/stop scenarios and adjust values.
- Supports a "realistic" mode (e.g., MAP absolute with vacuum at idle; boost is MAP − BARO).

## Quick Start (PC)

> Tested as a dev tool. No production hardening.

1) Install Python 3.10+ (recommended).
2) Create a venv (optional but recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3) Install requirements:
   ```bash
   pip install -r requirements.txt
   ```
4) Run the UI:
   ```bash
   python -m ecusim_ms.web_ui
   ```
5) Open:
   - http://127.0.0.1:8000

## Quick Start (Android / Termux)

A Termux-friendly launcher is included.

1) Install Termux.
2) Install dependencies:
   ```bash
   pkg update
   pkg install python git
   ```
3) Run:
   ```bash
   bash run_termux.sh
   ```
4) Open:
   - http://127.0.0.1:8000

> Note: Android/USB permissions can be finicky depending on device/OS. This is still a bench tool.

## Notes on MAP / Boost (important)

- The simulator emits **MAP in kPa absolute**.
- Many gauge displays compute boost as: **boost = MAP(abs) − BARO(abs)**.
- Therefore **negative boost at idle** is normal on gasoline engines due to manifold vacuum.

## Known limitations

- Minimal error reporting / recovery (bench tool).
- Not designed for unattended operation.
- No formal test suite / CI guarantees.

## License

GPLv3 (see LICENSE).

## Disclaimer

This project is provided as-is, without warranty. It is intended for bench testing and development reference only.
