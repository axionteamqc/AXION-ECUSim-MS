ECU Simulator (Android / Termux)

Prereqs
- Termux
- Termux:API + app Android "Termux:API"
- termux-api package installed in Termux:  pkg install termux-api
- Python + deps installed via Termux packages (NOT pip install pip):
  pkg update
  pkg install python clang
  pip install -r requirements.txt

USB / CAN
- Plug USB CAN adapter via OTG.
- Start using:
  ./run_termux.sh

Then open:
  http://127.0.0.1:8000

Notes
- MUST start via termux-usb so TERMUX_USB_FD is provided.
- If no device found: run 'termux-usb -l' and ensure Android permission prompt accepted.
