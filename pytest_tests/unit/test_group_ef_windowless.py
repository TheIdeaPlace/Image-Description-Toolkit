"""
Windowless checks for the 4.9.0 group EF fixes in ImageDescriber.

* #424: descriptions are stored and shown without the leading line break some
  models open with (the editor started on a blank line, read as "blank").
* #479: the text export's "Total Images" counted videos and chats.
* #426: the save prompts said "bundle" and "<name>", read as "less than name
  greater than".
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ---- #424 ------------------------------------------------------------------

def test_a_new_gui_description_loses_the_leading_line_break():
    from data_models import ImageDescription
    d = ImageDescription(text="\n\nA red barn in a field.\n", model="m")
    assert d.text == "A red barn in a field."


def test_a_description_loaded_from_an_older_workspace_is_stripped_too():
    from data_models import ImageDescription
    d = ImageDescription.from_dict({"text": "\nA red barn.", "model": "m", "id": "1"})
    assert d.text == "A red barn."
    assert d.to_dict()["text"] == "A red barn."


def test_inner_line_breaks_are_kept():
    from data_models import ImageDescription
    text = "First paragraph.\n\nSecond paragraph."
    assert ImageDescription(text="\n" + text).text == text


def test_a_cli_description_is_stored_without_the_line_break():
    from idt_core.workspace import WorkspaceDescription
    d = WorkspaceDescription.create("\nA red barn.\n", provider="ollama", model="m")
    assert d.text == "A red barn."


def test_a_cli_description_saved_before_the_fix_reads_cleanly():
    from idt_core.workspace import WorkspaceDescription
    d = WorkspaceDescription.from_dict({"id": "1", "text": "\r\n\nA red barn."})
    assert d.text == "A red barn."


def test_the_first_line_keeps_its_indentation():
    """Only blank lines go: an indented code block or text picture is kept."""
    from data_models import ImageDescription
    assert ImageDescription(text="\n    indented code\nmore").text == "    indented code\nmore"
    assert ImageDescription(text="  \n\t\n  x").text == "  x"


def test_an_empty_or_missing_text_is_left_alone():
    from data_models import ImageDescription
    assert ImageDescription(text="").text == ""
    assert ImageDescription(text=None).text is None


# ---- #479 ------------------------------------------------------------------

def _frame_module():
    pytest.importorskip("wx", reason="wxPython not installed in this environment")
    import imagedescriber_wx
    return imagedescriber_wx


def test_the_text_export_counts_pictures_only(tmp_path):
    mod = _frame_module()
    from data_models import ImageDescription, ImageItem, ImageWorkspace
    ws = ImageWorkspace(new_workspace=True)
    for name in ("a.jpg", "b.jpg"):
        item = ImageItem(str(tmp_path / name))
        item.add_description(ImageDescription(text=f"{name} described", model="m"))
        ws.add_item(item)
    ws.add_item(ImageItem(str(tmp_path / "undescribed.jpg")))
    ws.add_item(ImageItem(str(tmp_path / "clip.mp4"), item_type="video"))
    frame = ImageItem(str(tmp_path / "clip_0001.jpg"), item_type="extracted_frame")
    ws.add_item(frame)
    chat = ImageItem("chat:chat_1", item_type="chat")
    chat.add_description(ImageDescription(text="User: hi", model="m"))
    ws.add_item(chat)

    fake = SimpleNamespace(workspace=ws, _format_metadata_for_export=lambda m: "")
    out = tmp_path / "export.txt"
    mod.ImageDescriberFrame.export_descriptions_to_text(fake, str(out))
    text = out.read_text(encoding="utf-8")
    # The total matches the entries listed: the two described pictures.
    assert "Total Images: 2\n" in text
    assert text.count("\nFile: ") == 2
    assert "chat" not in text.lower()


# ---- #426 ------------------------------------------------------------------

def test_the_workspace_name_prompt_has_no_placeholder_or_jargon():
    mod = _frame_module()
    prompt = mod.WORKSPACE_NAME_PROMPT
    assert "<" not in prompt and ">" not in prompt
    assert "bundle" not in prompt.lower()
    assert prompt.startswith("Workspace name")


def test_the_save_dialogs_no_longer_say_bundle():
    source = (_ROOT / "imagedescriber" / "imagedescriber_wx.py").read_text(encoding="utf-8")
    assert "create the bundle inside" not in source
    assert "<name>.idtw" not in source
