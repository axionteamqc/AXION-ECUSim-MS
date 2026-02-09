from ecusim_ms.can_bus import CanBus

bus = CanBus(iface="termux-usb", channel=0, bitrate=500000, backend="pythoncan")
bus.open()
ok = bus.send(frame_id=0x123, payload=bytes.fromhex("1122334455667788"), is_extended=False)
print("OK CanBus send:", ok)
bus.close()
print("DONE")
