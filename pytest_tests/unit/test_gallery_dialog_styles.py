"""#428: the Gallery dialog opened by reading all four style descriptions.

Each style had a text line under its button, and a screen reader read all four
in a row before reaching anything that could be acted on (NVDA bug bash,
11/15/2026). Now each description is part of its button's screen reader name,
one line shows the selected style's description, and the dialog opens on the
style choice. Opens a real (hidden) dialog: runs in the VM and CI.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

wx = pytest.importorskip("wx", reason="wxPython not installed in this environment")

pytestmark = pytest.mark.unit


@pytest.fixture
def dialog():
    app = wx.App.Get() or wx.App(False)
    from dialogs_wx import ExportHtmlGalleryDialog
    dlg = ExportHtmlGalleryDialog(None)
    yield dlg
    dlg.Destroy()
    del app


def _descriptions():
    from dialogs_wx import ExportHtmlGalleryDialog
    return [d for _v, _l, d in ExportHtmlGalleryDialog._STYLES]


def _static_texts(win):
    found = []
    for child in win.GetChildren():
        if isinstance(child, wx.StaticText):
            found.append(child.GetLabel().replace("\n", " "))
        found.extend(_static_texts(child))
    return found


def test_only_one_description_is_on_screen(dialog):
    texts = _static_texts(dialog)
    shown = [d for d in _descriptions() if any(d in t for t in texts)]
    assert len(shown) == 1


def test_each_style_is_named_with_its_description(dialog):
    from dialogs_wx import ExportHtmlGalleryDialog
    for value, label, description in ExportHtmlGalleryDialog._STYLES:
        name = dialog._style_radios[value].GetName()
        assert name == f"{label.replace('&', '')}, {description}"


def test_the_line_follows_the_selected_style(dialog):
    from dialogs_wx import ExportHtmlGalleryDialog
    for value, _label, description in ExportHtmlGalleryDialog._STYLES:
        dialog._style_radios[value].SetValue(True)
        dialog._on_style_changed(wx.CommandEvent(wx.wxEVT_RADIOBUTTON))
        assert dialog._style_hint.GetLabel().replace("\n", " ") == description
        assert dialog.get_options()["style"] == value


def test_it_opens_on_the_selected_style(dialog, monkeypatch):
    assert dialog._selected_style_radio() is dialog._style_radios["card_grid"]
    dialog._style_radios["photo_essay"].SetValue(True)
    assert dialog._selected_style_radio() is dialog._style_radios["photo_essay"]


def test_focus_is_queued_for_the_style_choice(monkeypatch):
    app = wx.App.Get() or wx.App(False)
    from dialogs_wx import ExportHtmlGalleryDialog
    queued = []
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *a, **k: queued.append(fn))
    dlg = ExportHtmlGalleryDialog(None)
    try:
        assert dlg._style_radios["card_grid"].SetFocus in queued
        assert dlg._browse_btn.SetFocus not in queued
    finally:
        dlg.Destroy()
        del app
