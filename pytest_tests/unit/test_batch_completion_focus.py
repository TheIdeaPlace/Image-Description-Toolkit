"""
#409: a finished batch was never announced.

The progress window is retitled "Batch Complete — Review stats then close" so
a screen reader announces it, and the main window then took focus straight
away, leaving that window behind unheard (NVDA bug bash, 11/15/2026). Now a
clean finish focuses the window on its summary line, and its Close button
brings focus back to the image list.

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
    assert later == [(batch_progress_dialog._focus_if_alive, (frame.image_list,))]


def test_the_main_window_hands_a_clean_finish_to_the_completion_window():
    """The batch-finished handler focuses the completion window only for a clean
    finish; failures and stops still get their message box and the image list."""
    src = (_ROOT / "imagedescriber" / "imagedescriber_wx.py").read_text(encoding="utf-8")
    assert "wx.CallAfter(finished_dialog.focus_completion)" in src
    assert ("if (finished_dialog and not halted and not failures and not video_failures\n"
            "                and finished_dialog.IsShown()):") in src
