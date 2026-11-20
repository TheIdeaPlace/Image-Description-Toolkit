"""Notice when the running app has been replaced on disk.

The macOS apps are one-file PyInstaller builds: modules not imported at startup
are read later out of the executable itself. Install a new version while the
old one is still open and the old process goes on reading the *new* file at the
old offsets. What fails is whatever is opened next, with an error that has
nothing to do with it. On 11/20/2026 Settings, opened in a window left running
across the 4.9.0 install, said "Operation not permitted" for the settings file,
and in a deliberate repeat "Error -3 while decompressing data: incorrect header
check". The settings file was fine both times; quitting and reopening fixed it.

``remember()`` at startup, then ``replaced()`` says whether the executable is
no longer the file that was started. ``notice(app_name)`` is the text to show.

Wx-free, and imported at startup, so asking works even when nothing more can be
loaded from the executable.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Tuple

__all__ = ['remember', 'replaced', 'notice']

_started: Optional[Tuple[int, int, int, int]] = None


def _fingerprint() -> Optional[Tuple[int, int, int, int]]:
    st = os.stat(sys.executable)
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


def remember() -> None:
    """Record the executable as started. Only a frozen build can be replaced."""
    global _started
    if not getattr(sys, 'frozen', False):
        return
    try:
        _started = _fingerprint()
    except OSError:
        _started = None


def replaced() -> bool:
    """True if the executable was replaced, moved or deleted since remember()."""
    if _started is None:
        return False
    try:
        return _fingerprint() != _started
    except OSError:
        return True         # gone, or no longer readable: either way, reopen


#: Executable names whose display name differs.
_DISPLAY_NAMES = {'IDTChat': 'IDT Chat', 'idt': 'idt'}


def notice(app_name: Optional[str] = None) -> str:
    """What to tell the user. ``app_name`` defaults to the running app's."""
    if app_name is None:
        stem = os.path.splitext(os.path.basename(sys.executable))[0]
        app_name = _DISPLAY_NAMES.get(stem, stem)
    return (f"{app_name} was updated or moved while it was open, so it can't "
            f"load the rest of itself. Quit {app_name} and open it again.")
