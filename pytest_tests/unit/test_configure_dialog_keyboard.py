"""
Configure dialog keyboard access (reported by Kelly with JAWS, 11/15/2026).

* Arrowing along the tabs visited only some of them: on Windows the dialog moved
  to the next tab itself and then let Windows' tab control handle the same key,
  so each press moved two tabs.
* Each setting's explanation sat in a box Tab could never reach (focus was
  bounced back to the list), so it was only heard after opening Change Setting.
  Help paragraphs on other tabs were static text, also unreachable by Tab.

These test which code path each key takes. That one press moves exactly one tab
in Windows' own tab control is a hands-on check with a real keyboard: posted key
messages don't reach an inactive dialog's handler, and real keystrokes would
interrupt whoever is using the PC.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _import_wx():
    """wx, or a skip -- a failure instead when IDT_REQUIRE_WX=1 (test_gui_smoke.py's rule)."""
    if os.environ.get("IDT_REQUIRE_WX") == "1":
        import wx   # a missing wx is an ImportError, failing the test
        return wx
    return pytest.importorskip("wx", reason="wxPython is not installed")


@pytest.fixture(scope="module")
def dialog():
    wx = _import_wx()
    saved_path = list(sys.path)
    sys.path[:0] = [str(_ROOT), str(_ROOT / "imagedescriber")]
    app = wx.App.Get() or wx.App(False)   # must exist while the dialog does
    import configure_dialog
    dlg = configure_dialog.ConfigureDialog(None)
    yield dlg, configure_dialog, wx
    dlg.Destroy()
    del app
    sys.path[:] = saved_path


def _focusable(win, wx):
    out = []
    for child in win.GetChildren():
        if not isinstance(child, (wx.StaticText, wx.StaticBox)) and child.AcceptsFocusFromKeyboard():
            out.append(child)
        out.extend(_focusable(child, wx))
    return out


class _Key:
    """A key event stand-in that records whether it was passed on."""

    def __init__(self, code):
        self.code = code
        self.skipped = False

    def GetKeyCode(self):
        return self.code

    def CmdDown(self):
        return False

    def ShiftDown(self):
        return False

    def Skip(self, skip=True):
        self.skipped = skip


def test_left_and_right_on_the_tabs_are_left_to_windows(dialog, monkeypatch):
    dlg, cfg, wx = dialog
    monkeypatch.setattr(cfg.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: dlg.notebook))
    dlg.notebook.SetSelection(0)
    for code in (wx.WXK_RIGHT, wx.WXK_LEFT):
        key = _Key(code)
        dlg.on_notebook_char(key)
        assert key.skipped, "the key must reach the native tab control"
        assert dlg.notebook.GetSelection() == 0, "the dialog must not move the tab as well"


def test_up_and_down_move_one_tab_on_windows_and_stop_there(dialog, monkeypatch):
    """Windows' tab control ignores Up and Down, so the dialog moves the tab, and
    does not pass the key on (in case a control ever does take them)."""
    dlg, cfg, wx = dialog
    monkeypatch.setattr(cfg.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: dlg.notebook))
    dlg.notebook.SetSelection(0)
    down = _Key(wx.WXK_DOWN)
    dlg.on_notebook_char(down)
    assert dlg.notebook.GetSelection() == 1 and not down.skipped
    up = _Key(wx.WXK_UP)
    dlg.on_notebook_char(up)
    assert dlg.notebook.GetSelection() == 0 and not up.skipped


def test_enter_on_the_tab_bar_goes_to_the_settings_list(dialog, monkeypatch):
    """It went past the list (inside a group box) to Change Setting."""
    dlg, cfg, wx = dialog
    monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: dlg.notebook))
    index = [dlg.notebook.GetPageText(i) for i in range(dlg.notebook.GetPageCount())].index("Generation")
    dlg.notebook.SetSelection(index)
    page = dlg.notebook.GetPage(index)
    assert cfg.first_tab_stop(page) is dlg.category_widgets["Generation"]["settings_list"]


def test_change_setting_has_no_alt_letter(dialog):
    """One per settings tab: a repeated letter in one dialog cycles focus."""
    dlg, cfg, wx = dialog
    for widgets in dlg.category_widgets.values():
        assert "&" not in widgets["change_button"].GetLabel()


def test_arrows_still_move_tabs_on_macos(dialog, monkeypatch):
    dlg, cfg, wx = dialog
    monkeypatch.setattr(cfg.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: dlg.notebook))
    dlg.notebook.SetSelection(0)
    dlg.on_notebook_char(_Key(wx.WXK_RIGHT))
    assert dlg.notebook.GetSelection() == 1


def test_every_settings_tab_reaches_the_explanation_by_tab(dialog):
    dlg, cfg, wx = dialog
    for category, widgets in dlg.category_widgets.items():
        stops = _focusable(widgets["panel"], wx)
        assert stops == [widgets["settings_list"], widgets["explanation_text"],
                         widgets["change_button"]], category


def test_the_explanation_keeps_focus(dialog):
    """It used to hand focus straight back to the list."""
    dlg, cfg, wx = dialog
    box = dlg.category_widgets["Generation"]["explanation_text"]
    # Unbind reports whether a handler was bound: none should be.
    assert box.Unbind(wx.EVT_SET_FOCUS) is False


def test_the_explanation_follows_the_selection(dialog):
    dlg, cfg, wx = dialog
    widgets = dlg.category_widgets["Generation"]
    box = widgets["explanation_text"]
    for index in (1, 0):
        widgets["settings_list"].SetSelection(index)
        dlg.on_setting_selected("Generation", None)
        name = widgets["settings_list"].GetClientData(index)
        expected = dlg.settings_metadata["Generation"][name]["description"]
        assert box.GetValue().startswith(expected), name
    assert box.IsEditable() is False
    assert box.GetName() == "Explanation"


def test_help_boxes_fit_their_text(dialog):
    """No hidden last lines: tall enough for the text at the real font size."""
    dlg, cfg, wx = dialog
    text = "word " * 200
    box = cfg.readable_text(dlg, text, "test", width=300)
    per_line = (300 - 16) // box.GetCharWidth()
    assert box.GetMinSize().height >= box.GetCharHeight() * (len(text) // per_line)
    box.Destroy()


def test_enter_on_a_settings_list_opens_change_setting(dialog, monkeypatch):
    """The list's own handler never sees Enter on Windows (the dialog takes it
    for the default button); the notebook's char hook, which runs first, does
    (installed-build settings check, 11/16/2026: only Space worked)."""
    dlg, cfg, wx = dialog
    settings_list = dlg.category_widgets["Generation"]["settings_list"]
    opened = []
    monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: settings_list))
    monkeypatch.setattr(dlg, "change_setting", lambda category, event: opened.append(category))
    for code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
        key = _Key(code)
        dlg.on_notebook_char(key)
        assert not key.skipped
    assert opened == ["Generation", "Generation"]


def test_other_keys_on_a_settings_list_pass_through(dialog, monkeypatch):
    dlg, cfg, wx = dialog
    settings_list = dlg.category_widgets["Generation"]["settings_list"]
    monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: settings_list))
    key = _Key(wx.WXK_DOWN)
    dlg.on_notebook_char(key)
    assert key.skipped


def test_help_paragraphs_are_reachable_by_tab(dialog):
    dlg, cfg, wx = dialog
    names = {w.GetName() for w in _focusable(dlg.notebook, wx)}
    assert {"About API keys", "About the workspace location",
            "Workspace location from the command line"} <= names
