import os
from serial import serial_for_url

fd = os.environ.get("TERMUX_USB_FD")
print("FD =", fd)

s = serial_for_url(f"fd://{fd}", baudrate=115200, timeout=0.2)
s.write(b"C\r")
s.flush()
print("OPEN+WRITE OK")
s.close()
