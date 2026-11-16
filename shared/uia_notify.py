"""Ask the screen reader to speak a message, without moving focus (Windows).

UI Automation's notification event is what Windows itself uses for "message
sent", "download complete" and the like: the app hands the text to UIA and the
screen reader speaks it, while focus stays where the user is. NVDA and Narrator
speak it; JAWS does from 2021 on in most cases.

ImageDescriber's chat window announced a reply by moving focus to the history
list and back 100 ms later. With NVDA nothing was spoken at all (#410, NVDA bug
bash 11/15/2026). This is the replacement; callers fall back to their old way
when it returns False (not Windows, or UIA refused).

No wx import: the caller passes the window handle (wx's GetHandle()).
"""
from __future__ import annotations

import ctypes
import sys

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


def notify(hwnd: int, text: str, activity_id: str = "idt",
           kind: int = NOTIFICATION_KIND_ACTION_COMPLETED,
           processing: int = NOTIFICATION_PROCESSING_IMPORTANT_MOST_RECENT,
           api=None) -> bool:
    """Raise a UIA notification on ``hwnd``'s window. True if UIA accepted it.

    ``api`` is for tests: a (uiacore, oleaut32) pair standing in for the DLLs.
    """
    if not text or not hwnd:
        return False
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
