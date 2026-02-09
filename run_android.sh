#!/usr/bin/env sh
set -e

echo "Connect the OTG dongle and check /dev/ttyACM0"

PORT="${PORT:-/dev/ttyACM0}"
BITRATE="${BITRATE:-500000}"
SERIAL_BAUD="${SERIAL_BAUD:-115200}"
CONTROL_PATH="${CONTROL_PATH:-data/control.json}"

python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ.get("CONTROL_PATH", "data/control.json"))
path.parent.mkdir(parents=True, exist_ok=True)
data = {}
if path.exists():
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
if not isinstance(data, dict):
    data = {}

data.setdefault("profile_id", "ms_simplified")
data.setdefault("iface", "gs_usb")
data.setdefault("channel", 0)
data.setdefault("hz", 50.0)
data.setdefault("mode", "koeo")
data["backend"] = "slcan"
data["port"] = os.environ.get("PORT", "/dev/ttyACM0")
data["bitrate"] = int(os.environ.get("BITRATE", "500000"))
data["serial_baud"] = int(os.environ.get("SERIAL_BAUD", "115200"))
data["skip_bitrate"] = False

path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Configured control.json for PORT={data['port']} BITRATE={data['bitrate']}")
PY

echo "Starting ECU Simulator web UI..."
echo "Open http://127.0.0.1:8000 in your browser."
python -m ecusim_ms.web_ui
