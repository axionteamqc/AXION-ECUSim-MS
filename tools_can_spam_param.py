import sys, time
from ecusim_ms.transport import TermuxUsbSlcanTransport

br = int(sys.argv[1]) if len(sys.argv) > 1 else 500000
t = TermuxUsbSlcanTransport(bitrate=br)
t.open()

start = time.time()
count = 0
while time.time() - start < 3.0:
    t.send(0x5E8, bytes.fromhex("0102030405060708"), is_extended=False)
    count += 1
    time.sleep(0.02)

t.close()
print("BITRATE", br, "SENT", count)
