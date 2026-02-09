import os
import ctypes
import ctypes.util
from dataclasses import dataclass
from typing import Optional, Tuple

# libusb C types
libusb_context_p = ctypes.c_void_p
libusb_device_handle_p = ctypes.c_void_p

# Endpoint helpers
LIBUSB_ENDPOINT_IN  = 0x80
LIBUSB_ENDPOINT_OUT = 0x00
LIBUSB_TRANSFER_TYPE_MASK = 0x03
LIBUSB_TRANSFER_TYPE_BULK = 0x02

class LibusbError(RuntimeError):
    pass

def _load_libusb():
    path = ctypes.util.find_library("usb-1.0")
    if not path:
        # Termux usually provides libusb-1.0.so
        path = "libusb-1.0.so"
    return ctypes.CDLL(path)

_libusb = _load_libusb()

# int libusb_init(libusb_context **ctx);
_libusb.libusb_init.argtypes = [ctypes.POINTER(libusb_context_p)]
_libusb.libusb_init.restype = ctypes.c_int

# void libusb_exit(libusb_context *ctx);
_libusb.libusb_exit.argtypes = [libusb_context_p]
_libusb.libusb_exit.restype = None

# int libusb_wrap_sys_device(libusb_context *ctx, intptr_t sys_dev, libusb_device_handle **dev_handle);
# Linux: sys_dev is usually a file descriptor for usbfs node
_libusb.libusb_wrap_sys_device.argtypes = [libusb_context_p, ctypes.c_long, ctypes.POINTER(libusb_device_handle_p)]
_libusb.libusb_wrap_sys_device.restype = ctypes.c_int

# int libusb_kernel_driver_active(libusb_device_handle *dev, int interface_number);
_libusb.libusb_kernel_driver_active.argtypes = [libusb_device_handle_p, ctypes.c_int]
_libusb.libusb_kernel_driver_active.restype = ctypes.c_int

# int libusb_detach_kernel_driver(libusb_device_handle *dev, int interface_number);
_libusb.libusb_detach_kernel_driver.argtypes = [libusb_device_handle_p, ctypes.c_int]
_libusb.libusb_detach_kernel_driver.restype = ctypes.c_int

# int libusb_attach_kernel_driver(libusb_device_handle *dev, int interface_number);
_libusb.libusb_attach_kernel_driver.argtypes = [libusb_device_handle_p, ctypes.c_int]
_libusb.libusb_attach_kernel_driver.restype = ctypes.c_int

# int libusb_claim_interface(libusb_device_handle *dev, int interface_number);
_libusb.libusb_claim_interface.argtypes = [libusb_device_handle_p, ctypes.c_int]
_libusb.libusb_claim_interface.restype = ctypes.c_int

# int libusb_release_interface(libusb_device_handle *dev, int interface_number);
_libusb.libusb_release_interface.argtypes = [libusb_device_handle_p, ctypes.c_int]
_libusb.libusb_release_interface.restype = ctypes.c_int

# void libusb_close(libusb_device_handle *dev_handle);
_libusb.libusb_close.argtypes = [libusb_device_handle_p]
_libusb.libusb_close.restype = None

# int libusb_bulk_transfer(libusb_device_handle *dev, unsigned char endpoint,
#                          unsigned char *data, int length, int *transferred, unsigned int timeout);
_libusb.libusb_bulk_transfer.argtypes = [
    libusb_device_handle_p, ctypes.c_ubyte,
    ctypes.c_void_p, ctypes.c_int,
    ctypes.POINTER(ctypes.c_int), ctypes.c_uint
]
_libusb.libusb_bulk_transfer.restype = ctypes.c_int

# Descriptor structs (minimal subset)
class libusb_endpoint_descriptor(ctypes.Structure):
    _fields_ = [
        ("bLength", ctypes.c_ubyte),
        ("bDescriptorType", ctypes.c_ubyte),
        ("bEndpointAddress", ctypes.c_ubyte),
        ("bmAttributes", ctypes.c_ubyte),
        ("wMaxPacketSize", ctypes.c_ushort),
        ("bInterval", ctypes.c_ubyte),
        ("bRefresh", ctypes.c_ubyte),
        ("bSynchAddress", ctypes.c_ubyte),
        ("extra", ctypes.c_void_p),
        ("extra_length", ctypes.c_int),
    ]

class libusb_interface_descriptor(ctypes.Structure):
    _fields_ = [
        ("bLength", ctypes.c_ubyte),
        ("bDescriptorType", ctypes.c_ubyte),
        ("bInterfaceNumber", ctypes.c_ubyte),
        ("bAlternateSetting", ctypes.c_ubyte),
        ("bNumEndpoints", ctypes.c_ubyte),
        ("bInterfaceClass", ctypes.c_ubyte),
        ("bInterfaceSubClass", ctypes.c_ubyte),
        ("bInterfaceProtocol", ctypes.c_ubyte),
        ("iInterface", ctypes.c_ubyte),
        ("endpoint", ctypes.POINTER(libusb_endpoint_descriptor)),
        ("extra", ctypes.c_void_p),
        ("extra_length", ctypes.c_int),
    ]

class libusb_interface(ctypes.Structure):
    _fields_ = [
        ("altsetting", ctypes.POINTER(libusb_interface_descriptor)),
        ("num_altsetting", ctypes.c_int),
    ]

class libusb_config_descriptor(ctypes.Structure):
    _fields_ = [
        ("bLength", ctypes.c_ubyte),
        ("bDescriptorType", ctypes.c_ubyte),
        ("wTotalLength", ctypes.c_ushort),
        ("bNumInterfaces", ctypes.c_ubyte),
        ("bConfigurationValue", ctypes.c_ubyte),
        ("iConfiguration", ctypes.c_ubyte),
        ("bmAttributes", ctypes.c_ubyte),
        ("MaxPower", ctypes.c_ubyte),
        ("interface", ctypes.POINTER(libusb_interface)),
        ("extra", ctypes.c_void_p),
        ("extra_length", ctypes.c_int),
    ]

# int libusb_get_active_config_descriptor(libusb_device *dev, libusb_config_descriptor **config);
# Need libusb_device*: get it from handle: libusb_get_device(handle)
_libusb.libusb_get_device.argtypes = [libusb_device_handle_p]
_libusb.libusb_get_device.restype = ctypes.c_void_p

_libusb.libusb_get_active_config_descriptor.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(libusb_config_descriptor))]
_libusb.libusb_get_active_config_descriptor.restype = ctypes.c_int

_libusb.libusb_free_config_descriptor.argtypes = [ctypes.POINTER(libusb_config_descriptor)]
_libusb.libusb_free_config_descriptor.restype = None


def _check(rc: int, msg: str):
    if rc < 0:
        raise LibusbError(f"{msg} (rc={rc})")


@dataclass
class UsbEndpoints:
    interface_number: int
    ep_out: int
    ep_in: Optional[int] = None


def _find_bulk_endpoints(handle: libusb_device_handle_p) -> UsbEndpoints:
    dev = _libusb.libusb_get_device(handle)
    if not dev:
        raise LibusbError("libusb_get_device returned NULL")

    cfg_p = ctypes.POINTER(libusb_config_descriptor)()
    rc = _libusb.libusb_get_active_config_descriptor(dev, ctypes.byref(cfg_p))
    _check(rc, "libusb_get_active_config_descriptor failed")

    try:
        cfg = cfg_p.contents
        # iterate interfaces / altsettings / endpoints, pick first interface with bulk OUT (+ optional bulk IN)
        for i in range(cfg.bNumInterfaces):
            intf = cfg.interface[i]
            for a in range(intf.num_altsetting):
                alt = intf.altsetting[a]
                out_ep = None
                in_ep = None
                for e in range(alt.bNumEndpoints):
                    ep = alt.endpoint[e]
                    addr = ep.bEndpointAddress
                    xfer_type = ep.bmAttributes & LIBUSB_TRANSFER_TYPE_MASK
                    if xfer_type != LIBUSB_TRANSFER_TYPE_BULK:
                        continue
                    if (addr & LIBUSB_ENDPOINT_IN) == LIBUSB_ENDPOINT_IN:
                        in_ep = addr
                    else:
                        out_ep = addr
                if out_ep is not None:
                    return UsbEndpoints(interface_number=int(alt.bInterfaceNumber), ep_out=int(out_ep), ep_in=(int(in_ep) if in_ep is not None else None))
        raise LibusbError("No BULK OUT endpoint found in active config descriptor")
    finally:
        _libusb.libusb_free_config_descriptor(cfg_p)


class TermuxUsbSlcan:
    """
    SLCAN over Termux USB FD using libusb_wrap_sys_device.
    """
    def __init__(self, usb_fd_env: str = "TERMUX_USB_FD", baudrate: int = 115200, timeout_ms: int = 200):
        self.usb_fd_env = usb_fd_env
        self.timeout_ms = timeout_ms
        self.ctx = libusb_context_p()
        self.handle = libusb_device_handle_p()
        self.eps: Optional[UsbEndpoints] = None

        fd_str = os.environ.get(self.usb_fd_env)
        if not fd_str:
            raise LibusbError(f"{self.usb_fd_env} not set. Use termux-usb -r -E ...")
        try:
            self.fd = int(fd_str)
        except ValueError:
            raise LibusbError(f"{self.usb_fd_env} is not an int: {fd_str}")

        rc = _libusb.libusb_init(ctypes.byref(self.ctx))
        _check(rc, "libusb_init failed")

        rc = _libusb.libusb_wrap_sys_device(self.ctx, ctypes.c_long(self.fd), ctypes.byref(self.handle))
        _check(rc, "libusb_wrap_sys_device failed (fd might not be usbfs device)")

        self.eps = _find_bulk_endpoints(self.handle)

        # Android often binds a kernel driver; try to detach before claiming
        try:
            active = _libusb.libusb_kernel_driver_active(self.handle, int(self.eps.interface_number))
            if active == 1:
                _libusb.libusb_detach_kernel_driver(self.handle, int(self.eps.interface_number))
        except Exception:
            pass
        rc = _libusb.libusb_claim_interface(self.handle, int(self.eps.interface_number))
        _check(rc, f"libusb_claim_interface({self.eps.interface_number}) failed")

    def close(self):
        try:
            if self.handle and self.eps:
                _libusb.libusb_release_interface(self.handle, int(self.eps.interface_number))
        except Exception:
            pass
        try:
            if self.handle:
                _libusb.libusb_close(self.handle)
        except Exception:
            pass
        try:
            if self.ctx:
                _libusb.libusb_exit(self.ctx)
        except Exception:
            pass

    def write_ascii(self, s: str):
        data = (s).encode("ascii")
        buf = ctypes.create_string_buffer(data)
        transferred = ctypes.c_int(0)
        rc = _libusb.libusb_bulk_transfer(
            self.handle,
            ctypes.c_ubyte(self.eps.ep_out),
            ctypes.cast(buf, ctypes.c_void_p),
            len(data),
            ctypes.byref(transferred),
            ctypes.c_uint(self.timeout_ms),
        )
        _check(rc, "bulk OUT transfer failed")
        if transferred.value != len(data):
            raise LibusbError(f"short write: {transferred.value}/{len(data)}")

    def init_slcan(self, bitrate_cmd: str = "S6"):
        # minimal Lawicel init sequence
        self.write_ascii("C\r")
        self.write_ascii(f"{bitrate_cmd}\r")
        self.write_ascii("O\r")

