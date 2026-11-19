"""Viewer mode lists descriptions oldest first, newest last.

It sorted by file path, so Home and End stayed on the alphabetically first and
last pictures however many descriptions arrived, even after a refresh (Kelly,
11/19/2026). Kelly chose newest-last: End is always the latest description.

Opens a real (hidden) frame, so it runs in the test VM and CI.
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
    yield f
    f.Destroy()
    app.ProcessPendingEvents()


def _workspace(tmp_path):
    from data_models import ImageDescription, ImageItem, ImageWorkspace

    w = ImageWorkspace(new_workspace=True)
    # Path order is a, b, c; description order is c, a, b (then a again).
    made = [("c.jpg", "2026-11-18T09:00:00"), ("a.jpg", "2026-11-18T10:00:00"),
            ("b.jpg", "2026-11-18T11:00:00"), ("a.jpg", "2026-11-19T08:00:00")]
    for name, when in made:
        path = str(tmp_path / name)
        if path not in w.items:
            w.add_item(ImageItem(path))
        w.items[path].add_description(ImageDescription(f"{name} at {when}", "m", "narrative",
                                                       created=when))
    return w


def test_newest_description_is_last(frame, tmp_path):
    panel = frame.viewer_panel
    panel.load_from_workspace(_workspace(tmp_path))
    texts = [e["description"] for e in panel.entries]
    assert texts[-1] == "a.jpg at 2026-11-19T08:00:00"   # End: the latest
    assert texts[0] == "c.jpg at 2026-11-18T09:00:00"    # Home: the oldest
    assert panel.desc_list.GetCount() == 4


def test_unreadable_times_sort_first():
    import viewer_components

    key = viewer_components._created_sort_key
    assert key(None) == key("") == key("not a date") == 0.0
    assert key("2026-11-18T09:00:00") < key("2026-11-19T08:00:00")


def test_utc_and_local_times_are_ordered_by_the_instant_not_the_text():
    """Bundles from idt store UTC with a zone; ImageDescriber stores local time
    without one. Compared as text, the order would depend on the digits."""
    from datetime import datetime, timedelta, timezone

    import viewer_components

    key = viewer_components._created_sort_key
    utc = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
    local_just_before = utc.astimezone().replace(tzinfo=None) - timedelta(minutes=1)
    local_just_after = utc.astimezone().replace(tzinfo=None) + timedelta(minutes=1)
    assert (key(local_just_before.isoformat()) < key(utc.isoformat())
            < key(local_just_after.isoformat()))
    assert key("2026-11-18T15:00:00Z") == key(utc.isoformat())


def test_equal_times_keep_path_order_and_chats_come_after_pictures(frame, tmp_path):
    from data_models import ImageDescription, ImageItem, ImageWorkspace

    w = ImageWorkspace(new_workspace=True)
    when = "2026-11-18T09:00:00"
    for name in ("b.jpg", "a.jpg"):
        item = ImageItem(str(tmp_path / name))
        item.add_description(ImageDescription(name, "m", "narrative", created=when))
        w.add_item(item)
    chat = ImageItem("chat:chat_1", item_type="chat")
    chat.add_description(ImageDescription("A chat turn.", "m", "chat",
                                          created="2026-11-18T08:00:00"))   # oldest of all
    w.add_item(chat)
    panel = frame.viewer_panel
    panel.load_from_workspace(w)
    assert [e["description"] for e in panel.entries] == ["a.jpg", "b.jpg", "A chat turn."]
