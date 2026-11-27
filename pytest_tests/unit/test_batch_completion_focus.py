"""
#409: a finished batch was never announced.

The progress window is retitled "Batch Complete — Review stats then close" so
a screen reader announces it, and the main window then took focus straight
away, leaving that window behind unheard (NVDA bug bash, 11/15/2026). Now a
clean finish focuses the window on its summary line, and closing it (Close,
Escape, Alt+F4) brings focus back to the main window's list for its mode.

These open real wx windows: CI and the test VM run them, not a developer's PC.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _import_wx():
    if os.environ.get("IDT_REQUIRE_WX") == "1":
        import wx
        return wx
    return pytest.importorskip("wx", reason="wxPython not installed")


@pytest.fixture
def owner():
    wx = _import_wx()
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, title="ImageDescriber")
    frame.image_list = wx.ListBox(frame, choices=["a.jpg"])
    yield frame, wx
    frame.Destroy()
    wx.SafeYield()
    del app


def _finished(owner_frame):
    from batch_progress_dialog import BatchProgressDialog
    dlg = BatchProgressDialog(owner_frame, 3)
    dlg.Show()
    dlg.mark_complete("3 images described")
    return dlg


def test_focus_goes_to_the_summary(owner, monkeypatch):
    frame, wx = owner
    dlg = _finished(frame)
    try:
        focused = []
        monkeypatch.setattr(dlg.stats_list, "SetFocus", lambda: focused.append(True))
        dlg.focus_completion()
        assert focused, "the completion window must take focus"
        last = dlg.stats_list.GetCount() - 1
        assert dlg.stats_list.GetSelection() == last
        assert "3 images described" in dlg.stats_list.GetString(last)
        assert dlg.GetTitle().startswith("Batch Complete")
    finally:
        dlg.Destroy()


def test_a_hidden_window_is_not_focused(owner, monkeypatch):
    """Someone who hid the progress window doesn't get it pushed back at them."""
    frame, wx = owner
    dlg = _finished(frame)
    try:
        dlg.Hide()
        focused = []
        monkeypatch.setattr(dlg.stats_list, "SetFocus", lambda: focused.append(True))
        dlg.focus_completion()
        assert not focused
    finally:
        dlg.Destroy()


def test_close_returns_focus_to_the_image_list(owner, monkeypatch):
    frame, wx = owner
    import batch_progress_dialog
    dlg = _finished(frame)
    later = []
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *a: later.append((fn, a)))
    dlg.on_stop_clicked(None)
    assert later == [(batch_progress_dialog._focus_back, (frame,))]


def test_a_window_the_user_is_in_keeps_focus(owner, monkeypatch):
    """Finishing while the chat window (modal) is open must not pull focus out
    of it. Saying the result aloud from there needs NVDA's controller client,
    which 4.9.1 doesn't ship (#410, #439)."""
    frame, wx = owner
    dlg = _finished(frame)
    try:
        elsewhere = wx.Dialog(None, title="Chat")
        focused = []
        monkeypatch.setattr(wx, "GetActiveWindow", lambda: elsewhere)
        monkeypatch.setattr(dlg.stats_list, "SetFocus", lambda: focused.append(True))
        dlg.focus_completion()
        assert not focused
        elsewhere.Destroy()
    finally:
        dlg.Destroy()


def test_escape_or_alt_f4_on_a_finished_window_closes_it_like_close(owner, monkeypatch):
    frame, wx = owner
    import batch_progress_dialog
    dlg = _finished(frame)
    later = []
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *a: later.append((fn, a)))
    dlg.Close()                         # what Escape, Alt+F4 and the title bar do
    assert later == [(batch_progress_dialog._focus_back, (frame,))]


def test_escape_on_a_finished_window_closes_it(owner, monkeypatch):
    """The dialog has no Cancel button, so wx ignored Escape (seen under NVDA)."""
    frame, wx = owner
    import batch_progress_dialog
    dlg = _finished(frame)
    later = []
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *a: later.append((fn, a)))

    class _Key:
        def GetKeyCode(self):
            return wx.WXK_ESCAPE

        def Skip(self, skip=True):
            raise AssertionError("Escape must be handled, not passed on")

    dlg._on_char_hook(_Key())
    assert later == [(batch_progress_dialog._focus_back, (frame,))]


def test_focus_back_uses_the_mode_list_when_there_is_one(owner):
    """Viewer mode puts focus in the Viewer's list, not the hidden image tree."""
    frame, wx = owner
    import batch_progress_dialog
    calls = []
    frame._focus_current_mode = lambda: calls.append("mode")
    batch_progress_dialog._focus_back(frame)
    assert calls == ["mode"]


def test_focus_back_skips_a_closed_window():
    import batch_progress_dialog

    class Gone:
        def _focus_current_mode(self):
            raise RuntimeError("wrapped C/C++ object has been deleted")
    batch_progress_dialog._focus_back(Gone())       # no exception
    batch_progress_dialog._focus_back(None)
