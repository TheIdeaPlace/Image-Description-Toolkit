"""Ask the screen reader to speak a message, without moving focus (Windows).

Two routes, tried in order:

1. **NVDA, through its controller client** (NV Access's nvdaControllerClient.dll,
   LGPL 2.1, shipped in shared/nvda/). NVDA ignores UI Automation notifications
   from windows that aren't native UIA, and wx windows aren't, so route 2 alone
   was silent under NVDA. Measured in the test VM with NVDA 2026.2, 11/16/2026:
   the notification was accepted and nothing was spoken; the controller client
   spoke the whole reply once, with focus left where it was.
2. **A UI Automation notification event**, what Windows itself uses for "message
   sent" and the like. Narrator speaks these; whether JAWS does for a wx window
   is still to be checked by ear.

ImageDescriber's chat window announced a reply by moving focus to the history
list and back 100 ms later (#410, NVDA bug bash 11/15/2026). NVDA cuts speech off
when focus moves, so a long reply was lost after a word or two. Callers fall
back to that when this returns False (not Windows, or neither route available).

No wx import: the caller passes the window handle (wx's GetHandle()).
"""
from __future__ import annotations

import ctypes
import sys
import sysconfig
from pathlib import Path

__all__ = ["notify", "NOTIFICATION_KIND_ACTION_COMPLETED",
           "NOTIFICATION_PROCESSING_IMPORTANT_MOST_RECENT"]

# UIAutomationCore.h
NOTIFICATION_KIND_ITEM_ADDED = 0
NOTIFICATION_KIND_ACTION_COMPLETED = 2
NOTIFICATION_PROCESSING_IMPORTANT_ALL = 0
NOTIFICATION_PROCESSING_IMPORTANT_MOST_RECENT = 1
NOTIFICATION_PROCESSING_ALL = 2


def _api():
    """(uiacore, oleaut32), or None where UIA notifications don't exist."""
    if sys.platform != "win32":
        return None
    try:
        uia = ctypes.windll.uiautomationcore
        uia.UiaRaiseNotificationEvent          # Windows 10 1709 and later
        return uia, ctypes.windll.oleaut32
    except (AttributeError, OSError):
        return None


#: The interpreter's architecture -> the controller client built for it. The DLL
#: must match this process, not NVDA (an x64 build on ARM64 Windows needs x64).
_NVDA_ARCH = {"win-amd64": "x64", "win-arm64": "arm64"}
_nvda_dll = None        # cached ctypes handle, or False when unavailable


def _nvda_client():
    """NVDA's controller client loaded for this process, or None."""
    global _nvda_dll
    if _nvda_dll is None:
        _nvda_dll = False
        arch = _NVDA_ARCH.get(sysconfig.get_platform())
        if sys.platform == "win32" and arch:
            # shared/nvda/<arch>/ beside this module, from source and in a build
            # (the spec ships it to the same place under _MEIPASS).
            path = Path(__file__).resolve().parent / "nvda" / arch / "nvdaControllerClient.dll"
            try:
                if path.is_file():
                    _nvda_dll = ctypes.WinDLL(str(path))
            except OSError:
                _nvda_dll = False
    return _nvda_dll or None


def speak_with_nvda(text: str, client=None) -> bool:
    """Speak ``text`` through NVDA if it is running. True if NVDA took it."""
    client = client if client is not None else _nvda_client()
    if not client or not text:
        return False
    try:
        if client.nvdaController_testIfRunning() != 0:
            return False
        return client.nvdaController_speakText(ctypes.c_wchar_p(text)) == 0
    except Exception:                                           # noqa: BLE001
        return False


def notify(hwnd: int, text: str, activity_id: str = "idt",
           kind: int = NOTIFICATION_KIND_ACTION_COMPLETED,
           processing: int = NOTIFICATION_PROCESSING_IMPORTANT_MOST_RECENT,
           api=None, nvda=None) -> bool:
    """Have the screen reader speak ``text``. True if NVDA or UIA took it.

    ``api`` and ``nvda`` are for tests: a (uiacore, oleaut32) pair and a
    controller-client stand-in. A test passing ``api`` without ``nvda`` skips
    NVDA, so a developer's running NVDA never speaks test text.
    """
    if not text or not hwnd:
        return False
    if nvda is not None or api is None:
        if speak_with_nvda(text, client=nvda if nvda is not None else None):
            return True
    api = api if api is not None else _api()
    if api is None:
        return False
    uia, oleaut = api
    provider = ctypes.c_void_p()
    display = activity = None
    try:
        hr = uia.UiaHostProviderFromHwnd(ctypes.c_void_p(hwnd), ctypes.byref(provider))
        if hr != 0 or not provider:
            return False
        oleaut.SysAllocString.restype = ctypes.c_void_p
        display = oleaut.SysAllocString(ctypes.c_wchar_p(text))
        activity = oleaut.SysAllocString(ctypes.c_wchar_p(activity_id))
        hr = uia.UiaRaiseNotificationEvent(provider, kind, processing,
                                           ctypes.c_void_p(display), ctypes.c_void_p(activity))
        return hr == 0
    except Exception:                                           # noqa: BLE001
        return False
    finally:
        for bstr in (display, activity):
            if bstr:
                try:
                    oleaut.SysFreeString(ctypes.c_void_p(bstr))
                except Exception:                               # noqa: BLE001
                    pass
        if provider:
            _release(provider)


def _release(pointer: ctypes.c_void_p) -> None:
    """IUnknown::Release on a COM pointer from UiaHostProviderFromHwnd."""
    try:
        vtable = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        release(pointer)
    except Exception:                                           # noqa: BLE001
        pass
