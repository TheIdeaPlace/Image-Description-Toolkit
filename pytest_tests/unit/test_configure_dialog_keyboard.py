"""
Configure dialog keyboard access (reported by Kelly with JAWS, 11/15/2026).

* Arrowing along the tabs visited only some of them: on Windows the dialog moved
  to the next tab itself and then let Windows' tab control handle the same key,
  so each press moved two tabs.
* Each setting's explanation sat in a box Tab could never reach (focus was
  bounced back to the list), so it was only heard after opening Change Setting.
  Help paragraphs on other tabs were static text, also unreachable by Tab.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def dialog():
    try:
        import wx
    except ImportError as exc:
        if os.environ.get("IDT_REQUIRE_WX") == "1":
            raise RuntimeError(f"IDT_REQUIRE_WX=1 but wxPython is missing: {exc}") from exc
        pytest.skip("wxPython is not installed")
    sys.path[:0] = [str(_ROOT), str(_ROOT / "imagedescriber")]
    app = wx.App(False)  # noqa: F841 - must exist while the dialog does
    import configure_dialog
    dlg = configure_dialog.ConfigureDialog(None)
    yield dlg, configure_dialog, wx
    dlg.Destroy()


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


def test_arrows_on_the_tabs_are_left_to_windows(dialog, monkeypatch):
    dlg, cfg, wx = dialog
    monkeypatch.setattr(cfg.platform, "system", lambda: "Windows")
    monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: dlg.notebook))
    dlg.notebook.SetSelection(0)
    for code in (wx.WXK_RIGHT, wx.WXK_LEFT, wx.WXK_DOWN, wx.WXK_UP):
        key = _Key(code)
        dlg.on_notebook_char(key)
        assert key.skipped, "the key must reach the native tab control"
        assert dlg.notebook.GetSelection() == 0, "the dialog must not move the tab as well"


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
    widgets["settings_list"].SetSelection(1)
    dlg.on_setting_selected("Generation", None)
    assert "wording" in widgets["explanation_text"].GetValue()       # Ollama temperature
    assert widgets["explanation_text"].IsEditable() is False


def test_help_paragraphs_are_reachable_by_tab(dialog):
    dlg, cfg, wx = dialog
    names = {w.GetName() for w in _focusable(dlg.notebook, wx)}
    assert {"About API keys", "About the workspace location",
            "Workspace location from the command line"} <= names
