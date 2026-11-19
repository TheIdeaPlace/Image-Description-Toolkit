"""
GUI checks for the 4.9.0 group EF fixes. These open wx windows: run them in the
vmtest VM, not on a desktop.

* #423: the Descriptions list of a picture with no descriptions was empty, read
  as "unknown" twice; and Clear()/Set() left the accessible object answering
  with the previous picture's descriptions.
* #424: the editor no longer starts with a blank line.
* #498: the folder context menu opens from the Applications key / Shift+F10
  (EVT_TREE_ITEM_MENU), not only a mouse right-click.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

wx = pytest.importorskip("wx", reason="wxPython not installed in this environment")


@pytest.fixture(scope="module")
def frame():
    import imagedescriber_wx
    app = wx.App.Get() or wx.App(False)
    f = imagedescriber_wx.ImageDescriberFrame()
    yield f
    f.Destroy()
    wx.SafeYield()
    del app


# ---- #423 ------------------------------------------------------------------

def test_an_undescribed_picture_lists_one_entry_that_says_so(frame, tmp_path):
    import imagedescriber_wx
    from data_models import ImageDescription, ImageItem
    described = ImageItem(str(tmp_path / "a.jpg"))
    described.add_description(ImageDescription(text="a red barn", model="m"))
    frame.display_image_info(described)
    assert frame.desc_list.GetCount() == 1

    empty = ImageItem(str(tmp_path / "b.jpg"))
    frame.display_image_info(empty)
    assert frame.desc_list.GetCount() == 1
    assert frame.desc_list.GetString(0) == imagedescriber_wx.NO_DESCRIPTIONS_ENTRY
    assert frame.desc_list.GetSelection() == 0
    acc = frame.desc_list.custom_accessible
    if acc is not None:                       # Windows only
        assert acc.GetName(1) == (wx.ACC_OK, imagedescriber_wx.NO_DESCRIPTIONS_ENTRY)
        assert "a red barn" not in str(acc.GetName(1))
    # Selecting the entry does nothing to the editor (there is no description).
    frame.current_image_item = empty
    frame.on_description_selected(None)
    assert frame.description_text.GetValue() == ""


def test_clear_and_set_drop_the_previous_descriptions(frame):
    from shared import wx_common
    lst = wx_common.DescriptionListBox(frame)
    try:
        lst.LoadDescriptions([{"description": "old picture's description"}])
        lst.Clear()
        assert lst.descriptions_data == []
        if lst.custom_accessible is not None:
            assert lst.custom_accessible.descriptions_data == []
            assert lst.custom_accessible.GetName(1)[0] == wx.ACC_NOT_IMPLEMENTED
        lst.LoadDescriptions([{"description": "again"}])
        lst.Set(["You: hello", "AI: hi"])
        assert lst.GetCount() == 2
        assert lst.descriptions_data == []
        if lst.custom_accessible is not None:
            assert lst.custom_accessible.GetName(1)[0] == wx.ACC_NOT_IMPLEMENTED
    finally:
        lst.Destroy()


# ---- #424 ------------------------------------------------------------------

def test_the_editor_starts_with_the_description_not_a_blank_line(frame, tmp_path):
    from data_models import ImageDescription, ImageItem
    item = ImageItem(str(tmp_path / "c.jpg"))
    item.add_description(ImageDescription(text="\nA lighthouse at dusk.", model="m"))
    frame.display_image_info(item)
    assert frame.description_text.GetValue().startswith("A lighthouse at dusk.")


# ---- #498 ------------------------------------------------------------------

@pytest.mark.skipif(sys.platform == "darwin", reason="Windows TreeCtrl event")
def test_the_keyboard_context_menu_opens_the_folder_menu(frame, tmp_path, monkeypatch):
    from data_models import ImageWorkspace
    monkeypatch.setattr(frame, "workspace", ImageWorkspace(new_workspace=True))
    tree = frame.image_list
    root = frame._image_tree_root
    folder = tree.AppendItem(root, "Vacation")
    monkeypatch.setattr(frame, "_folder_abs_paths", {"Vacation": str(tmp_path)})

    shown = []

    def fake_popup(menu, *args):
        shown.append([menu.FindItemByPosition(i).GetItemLabelText()
                      for i in range(menu.GetMenuItemCount())])
        return True

    monkeypatch.setattr(frame, "PopupMenu", fake_popup)
    try:
        # What wxMSW sends for the Applications key or Shift+F10.
        event = wx.TreeEvent(wx.wxEVT_TREE_ITEM_MENU, tree, folder)
        tree.GetEventHandler().ProcessEvent(event)
        assert shown == [["Refresh Folder from Disk…"]]
        assert tree.GetSelection() == folder
    finally:
        tree.Delete(folder)


@pytest.mark.skipif(sys.platform == "darwin", reason="Windows TreeCtrl event")
def test_a_picture_node_gets_no_menu(frame, tmp_path, monkeypatch):
    tree = frame.image_list
    leaf = tree.AppendItem(frame._image_tree_root, "a.jpg", data=str(tmp_path / "a.jpg"))
    shown = []
    monkeypatch.setattr(frame, "PopupMenu", lambda *a: shown.append(a) or True)
    try:
        tree.GetEventHandler().ProcessEvent(
            wx.TreeEvent(wx.wxEVT_TREE_ITEM_MENU, tree, leaf))
        assert shown == []
    finally:
        tree.Delete(leaf)
