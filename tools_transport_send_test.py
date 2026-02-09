import can
from ecusim_ms.transport import CanTransport

t = CanTransport(backend="termux-usb", bitrate=500000)
t.open()

msg = can.Message(
    arbitration_id=0x123,
    data=bytes.fromhex("1122334455667788"),
    is_extended_id=False
)

ok = t.send(msg)
print("OK transport send", ok)

t.close()
print("DONE")
