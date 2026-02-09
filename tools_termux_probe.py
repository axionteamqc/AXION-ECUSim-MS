from ecusim_ms.transports.termux_libusb_slcan import TermuxUsbSlcan

t = TermuxUsbSlcan()
print(f"CLAIM OK. IF={t.eps.interface_number} OUT=0x{t.eps.ep_out:02X} IN={('0x%02X'%t.eps.ep_in) if t.eps.ep_in else 'None'}")
t.init_slcan("S6")
print("SLCAN INIT OK (C,S6,O)")
t.close()
print("DONE")
