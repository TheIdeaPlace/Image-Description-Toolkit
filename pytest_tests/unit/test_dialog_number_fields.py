"""
#406: the video extraction and Download dialogs' spin boxes changed an
out-of-range number to their limit without saying so (typing 500 for the
frame interval became 60), as Configure's did before #405. Now they are text
fields checked on OK with shared.number_entry, named with their range, and the
frame interval and scene threshold have one range everywhere.

The tests at the top open no windows. The dialog tests do: CI and the test VM
run them, not a developer's PC.
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

from shared import number_entry  # noqa: E402


def test_the_old_minus_one_still_means_no_limit_where_it_did():
    """Download's Maximum images said "-1 for unlimited"; it still works there."""
    info = {"type": "int_or_null", "range": [1, 10000], "minus_one_empty": True}
    assert number_entry.validate_number(info, "-1") == (None, None)
    assert number_entry.validate_number(info, "") == (None, None)
    assert number_entry.validate_number(info, "0")[1] == (
        "Enter a whole number from 1 to 10000, or leave it empty for no limit.")


def test_minus_one_is_refused_elsewhere():
    """Configure's Max frames per video never took -1; it isn't quietly made "no limit"."""
    info = {"type": "int_or_null", "range": [1, 1000]}
    assert number_entry.validate_number(info, "-1") == (
        None, "Enter a whole number from 1 to 1000, or leave it empty for no limit.")


def test_ranges_read_as_people_say_them():
    """ "1 to 100", not "1.0 to 100.0" (one point zero to one hundred point zero)."""
    info = {"type": "float", "range": [1.0, 100.0]}
    assert number_entry.spoken_range(info) == ", 1 to 100"
    assert number_entry.validate_number(info, "x")[1] == "Enter a number from 1 to 100."


def test_spoken_range():
    assert number_entry.spoken_range({"type": "float", "range": [0.5, 60.0]}) == ", 0.5 to 60"
    assert number_entry.spoken_range({"type": "int_or_null", "range": [1, 10000]}) == (
        ", 1 to 10000, or empty for no limit")
    assert number_entry.spoken_range({"type": "string"}) == ""


def test_one_range_for_each_video_setting():
    """Configure and the dialog disagreed: 0.5-30 against 0.1-60, 10-50 against 1-100."""
    assert number_entry.VIDEO_INTERVAL_RANGE == (0.5, 60.0)
    assert number_entry.SCENE_THRESHOLD_RANGE == (1.0, 100.0)


def test_nothing_uses_a_spin_box_for_these_settings_any_more():
    for rel in ("imagedescriber/dialogs_wx.py", "imagedescriber/download_dialog.py",
                "imagedescriber/configure_dialog.py"):
        src = (_ROOT / rel).read_text(encoding="utf-8")
        assert "wx.SpinCtrl(" not in src and "wx.SpinCtrlDouble(" not in src, rel


# --------------------------------------------------------------------------- #
# The dialogs (open windows: CI and the VM only)                               #
# --------------------------------------------------------------------------- #

def _wx():
    if os.environ.get("IDT_REQUIRE_WX") == "1":
        import wx
        return wx
    return pytest.importorskip("wx", reason="wxPython not installed")


@pytest.fixture
def app():
    wx = _wx()
    application = wx.App.Get() or wx.App(False)
    yield wx
    del application


class _Ok:
    skipped = False

    def Skip(self, skip=True):
        self.skipped = skip


def test_video_dialog_refuses_an_interval_out_of_range(app, monkeypatch):
    wx = app
    from dialogs_wx import VideoExtractionDialog
    shown = []
    monkeypatch.setattr(wx, "MessageBox", lambda msg, *a, **k: shown.append(msg))
    dlg = VideoExtractionDialog(None)
    try:
        assert type(dlg.time_input) is wx.TextCtrl
        assert dlg.time_input.GetName() == "Time interval in seconds, 0.5 to 60"
        dlg.time_input.SetValue("500")
        ok = _Ok()
        dlg._on_ok(ok)
        assert shown == ["Enter a number from 0.5 to 60."] and not ok.skipped
        dlg.time_input.SetValue("2.5")
        ok = _Ok()
        dlg._on_ok(ok)
        assert ok.skipped
        assert dlg.get_settings()["time_interval_seconds"] == 2.5
    finally:
        dlg.Destroy()


def test_video_dialog_checks_only_the_chosen_mode(app, monkeypatch):
    wx = app
    from dialogs_wx import VideoExtractionDialog
    shown = []
    monkeypatch.setattr(wx, "MessageBox", lambda msg, *a, **k: shown.append(msg))
    dlg = VideoExtractionDialog(None)
    try:
        dlg.scene_input.SetValue("not used")    # scene mode isn't chosen
        ok = _Ok()
        dlg._on_ok(ok)
        assert ok.skipped and not shown
    finally:
        dlg.Destroy()


def test_download_dialog_refuses_bad_numbers_and_reads_empty_as_no_limit(app, monkeypatch):
    wx = app
    from download_dialog import DownloadSettingsDialog
    shown = []
    monkeypatch.setattr(wx, "MessageBox", lambda msg, *a, **k: shown.append(msg))
    dlg = DownloadSettingsDialog(None, url="https://example.com")
    try:
        assert dlg.max_images.GetName() == "Maximum images, 1 to 10000, or empty for no limit"
        # The name a screen reader gets on Windows comes from the accessible
        # object, not the label before the field.
        acc = dlg.min_height.GetAccessible() if hasattr(dlg.min_height, "GetAccessible") else None
        if acc is not None:
            assert acc.GetName(0)[1] == "Minimum height in pixels, 0 to 10000"
        dlg.min_width.SetValue("abc")
        ended = []
        monkeypatch.setattr(dlg, "EndModal", lambda code: ended.append(code))
        dlg.on_ok(None)
        assert shown == ["Enter a whole number from 0 to 10000."] and not ended
        dlg.min_width.SetValue("200")
        dlg.max_images.SetValue("")
        dlg.on_ok(None)
        assert ended == [wx.ID_OK]
        settings = dlg.get_settings()
        assert settings["min_width"] == 200 and settings["max_images"] is None
    finally:
        dlg.Destroy()
