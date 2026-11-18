"""The Descriptions menu acts on what Viewer mode shows, not the hidden editor (#480).

Kelly read a description in Viewer mode, chose Descriptions > Copy
Description, and was told there was no description to copy (11/18/2026).
Every handler read current_image_item, the image selected in Editor mode,
which had none yet. Edit and Delete would have changed that hidden image.

The clipboard is replaced by a recorder, and message boxes by stubs, so
nothing here needs a real clipboard or a person to dismiss a dialog.
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
def setup(frame, monkeypatch, tmp_path):
    """Editor selection: an image with no description. Viewer: one with two."""
    import imagedescriber_wx
    from data_models import ImageDescription, ImageItem, ImageWorkspace

    undescribed = tmp_path / "a_undescribed.jpg"
    described = tmp_path / "b_described.jpg"
    from PIL import Image
    for p in (undescribed, described):
        Image.new("RGB", (8, 8), "red").save(p)

    ws = ImageWorkspace(new_workspace=True)
    a = ImageItem(str(undescribed))
    b = ImageItem(str(described))
    b.add_description(ImageDescription("An older description.", "claude-haiku-5-5", "narrative"))
    b.add_description(ImageDescription("A red square.", "claude-haiku-5-5", "narrative"))
    ws.add_item(a)
    ws.add_item(b)
    frame.workspace = ws
    frame.current_image_item = a

    copied, warnings, infos = [], [], []
    monkeypatch.setattr(frame, "_copy_text_to_clipboard",
                        lambda text: copied.append(text) or True)
    monkeypatch.setattr(imagedescriber_wx, "show_warning",
                        lambda parent, msg, *a, **k: warnings.append(msg))
    monkeypatch.setattr(imagedescriber_wx, "show_info",
                        lambda parent, msg, *a, **k: infos.append(msg))
    monkeypatch.setattr(imagedescriber_wx, "ask_yes_no",
                        lambda *a, **k: pytest.fail("asked to delete in Viewer mode"))
    yield {"frame": frame, "a": a, "b": b, "copied": copied,
           "warnings": warnings, "infos": infos, "described": described}
    frame.switch_mode("editor")
    frame.current_mode = "editor"


def _show_viewer(frame, select_text):
    frame.switch_mode("viewer", frame.workspace)
    panel = frame.viewer_panel
    index = next(i for i, e in enumerate(panel.entries) if e["description"] == select_text)
    panel.desc_list.SetSelection(index)
    panel.on_selection_changed(None)


def test_copy_description_copies_the_one_being_read(setup):
    f = setup["frame"]
    _show_viewer(f, "An older description.")
    f.on_copy_description(None)
    assert setup["copied"] == ["An older description."]
    assert setup["warnings"] == []


def test_copy_description_follows_the_viewer_selection(setup):
    f = setup["frame"]
    _show_viewer(f, "A red square.")
    f.on_copy_description(None)
    assert setup["copied"] == ["A red square."]


def test_copy_image_path_is_the_viewed_image(setup):
    f = setup["frame"]
    _show_viewer(f, "A red square.")
    f.on_copy_image_path(None)
    assert len(setup["copied"]) == 1
    assert Path(setup["copied"][0]).name == "b_described.jpg"


def test_copyable_image_path_is_the_viewed_image(setup):
    f = setup["frame"]
    _show_viewer(f, "A red square.")
    assert Path(str(f._get_copyable_image_path())).name == "b_described.jpg"


@pytest.mark.parametrize("handler", ["on_edit_description", "on_delete_description",
                                     "on_add_manual_description", "on_followup_question"])
def test_changing_items_point_to_editor_mode_and_leave_the_hidden_image_alone(setup, handler):
    f = setup["frame"]
    _show_viewer(f, "A red square.")
    before_a = list(setup["a"].descriptions)
    before_b = [d.text for d in setup["b"].descriptions]
    getattr(f, handler)(None)
    assert setup["infos"] and "Editor mode" in setup["infos"][-1]
    assert setup["a"].descriptions == before_a
    assert [d.text for d in setup["b"].descriptions] == before_b


def test_editor_mode_still_uses_the_editor_selection(setup):
    f = setup["frame"]
    f.switch_mode("editor")
    f.current_image_item = setup["b"]
    f.on_copy_description(None)
    assert setup["copied"] == ["A red square."]   # the latest, as before
    f.current_image_item = setup["a"]
    f.on_copy_description(None)
    assert setup["warnings"] == ["No description to copy"]


def test_viewer_with_nothing_selected_says_so(setup, monkeypatch):
    f = setup["frame"]
    f.switch_mode("viewer", f.workspace)
    monkeypatch.setattr(f.viewer_panel, "selected_entry", lambda: None)
    f.on_copy_description(None)
    assert setup["copied"] == [] and setup["warnings"] == ["No description to copy"]
