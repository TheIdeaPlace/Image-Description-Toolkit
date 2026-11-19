"""
#403: a chat started in a workspace that was already saved as a .idtw bundle
was never written by File > Save (``_save_bundle`` skipped every ``chat:``
item), so closing and reopening the workspace lost it.

These are real save -> reopen round trips through ImageDescriberFrame, so they
open a wx frame: run them in the vmtest VM, not on a desktop.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture(scope="module")
def _frame():
    wx = pytest.importorskip("wx", reason="wxPython not installed in this environment")
    import imagedescriber_wx
    app = wx.App.Get() or wx.App(False)
    f = imagedescriber_wx.ImageDescriberFrame()
    yield f
    f.Destroy()
    wx.SafeYield()
    del app


@pytest.fixture
def frame(_frame, tmp_path, monkeypatch):
    """The frame with a saved 3-picture workspace open, as after File > Open."""
    import imagedescriber_wx
    from data_models import ImageItem, ImageWorkspace
    from idt_core.gui_bridge import BundleCheckpointWriter
    from idt_core.workspace import Workspace

    src = tmp_path / "photos"
    src.mkdir()
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        (src / n).write_bytes(b"x")
    bundle = Workspace.create(tmp_path / "lib.idtw").path
    ws = ImageWorkspace(new_workspace=True)
    ws.directory_paths = [str(src)]
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        ws.add_item(ImageItem(str(src / n)))
    f = _frame
    monkeypatch.setattr(f, "workspace", ws)
    monkeypatch.setattr(f, "workspace_file", bundle)
    monkeypatch.setattr(f, "_checkpointer", BundleCheckpointWriter())
    monkeypatch.setattr(f, "_changed_seq", {})
    monkeypatch.setattr(f, "refresh_image_list", lambda *a, **k: None)
    for name in ("show_error", "show_warning", "show_info"):
        monkeypatch.setattr(imagedescriber_wx, name, lambda *a, **k: None)
    f._save_bundle()                                   # everything on disk
    f._remember_saved(ws.to_dict()["items"], replace=True)
    return f


def _add_chat(ws, chat_id, *texts):
    from data_models import ImageDescription, ImageItem
    item = ImageItem(f"chat:{chat_id}", item_type="chat")
    item.display_name = f"Chat {chat_id}"
    for t in texts:
        item.add_description(ImageDescription(text=t, model="m", provider="ollama"))
    ws.add_item(item)
    return item


def _reopen(f):
    """Close and reopen through File > Open, as the user would."""
    import wx
    f.workspace.saved = True
    f.load_workspace(f.workspace_file)
    wx.SafeYield()
    return f.workspace


def test_a_chat_started_in_a_saved_workspace_survives_save_and_reopen(frame):
    f = frame
    before = f.workspace
    _add_chat(f.workspace, "chat_1", "User: hello", "Assistant: hi there")
    f._save_bundle()
    reopened = _reopen(f)
    assert reopened is not before, "the workspace was not reloaded from disk"
    chat = reopened.items.get("chat:chat_1")
    assert chat is not None, "the chat was lost on reopen"
    assert chat.item_type == "chat"
    assert chat.display_name == "Chat chat_1"
    assert [d.text for d in chat.descriptions] == ["User: hello", "Assistant: hi there"]
    # The pictures are still there too.
    assert {Path(k).name for k in reopened.items if not k.startswith("chat:")} == \
        {"a.jpg", "b.jpg", "c.jpg"}


def test_a_new_turn_in_an_existing_chat_survives_save_and_reopen(frame):
    import wx
    from data_models import ImageDescription
    f = frame
    chat = _add_chat(f.workspace, "chat_2", "User: one")
    f._save_bundle()
    wx.SafeYield()
    chat.add_description(ImageDescription(text="Assistant: two", model="m"))
    f._save_bundle()
    reopened = _reopen(f)
    assert [d.text for d in reopened.items["chat:chat_2"].descriptions] == \
        ["User: one", "Assistant: two"]


def test_the_progress_save_writes_chats_too(frame):
    """File > Save on a saved workspace goes through the off-thread path."""
    import wx
    f = frame
    _add_chat(f.workspace, "chat_3", "User: via progress")
    names = []
    f._save_bundle(progress=lambda done, total, name: names.append(name),
                   ws_dict=f.workspace.to_dict(),
                   snap_seq=f._checkpointer.snapshot_seq())
    wx.SafeYield()
    assert names == ["Chat chat_3"]
    reopened = _reopen(f)
    assert "chat:chat_3" in reopened.items


def test_an_unchanged_chat_missing_from_disk_is_written(frame):
    """A save before the fix recorded the chat as saved without writing it."""
    from idt_core.workspace import Workspace
    f = frame
    _add_chat(f.workspace, "chat_4", "User: lost before")
    f._remember_saved(f.workspace.to_dict()["items"])     # as the old save did
    chat_file = Workspace(f.workspace_file).chats_dir / "chat_4.json"
    assert not chat_file.exists()
    f._save_bundle()
    assert chat_file.exists()
    reopened = _reopen(f)
    assert [d.text for d in reopened.items["chat:chat_4"].descriptions] == \
        ["User: lost before"]


def test_an_unchanged_chat_on_disk_is_not_rewritten(frame, monkeypatch):
    import wx
    from idt_core.workspace import Workspace
    f = frame
    _add_chat(f.workspace, "chat_5", "User: once")
    f._save_bundle()
    wx.SafeYield()
    calls = []
    real = Workspace.save_chat

    def spy(self, c):
        calls.append(c["id"])
        return real(self, c)

    monkeypatch.setattr(Workspace, "save_chat", spy)
    f._save_bundle()
    assert calls == []
