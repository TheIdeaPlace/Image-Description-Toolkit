"""Changing one picture relabels its entry; it doesn't rebuild the image list.

Kelly, 11/18/2026: in a 12,906-item workspace every P on one picture froze
ImageDescriber ("Not Responding") as the Process dialog closed and again when
the description came back. refresh_image_list rebuilt the whole tree each
time, 10 seconds on the UI thread. Adding a manual description didn't update
the list at all (#429).

Opens a real (hidden) frame, so it runs in the test VM and CI.
"""
import sys
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
def ws(frame, tmp_path, monkeypatch):
    from data_models import ImageItem, ImageWorkspace

    w = ImageWorkspace(new_workspace=True)
    for i in range(300):
        p = tmp_path / "Photos" / f"IMG_{i:04d}.jpg"
        item = ImageItem(str(p))
        item.subfolder = "Photos"
        item.file_mtime = 1_600_000_000 + i
        w.add_item(item)
    frame.workspace = w
    frame.current_filter = "all"
    frame.search_filter_text = ""
    frame.processing_items = {}
    frame.refresh_image_list()
    rebuilds = []
    real = frame.refresh_image_list
    monkeypatch.setattr(frame, "refresh_image_list", lambda: (rebuilds.append(1), real()))
    return w, rebuilds


def _label(frame, path):
    return frame.image_list.GetItemText(frame._tree_nodes[path])


def test_a_new_description_relabels_without_a_rebuild(frame, ws):
    from data_models import ImageDescription

    w, rebuilds = ws
    path = next(iter(w.items))
    w.items[path].add_description(ImageDescription("A cat.", "claude-haiku-5-5", "narrative"))
    frame.refresh_image_label(path)
    assert _label(frame, path) == "d1 " + Path(path).name
    assert rebuilds == []


def test_p_while_processing_comes_and_goes(frame, ws):
    w, rebuilds = ws
    path = list(w.items)[5]
    frame.processing_items[path] = {"provider": "claude", "model": "claude-haiku-5-5"}
    frame.refresh_image_label(path)
    assert _label(frame, path) == "P " + Path(path).name
    frame.processing_items.pop(path)
    frame.refresh_image_label(path)
    assert _label(frame, path) == Path(path).name
    assert rebuilds == []


def test_a_filter_that_changes_what_shows_still_rebuilds(frame, ws):
    """Under Undescribed Only, a described picture must leave the list."""
    from data_models import ImageDescription

    w, rebuilds = ws
    frame.current_filter = "undescribed"
    path = list(w.items)[7]
    w.items[path].add_description(ImageDescription("A dog.", "claude-haiku-5-5", "narrative"))
    frame.refresh_image_label(path)
    assert rebuilds == [1]
    assert path not in frame._tree_nodes


def test_a_search_still_rebuilds(frame, ws):
    w, rebuilds = ws
    frame.search_filter_text = "IMG"
    frame.refresh_image_label(list(w.items)[3])
    assert rebuilds == [1]


def test_an_item_not_in_the_tree_rebuilds(frame, ws, tmp_path):
    from data_models import ImageItem

    w, rebuilds = ws
    new = ImageItem(str(tmp_path / "Photos" / "IMG_new.jpg"))
    new.subfolder = "Photos"
    w.add_item(new)
    frame.refresh_image_label(new.file_path)
    assert rebuilds == [1]
    assert new.file_path in frame._tree_nodes


def test_relabelling_is_much_faster_than_a_rebuild(frame, ws):
    from data_models import ImageDescription

    w, _ = ws
    path = list(w.items)[9]
    start = time.perf_counter()
    frame.refresh_image_list()
    rebuild = time.perf_counter() - start
    w.items[path].add_description(ImageDescription("A boat.", "claude-haiku-5-5", "narrative"))
    start = time.perf_counter()
    frame.refresh_image_label(path)
    relabel = time.perf_counter() - start
    assert relabel < rebuild / 10


def test_tree_knows_whether_a_batch_needs_a_rebuild(frame, ws, tmp_path):
    """_launch_batch_impl rebuilds only for images the tree doesn't show yet
    (frames just extracted); otherwise the rebuild changed nothing."""
    from data_models import ImageItem

    w, _ = ws
    assert not frame._tree_lacks_any(list(w.items))           # all shown: no rebuild
    new_frame = ImageItem(str(tmp_path / "frames" / "clip_0.00s.jpg"), item_type="extracted_frame")
    w.add_item(new_frame)
    assert frame._tree_lacks_any(list(w.items))               # a new frame: rebuild
    frame.search_filter_text = "IMG"
    assert frame._tree_lacks_any([list(w.items)[0]])          # a search: rebuild


def test_adding_a_manual_description_updates_the_count(frame, ws, monkeypatch):
    """#429: the list kept saying no description after one was added."""
    w, rebuilds = ws
    path = list(w.items)[11]
    frame.current_mode = "editor"
    frame.current_image_item = w.items[path]

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def SetSize(self, *a):
            pass

        def ShowModal(self):
            return wx.ID_OK

        def GetValue(self):
            return "Written by hand."

        def Destroy(self):
            pass

    monkeypatch.setattr(wx, "TextEntryDialog", FakeDialog)
    frame.on_add_manual_description(None)
    assert _label(frame, path) == "d1 " + Path(path).name
    assert rebuilds == []
