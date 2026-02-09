#!/data/data/com.termux/files/usr/bin/bash
set -e

cd "$(dirname "$0")"

# Pick first USB device from termux-usb JSON output
DEV="$(termux-usb -l 2>/dev/null | grep -oE '/dev/bus/usb/[0-9]{3}/[0-9]{3}' | head -n 1)"
if [ -z "$DEV" ]; then
  echo "ERROR: No USB device listed by termux-usb -l"
  termux-usb -l || true
  exit 1
fi

echo "Using USB device: $DEV"
echo "HTTP: http://127.0.0.1:8000"

# Kill previous instance if any
pkill -f "ecusim_ms.web_ui" 2>/dev/null || true
pkill -f "python -m ecusim_ms.web_ui" 2>/dev/null || true

# Start server (must be started through termux-usb so TERMUX_USB_FD exists)
termux-usb -r -E -e "env PYTHONUNBUFFERED=1 PYTHONPATH=$PWD/src python -m ecusim_ms.web_ui --backend pythoncan --iface termux-usb --bitrate 500000 --host 127.0.0.1 --web-port 8000" "$DEV"
