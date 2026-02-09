"""Helpers for preparing the gs_usb backend on Windows using pyusb/libusb."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Optional

import usb.backend.libusb1 as libusb1
import usb.core
import usb.util

_BACKEND = None
_ORIG_FIND = None


def ensure_pyusb_libusb_backend(verbose: bool = False):
    """Ensure a libusb backend is available (required for gs_usb on Windows).

    Raises RuntimeError if the backend cannot be loaded.
    """
    global _BACKEND, _ORIG_FIND
    if _BACKEND is not None:
        return _BACKEND

    libusb_pkg = None
    try:
        import libusb_package

        libusb_pkg = libusb_package
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("libusb-package not installed; required for gs_usb on Windows") from exc

    dll_path: Optional[str] = None
    if hasattr(libusb_pkg, "get_library_path"):
        try:
            dll_path = libusb_pkg.get_library_path()
        except Exception:
            dll_path = None

    if dll_path:
        try:
            dll_dir = Path(dll_path).parent
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(dll_dir))
        except Exception:
            pass
        try:
            ctypes.WinDLL(dll_path)
        except Exception:
            # continue; libusb1.get_backend may still succeed
            pass

    backend = libusb1.get_backend(find_library=(lambda _: dll_path) if dll_path else None)
    if backend is None and hasattr(libusb_pkg, "get_libusb1_backend"):
        try:
            backend = libusb_pkg.get_libusb1_backend()
        except Exception:
            backend = None
    if backend is None:
        backend = libusb1.get_backend()

    if backend is None:
        msg = "libusb backend not available. "
        msg += f"libusb_package.get_library_path={dll_path}. "
        msg += "Suggest: reinstall libusb-package wheel; check 64-bit Python; ensure VC runtime if needed."
        raise RuntimeError(msg)

    if _ORIG_FIND is None:
        _ORIG_FIND = usb.core.find

        def _patched_find(*args, **kwargs):
            if kwargs.get("backend") is None:
                kwargs["backend"] = backend
            return _ORIG_FIND(*args, **kwargs)

        usb.core.find = _patched_find  # type: ignore[assignment]

    if verbose:
        print("libusb backend loaded:", backend)  # noqa: T201
    _BACKEND = backend
    return _BACKEND


def ensure_backend(verbose: bool = False):
    """Alias for ensure_pyusb_libusb_backend (compat)."""
    return ensure_pyusb_libusb_backend(verbose=verbose)


def hard_reset_gsusb(vid: int = 0x1D50, pid: int = 0x606F, verbose: bool = False) -> bool:
    """Best-effort USB-level reset of a gs_usb-compatible device via libusb."""
    try:
        backend = ensure_backend(verbose=verbose)
    except Exception as exc:
        raise RuntimeError(f"Cannot reset device: backend unavailable ({exc})") from exc

    dev = usb.core.find(idVendor=vid, idProduct=pid, backend=backend)
    if dev is None:
        raise RuntimeError(f"gs_usb device not found vid=0x{vid:04x} pid=0x{pid:04x}")
    try:
        dev.reset()
        if verbose:
            print(f"USB reset issued to 0x{vid:04x}:0x{pid:04x}")  # noqa: T201
        return True
    except Exception as exc:
        raise RuntimeError(f"USB reset failed for 0x{vid:04x}:0x{pid:04x}: {exc}") from exc


def probe_gsusb(vid: int, pid: int, verbose: bool = False) -> bool:
    """Return True if a gs_usb device with the given VID/PID is detectable."""
    try:
        backend = ensure_pyusb_libusb_backend(verbose=verbose)
    except Exception:
        return False

    dev: Optional[usb.core.Device] = usb.core.find(idVendor=vid, idProduct=pid, backend=backend)
    if verbose:
        print(f"probe_gsusb vid=0x{vid:04x} pid=0x{pid:04x} -> {bool(dev)}")  # noqa: T201
    return dev is not None


def probe_any_gsusb(verbose: bool = False) -> bool:
    """Best-effort detection of common gs_usb devices (candleLight VID/PID)."""
    try:
        backend = ensure_pyusb_libusb_backend(verbose=verbose)
    except Exception:
        return False

    VID = 0x1D50
    PID = 0x606F
    try:
        dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
        found = dev is not None
        if verbose:
            print(f"probe_any_gsusb candleLight 0x1d50:0x606f -> {found}")  # noqa: T201
        return found
    except Exception:
        return False
