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


def test_undated_descriptions_come_first_in_path_order(tmp_path):
    import viewer_components

    key = viewer_components._created_sort_key
    assert key(None) == key("") == key("not a date") == 0.0
    assert key("2026-11-18T09:00:00") < key("2026-11-19T08:00:00")
    # With and without a time zone both parse (string comparison would not
    # order these correctly in every case).
    assert key("2026-11-18T11:00:00Z") > 0 and key("2026-11-18T11:00:00+00:00") > 0
