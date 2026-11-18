"""Switching between Editor and Viewer mode moves focus into the view now showing (#419).

The switch itself took effect at once, but hiding one view left focus on a
hidden control, so JAWS and NVDA said nothing. It sounded as if the switch
hadn't happened: Kelly waited over 30 seconds during a batch, 11/18/2026.

Where focus goes is checked by spying on SetFocus rather than with FindFocus,
which on macOS needs the test process to be the active app (#452 review).
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


@pytest.fixture
def focused(frame, monkeypatch):
    """Records which of the two lists SetFocus was called on."""
    calls = []
    viewer_list = frame.viewer_panel.desc_list
    for name, ctrl in (("viewer", viewer_list), ("editor", frame.image_list)):
        monkeypatch.setattr(ctrl, "SetFocus", lambda n=name: calls.append(n))
    return calls


def _settle():
    for _ in range(5):
        wx.SafeYield()


def test_viewer_mode_puts_focus_on_the_viewer_list(frame, focused):
    frame.switch_mode("viewer", frame.workspace)
    _settle()
    assert focused[-1:] == ["viewer"]
    assert frame.GetStatusBar().GetStatusText(0) == "Viewer mode"


def test_editor_mode_puts_focus_back_on_the_image_list(frame, focused):
    frame.switch_mode("viewer", frame.workspace)
    _settle()
    frame.switch_mode("editor")
    _settle()
    assert focused[-1:] == ["editor"]
    assert frame.GetStatusBar().GetStatusText(0) == "Editor mode"


def test_a_batch_ending_in_viewer_mode_keeps_focus_in_the_viewer(frame, focused):
    """Stopping a batch (and the other end and error paths) used to send focus
    to the hidden Editor tree, making the Viewer go silent again."""
    frame.switch_mode("viewer", frame.workspace)
    _settle()
    focused.clear()
    frame._focus_current_mode()
    frame._restore_focus_after_error()
    assert focused == ["viewer", "viewer"]
    frame.switch_mode("editor")
    _settle()


def test_the_viewer_list_says_it_is_the_viewer_before_anything_loads(frame):
    acc = frame.viewer_panel.desc_list.custom_accessible
    if acc is None:              # wx.Accessible is Windows-only
        pytest.skip("no wx.Accessible on this platform")
    assert acc.GetName(wx.ACC_SELF) == (wx.ACC_OK, "Viewer, all descriptions")
