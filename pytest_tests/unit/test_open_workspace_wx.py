"""Opening a workspace reads it off the UI thread (#492).

Kelly, 11/19/2026: Ctrl+O on a 12,906-item workspace froze ImageDescriber for
95 seconds ("Not Responding"). These cover the open's own path and what the
review found around it. Opens a real (hidden) frame: runs in the VM and CI.
"""
import sys
import threading
import time
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
    yield f
    f.Destroy()
    app.ProcessPendingEvents()


@pytest.fixture
def bundle(tmp_path):
    from idt_core.workspace import Workspace, WorkspaceItem

    ws = Workspace.create(tmp_path / "w.idtw", name="w", copy_originals=False)
    for i in range(3):
        src = tmp_path / f"IMG_{i}.jpg"
        src.write_bytes(b"x")
        ws.save_item(WorkspaceItem(image=src.name, source_path=str(src), storage="reference"))
    return ws.path


def test_the_read_runs_off_the_ui_thread_and_loads(frame, bundle, monkeypatch):
    import idt_core.gui_bridge as bridge

    seen = {}
    real = bridge.bundle_to_gui_workspace_dict

    def spy(ws, progress=None):
        seen["thread"] = threading.current_thread() is threading.main_thread()
        return real(ws, progress=progress)

    monkeypatch.setattr(bridge, "bundle_to_gui_workspace_dict", spy)
    frame.load_workspace(str(bundle))
    assert seen["thread"] is False
    assert len(frame.workspace.items) == 3
    assert Path(frame.workspace_file) == Path(bundle)


def test_a_quick_open_shows_no_progress_window(frame, bundle, monkeypatch):
    opened = []
    real = frame._ensure_progress_dialog
    monkeypatch.setattr(frame, "_ensure_progress_dialog",
                        lambda *a, **k: (opened.append(1), real(*a, **k))[1])
    frame.load_workspace(str(bundle))
    assert opened == []
    assert frame.batch_progress_dialog is None


def test_a_slow_open_shows_it_and_closes_it(frame, bundle, monkeypatch):
    import idt_core.gui_bridge as bridge

    real = bridge.bundle_to_gui_workspace_dict
    monkeypatch.setattr(bridge, "bundle_to_gui_workspace_dict",
                        lambda ws, progress=None: (time.sleep(1.0), real(ws, progress))[1])
    opened = []
    real_ensure = frame._ensure_progress_dialog
    monkeypatch.setattr(frame, "_ensure_progress_dialog",
                        lambda *a, **k: (opened.append(1), real_ensure(*a, **k))[1])
    frame.load_workspace(str(bundle))
    assert opened == [1]
    assert frame.batch_progress_dialog is None   # closed again
    assert len(frame.workspace.items) == 3


def test_a_failed_read_leaves_the_open_workspace_alone(frame, bundle, monkeypatch):
    import idt_core.gui_bridge as bridge
    import imagedescriber_wx

    frame.load_workspace(str(bundle))
    before, before_file = frame.workspace, frame.workspace_file
    errors = []
    monkeypatch.setattr(imagedescriber_wx, "show_error", lambda parent, msg, *a, **k: errors.append(msg))

    def boom(ws, progress=None):
        raise OSError("disk went away")

    monkeypatch.setattr(bridge, "bundle_to_gui_workspace_dict", boom)
    frame.load_workspace(str(bundle))
    assert errors and "disk went away" in errors[-1]
    assert frame.workspace is before and frame.workspace_file == before_file


def test_a_running_folder_scan_is_stopped_first(frame, bundle):
    class Scan:
        stopped = False

        def stop(self):
            Scan.stopped = True

    frame.scan_worker = Scan()
    frame.load_workspace(str(bundle))
    assert Scan.stopped and frame.scan_worker is None


def test_the_update_check_waits_for_an_open(frame, monkeypatch):
    later = []
    monkeypatch.setattr(wx, "CallLater", lambda ms, fn, *a, **k: later.append((ms, fn)))
    frame._progress_pump_depth = 1
    try:
        frame._auto_check_updates()
    finally:
        frame._progress_pump_depth = 0
    assert later and later[0][1] == frame._auto_check_updates


def test_focus_goes_to_the_image_tree_after_opening(frame, bundle, monkeypatch):
    """#493: after Ctrl+O, focus stayed where the Open dialog left it."""
    calls, later = [], []
    monkeypatch.setattr(frame, "_focus_current_mode", lambda: calls.append("focus"))
    real_call_after = wx.CallAfter
    monkeypatch.setattr(wx, "CallAfter",
                        lambda fn, *a, **k: later.append(fn) if fn == frame._focus_current_mode
                        else real_call_after(fn, *a, **k))
    frame.load_workspace(str(bundle))
    assert frame._focus_current_mode in later       # queued, not done inline
    for fn in later:
        fn()
    assert calls == ["focus"]


def test_a_failed_open_does_not_move_focus(frame, bundle, monkeypatch):
    import idt_core.gui_bridge as bridge
    calls = []
    monkeypatch.setattr(frame, "_focus_current_mode", lambda: calls.append("focus"))
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *a, **k: fn(*a, **k))

    def broken(ws, progress=None):
        raise OSError("unreadable")
    monkeypatch.setattr(bridge, "bundle_to_gui_workspace_dict", broken)
    import imagedescriber_wx
    monkeypatch.setattr(imagedescriber_wx, "show_error", lambda *a, **k: None)
    frame.load_workspace(str(bundle))
    assert calls == []

