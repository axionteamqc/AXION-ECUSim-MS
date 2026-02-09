from ecusim_ms.transport import TermuxUsbSlcanTransport

t = TermuxUsbSlcanTransport(bitrate=500000)
t.open()
t.send(0x123, bytes.fromhex("1122334455667788"), is_extended=False)
print("OK send via TermuxUsbSlcanTransport")
t.close()
print("DONE")
