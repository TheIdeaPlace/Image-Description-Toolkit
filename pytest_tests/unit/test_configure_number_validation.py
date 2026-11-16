"""
Every number typed into the Configure dialog is checked before it is saved.

Only the Generation tab's numbers were checked. Elsewhere a bad entry was saved
as something else without a word: "abc" in a plain number field became 0.0 (a
0-second frame interval), "abc" in Max frames per video became unlimited, and a
spin box clamped 150 to its maximum. Now each is refused with a message box
naming the allowed range, and the field keeps focus.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _import_wx():
    """wx, or a skip -- a failure instead when IDT_REQUIRE_WX=1."""
    if os.environ.get("IDT_REQUIRE_WX") == "1":
        import wx
        return wx
    return pytest.importorskip("wx", reason="wxPython is not installed")


@pytest.fixture(scope="module")
def cfg():
    wx = _import_wx()
    for p in (str(_ROOT), str(_ROOT / "imagedescriber")):
        if p not in sys.path:
            sys.path.insert(0, p)
    app = wx.App.Get() or wx.App(False)
    import configure_dialog
    yield configure_dialog, wx
    del app


FLOAT = {"type": "float", "range": [0.5, 30.0]}
INT_OR_NULL = {"type": "int_or_null", "range": [1, 1000]}
INT = {"type": "int", "range": [50, 100]}
FLOAT_AUTO = {"type": "float_or_auto", "range": [0.0, 2.0]}
INT_AUTO = {"type": "int_or_auto", "range": [1, 100000]}


@pytest.mark.parametrize("info, text, expected", [
    (FLOAT, "3", 3.0), (FLOAT, " 0.5 ", 0.5), (FLOAT, "30", 30.0),
    (INT_OR_NULL, "50", 50), (INT_OR_NULL, "", None), (INT_OR_NULL, "none", None),
    (INT, "85", 85),
    (FLOAT_AUTO, "", None), (FLOAT_AUTO, "Automatic", None), (FLOAT_AUTO, "0.7", 0.7),
    (INT_AUTO, "800", 800),
])
def test_good_entries_are_accepted(cfg, info, text, expected):
    configure_dialog, _wx = cfg
    assert configure_dialog.validate_number(info, text) == (expected, None)


@pytest.mark.parametrize("info, text, says", [
    (FLOAT, "abc", "Enter a number from 0.5 to 30."),     # was saved as 0.0
    (FLOAT, "", "Enter a number from 0.5 to 30."),        # empty isn't allowed here
    (FLOAT, "0", "Enter a number from 0.5 to 30."),
    (FLOAT, "500", "Enter a number from 0.5 to 30."),
    (FLOAT, "nan", "Enter a number from 0.5 to 30."),
    (FLOAT, "inf", "Enter a number from 0.5 to 30."),
    (INT_OR_NULL, "abc", "Enter a whole number from 1 to 1000, or leave it empty for no limit."),
    (INT_OR_NULL, "5000", "Enter a whole number from 1 to 1000, or leave it empty for no limit."),
    (INT_OR_NULL, "2.5", "Enter a whole number from 1 to 1000, or leave it empty for no limit."),
    (INT, "150", "Enter a whole number from 50 to 100."),    # a spin box clamped it to 100
    (FLOAT_AUTO, "5", "Enter a number from 0 to 2, or leave it empty for Automatic."),
    (INT_AUTO, "1.5", "Enter a whole number from 1 to 100000, or leave it empty for Automatic."),
])
def test_bad_entries_are_refused_with_the_range(cfg, info, text, says):
    configure_dialog, _wx = cfg
    assert configure_dialog.validate_number(info, text) == (None, says)


class _Ok:
    def __init__(self):
        self.skipped = False

    def Skip(self, skip=True):
        self.skipped = skip


def _dialog(cfg, monkeypatch, name, value, info):
    configure_dialog, wx = cfg
    shown = []
    monkeypatch.setattr(wx, "MessageBox", lambda msg, *a, **k: shown.append(msg))
    dlg = configure_dialog.SettingEditDialog(None, name, value, info)
    return dlg, shown


@pytest.mark.parametrize("info, value, typed", [
    (FLOAT, 5.0, "abc"),
    (INT_OR_NULL, None, "abc"),
    (INT, 85, "150"),
])
def test_ok_refuses_a_bad_entry_and_keeps_the_dialog_open(cfg, monkeypatch, info, value, typed):
    configure_dialog, wx = cfg
    dlg, shown = _dialog(cfg, monkeypatch, "Setting", value, info)
    try:
        dlg.editor.SetValue(typed)
        ok = _Ok()
        dlg._on_ok(ok)
        assert shown and "Enter a" in shown[0]
        assert not ok.skipped, "the dialog must stay open"
        assert dlg.GetValue() == value, "nothing else may be saved in its place"
    finally:
        dlg.Destroy()


@pytest.mark.parametrize("info", [FLOAT, INT, INT_OR_NULL, FLOAT_AUTO, INT_AUTO],
                         ids=lambda i: i["type"])
def test_every_number_editor_is_a_text_box(cfg, monkeypatch, info):
    """Not a SpinCtrl: a spin box rewrites a typed 150 to its maximum when it
    loses focus, so Tab to OK saved 100 without a word."""
    configure_dialog, wx = cfg
    dlg, _shown = _dialog(cfg, monkeypatch, "Setting", None, info)
    try:
        assert type(dlg.editor) is wx.TextCtrl
    finally:
        dlg.Destroy()


def test_tabbing_away_to_ok_does_not_change_the_entry(cfg, monkeypatch):
    """The usual screen reader path: type, Tab to OK, press Space."""
    configure_dialog, wx = cfg
    dlg, shown = _dialog(cfg, monkeypatch, "image_quality", 85, INT)
    try:
        dlg.Show()
        dlg.editor.SetFocus()
        dlg.editor.SetValue("150")
        dlg.FindWindowById(wx.ID_OK).SetFocus()     # focus leaves the field
        wx.Yield()
        ok = _Ok()
        dlg._on_ok(ok)
        assert dlg.editor.GetValue() == "150"
        assert not ok.skipped and shown == ["Enter a whole number from 50 to 100."]
    finally:
        dlg.Destroy()


@pytest.mark.parametrize("text, expected", [
    ("+85", (85, None)), (" 85 ", (85, None)),
    ("1e2", (None, "Enter a whole number from 50 to 100.")),
    ("85.0", (None, "Enter a whole number from 50 to 100.")),
    ("", (None, "Enter a whole number from 50 to 100.")),
])
def test_whole_number_edge_cases(cfg, text, expected):
    configure_dialog, _wx = cfg
    assert configure_dialog.validate_number(INT, text) == expected


@pytest.mark.parametrize("text", ["NULL", "Unlimited", " none "])
def test_no_limit_words(cfg, text):
    configure_dialog, _wx = cfg
    assert configure_dialog.validate_number(INT_OR_NULL, text) == (None, None)


def test_a_good_entry_closes_and_is_saved(cfg, monkeypatch):
    dlg, shown = _dialog(cfg, monkeypatch, "time_interval_seconds", 5.0, FLOAT)
    try:
        dlg.editor.SetValue("2.5")
        ok = _Ok()
        dlg._on_ok(ok)
        assert ok.skipped and not shown
        assert dlg.GetValue() == 2.5
    finally:
        dlg.Destroy()


def test_the_range_is_part_of_the_field_name(cfg, monkeypatch):
    """The visible "Range:" line is static text a screen reader doesn't read on focus."""
    dlg, _shown = _dialog(cfg, monkeypatch, "time_interval_seconds", 5.0, FLOAT)
    try:
        # Spaces, not underscores, which JAWS and NVDA read as "underline".
        assert dlg.editor.GetName() == "time interval seconds value, 0.5 to 30"
        assert dlg.GetTitle() == "Edit: time interval seconds"
        # What a screen reader gets on Windows: the accessible object's name, not
        # the "Value:" label before the field (installed-build settings check).
        try:
            acc = dlg.editor.GetAccessible()
        except (NotImplementedError, AttributeError):       # macOS: no wx.Accessible
            acc = None
        if acc is not None:
            assert acc.GetName(0)[1] == "time interval seconds value, 0.5 to 30"
    finally:
        dlg.Destroy()


def test_the_name_says_what_empty_means(cfg, monkeypatch):
    dlg, _shown = _dialog(cfg, monkeypatch, "max_frames_per_video", None, INT_OR_NULL)
    try:
        assert dlg.editor.GetName() == "max frames per video value, 1 to 1000, or empty for no limit"
    finally:
        dlg.Destroy()


def test_the_message_box_title_is_spoken_cleanly(cfg, monkeypatch):
    configure_dialog, wx = cfg
    titles = []
    monkeypatch.setattr(wx, "MessageBox", lambda msg, title, *a, **k: titles.append(title))
    dlg = configure_dialog.SettingEditDialog(None, "batch_delay", 1.0, FLOAT)
    try:
        dlg.editor.SetValue("x")
        dlg._on_ok(_Ok())
        assert titles == ["batch delay"]
    finally:
        dlg.Destroy()


def test_every_number_setting_in_the_dialog_is_checked(cfg):
    """No number type is left out of validate_number."""
    configure_dialog, _wx = cfg
    from types import SimpleNamespace
    meta = configure_dialog.ConfigureDialog.build_settings_metadata(
        SimpleNamespace(_get_ollama_models=lambda: []))
    # The Mac-only Generation entries too, whichever platform runs this.
    meta["Generation (with Mac)"] = configure_dialog.generation_settings_metadata(include_mac=True)
    types ={info.get("type") for cat in meta.values() for info in cat.values()}
    numeric = {t for t in types if t and ("int" in t or "float" in t)}
    assert numeric <= set(configure_dialog.NUMBER_TYPES)
    for cat in meta.values():
        for name, info in cat.items():
            if info.get("type") in configure_dialog.NUMBER_TYPES:
                assert "range" in info, f"{name} has no range to check against"
