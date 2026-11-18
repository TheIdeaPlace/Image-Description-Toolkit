"""Switching between Editor and Viewer mode moves focus into the view now showing (#419).

The switch itself took effect at once, but hiding one view left focus on a
hidden control, so JAWS and NVDA said nothing. It sounded as if the switch
hadn't happened: Kelly waited over 30 seconds during a batch, 11/18/2026.
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


@pytest.fixture(scope="module")
def frame():
    import imagedescriber_wx
    app = wx.App.Get() or wx.App(False)
    f = imagedescriber_wx.ImageDescriberFrame()
    f.Show()
    yield f
    f.Destroy()
    app.ProcessPendingEvents()


def _settle():
    for _ in range(5):
        wx.SafeYield()


def test_viewer_mode_puts_focus_on_the_viewer_list(frame):
    frame.image_list.SetFocus()
    frame.switch_mode("viewer", frame.workspace)
    _settle()
    assert wx.Window.FindFocus() is frame.viewer_panel.desc_list
    assert frame.GetStatusBar().GetStatusText(0) == "Viewer mode"


def test_editor_mode_puts_focus_back_on_the_image_list(frame):
    frame.switch_mode("viewer", frame.workspace)
    _settle()
    frame.switch_mode("editor")
    _settle()
    assert wx.Window.FindFocus() is frame.image_list
    assert frame.GetStatusBar().GetStatusText(0) == "Editor mode"


def test_the_viewer_list_says_it_is_the_viewer(frame):
    frame.switch_mode("viewer", frame.workspace)
    _settle()
    lst = frame.viewer_panel.desc_list
    lst.LoadDescriptions([{"description": "A salmon leaps."}])
    acc = lst.custom_accessible
    if acc is None:              # wx.Accessible is Windows-only
        pytest.skip("no wx.Accessible on this platform")
    assert acc.GetName(wx.ACC_SELF) == (wx.ACC_OK, "Viewer, all descriptions")
