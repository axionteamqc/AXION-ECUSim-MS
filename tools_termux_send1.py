from ecusim_ms.transports.termux_libusb_slcan import TermuxUsbSlcan

t = TermuxUsbSlcan()
t.init_slcan("S6")

# Example: standard ID 0x123, DLC=8, data 11..88
t.write_ascii("t12381122334455667788\r")

print("SENT 0x123 DLC8")
t.close()
