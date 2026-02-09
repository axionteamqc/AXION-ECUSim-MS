import time
from ecusim_ms.transport import TermuxUsbSlcanTransport

t = TermuxUsbSlcanTransport(bitrate=500000)
t.open()

start = time.time()
count = 0

# 0x5E8 standard, 8 bytes
frame_id = 0x5E8
payload = bytes.fromhex("0102030405060708")

while time.time() - start < 5.0:
    t.send(frame_id, payload, is_extended=False)
    count += 1
    time.sleep(0.020)  # 20 ms

t.close()
print("SENT_FRAMES=", count)
