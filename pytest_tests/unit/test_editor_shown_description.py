"""Editor mode acts on the description being shown, and Save leaves out the details (#482, #449).

Save Description, Copy Description, Edit and Delete always used the image's
latest description. Editing an older one in the editor and pressing Save
overwrote the newest with it. Save also stored the details block the editor
shows under the description (Provider, Model, Prompt...), so it ended up in
exports and embedded metadata, and a second block appeared the next time.

The clipboard and message boxes are stubbed; nothing here needs a person.
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

TEXTS = ["First description.", "Second description.\n\n---\n\nWith a rule of its own.",
         "Third and latest description."]


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
    import imagedescriber_wx
    from data_models import ImageDescription, ImageItem, ImageWorkspace
    from PIL import Image

    pic = tmp_path / "pic.jpg"
    Image.new("RGB", (8, 8), "red").save(pic)
    ws = ImageWorkspace(new_workspace=True)
    item = ImageItem(str(pic))
    for text in TEXTS:
        item.add_description(ImageDescription(text, "claude-haiku-5-5", "narrative",
                                              provider="claude"))
    ws.add_item(item)
    frame.workspace = ws
    frame.switch_mode("editor")
    frame.current_image_item = item
    frame.display_image_info(item)

    copied, warnings, asked = [], [], []
    monkeypatch.setattr(frame, "_copy_text_to_clipboard",
                        lambda text: copied.append(text) or True)
    monkeypatch.setattr(imagedescriber_wx, "show_warning",
                        lambda parent, msg, *a, **k: warnings.append(msg))
    monkeypatch.setattr(imagedescriber_wx, "ask_yes_no",
                        lambda parent, msg, *a, **k: asked.append(msg) or True)
    return {"frame": frame, "item": item, "copied": copied, "warnings": warnings,
            "asked": asked, "tmp": tmp_path}


def _select(frame, index):
    frame.desc_list.SetSelection(index)
    frame.on_description_selected(None)


def _texts(item):
    return [d.text for d in item.descriptions]


def test_save_edits_the_one_shown_and_leaves_the_latest_alone(setup):
    f, item = setup["frame"], setup["item"]
    _select(f, 1)
    shown = f.description_text.GetValue()
    assert "Model:" in shown   # the details block is shown, as before
    f.description_text.SetValue(shown.replace("Second description.", "Second, edited."))
    f.on_save_description(None)
    assert _texts(item) == [TEXTS[0], TEXTS[1].replace("Second description.", "Second, edited."),
                            TEXTS[2]]


def test_save_leaves_out_the_details_block(setup):
    """#449: and keeps the description's own "---"."""
    f, item = setup["frame"], setup["item"]
    _select(f, 1)
    f.on_save_description(None)
    assert item.descriptions[1].text == TEXTS[1]
    assert "Provider:" not in item.descriptions[1].text


def test_saving_twice_adds_no_second_block(setup):
    f, item = setup["frame"], setup["item"]
    _select(f, 0)
    f.on_save_description(None)
    _select(f, 0)
    f.on_save_description(None)
    assert item.descriptions[0].text == TEXTS[0]


def test_text_typed_after_the_details_is_kept(setup):
    """Ctrl+End puts the caret after the details; what's typed there is the
    user's, so only the block goes (#484 review: it was silently dropped)."""
    f, item = setup["frame"], setup["item"]
    _select(f, 0)
    shown = f.description_text.GetValue()
    f.description_text.SetValue(shown + "\nA note typed after the details.")
    f.on_save_description(None)
    assert item.descriptions[0].text == TEXTS[0] + "\nA note typed after the details."
    assert "Provider:" not in item.descriptions[0].text


def test_an_edited_details_block_is_not_saved_and_the_user_is_told(setup):
    f, item = setup["frame"], setup["item"]
    _select(f, 0)
    shown = f.description_text.GetValue()
    f.description_text.SetValue(shown.replace("Prompt:", "Prompt was:"))
    f.on_save_description(None)
    assert _texts(item) == TEXTS
    assert "details shown with the description were changed" in setup["warnings"][-1]


def test_deleting_the_details_saves_the_description(setup):
    f, item = setup["frame"], setup["item"]
    _select(f, 1)
    f.description_text.SetValue("Just the description now.")
    f.on_save_description(None)
    assert item.descriptions[1].text == "Just the description now."


def test_download_and_image_info_blocks_are_left_out_too(setup):
    """Those blocks put a blank line after the "---", the same shape as a
    description's own rule (TEXTS[1])."""
    f, item = setup["frame"], setup["item"]
    item.download_url = "https://example.com/pic.jpg"
    item.download_timestamp = "2026-11-18T10:00:00"
    item.descriptions[1].metadata = {"camera": "iPhone 15", "datetime": "2026:11:18 10:00:00"}
    _select(f, 1)
    shown = f.description_text.GetValue()
    assert "Download Source" in shown
    f.on_save_description(None)
    assert item.descriptions[1].text == TEXTS[1]


def test_the_first_description_is_shown_on_opening_and_is_what_save_changes(setup):
    """display_image_info shows the first; Save used to write the latest."""
    f, item = setup["frame"], setup["item"]
    shown = f.description_text.GetValue()
    f.description_text.SetValue(shown.replace("First description.", "First, edited."))
    f.on_save_description(None)
    assert _texts(item) == ["First, edited.", TEXTS[1], TEXTS[2]]


def test_copy_description_copies_the_one_shown(setup):
    f = setup["frame"]
    _select(f, 1)
    f.on_copy_description(None)
    assert setup["copied"] == [TEXTS[1]]


def test_delete_deletes_the_one_shown_and_says_which(setup):
    f, item = setup["frame"], setup["item"]
    _select(f, 1)
    f.on_delete_description(None)
    assert "description 2 of 3, by Claude Haiku 5.5" in setup["asked"][-1]
    assert "Second description." in setup["asked"][-1]
    assert _texts(item) == [TEXTS[0], TEXTS[2]]
    # The editor moves to the one that took its place, not back to the first.
    assert f.desc_list.GetSelection() == 1
    assert f.description_text.GetValue().startswith(TEXTS[2])


def test_delete_question_ends_a_long_description_at_a_word(setup):
    f, item = setup["frame"], setup["item"]
    item.descriptions[0].text = "A large tabby cat sitting on a wooden windowsill looking out at the garden beyond."
    f.display_image_info(item)
    f.on_delete_description(None)
    assert setup["asked"][-1].endswith("out at the garden…")   # not "beyon"


def test_follow_up_is_about_the_description_shown(setup, monkeypatch):
    """The list has no selection after opening an image, so Follow-up used
    the latest while the editor showed the first (#484 review)."""
    import dialogs_wx

    seen = {}

    class FakeFollowup:
        def __init__(self, parent, provider, model, existing, *a, **k):
            seen["existing"] = existing

        def ShowModal(self):
            return wx.ID_CANCEL

        def Destroy(self):
            pass

    monkeypatch.setattr(dialogs_wx, "FollowupQuestionDialog", FakeFollowup)
    f = setup["frame"]
    f.display_image_info(setup["item"])
    f.on_followup_question(None)
    assert seen["existing"].startswith(TEXTS[0])


def test_chat_edit_stays_on_the_turn_and_delete_says_message(setup, monkeypatch):
    from data_models import ImageDescription, ImageItem

    f = setup["frame"]
    chat = ImageItem("chat:chat_1", item_type="chat")
    for i in range(4):
        style = "user_question" if i % 2 == 0 else "chat"
        chat.add_description(ImageDescription(f"Turn {i + 1}.", "claude-haiku-5-5", style,
                                              provider="claude"))
    f.workspace.add_item(chat)
    f.current_image_item = chat
    f.display_image_info(chat)
    f._show_description(1)

    class FakeDialog:
        def __init__(self, *a, **k):
            pass

        def SetSize(self, *a):
            pass

        def ShowModal(self):
            return wx.ID_OK

        def GetValue(self):
            return "Turn 2, edited."

        def Destroy(self):
            pass

    monkeypatch.setattr(wx, "TextEntryDialog", FakeDialog)
    f.on_edit_description(None)
    assert [d.text for d in chat.descriptions][1] == "Turn 2, edited."
    assert f.desc_list.GetSelection() == 1
    assert f.description_text.GetValue() == "Turn 2, edited."
    f._show_description(0)
    f.on_delete_description(None)
    assert setup["asked"][-1].startswith("Delete message 1 of 4?")   # the user's own turn: no "by"


def test_edit_edits_the_one_shown(setup, monkeypatch):
    f, item = setup["frame"], setup["item"]

    class FakeDialog:
        def __init__(self, parent, message, caption, value, style=0):
            FakeDialog.value = value

        def SetSize(self, *a):
            pass

        def ShowModal(self):
            return wx.ID_OK

        def GetValue(self):
            return "Rewritten."

        def Destroy(self):
            pass

    monkeypatch.setattr(wx, "TextEntryDialog", FakeDialog)
    _select(f, 1)
    f.on_edit_description(None)
    assert FakeDialog.value == TEXTS[1]
    assert _texts(item) == [TEXTS[0], "Rewritten.", TEXTS[2]]
    assert f.desc_list.GetSelection() == 1   # still on the one just edited


def test_saving_a_videos_details_is_refused(setup):
    from data_models import ImageItem

    f = setup["frame"]
    video = ImageItem(str(setup["tmp"] / "clip.mp4"), item_type="video")
    video.video_metadata = {"duration": 65, "fps": 30.0, "total_frames": 1950}
    f.workspace.add_item(video)
    f.current_image_item = video
    f.display_image_info(video)
    assert "Video Metadata" in f.description_text.GetValue()
    f.on_save_description(None)
    assert video.descriptions == []
    assert "video's details" in setup["warnings"][-1]


def test_a_description_typed_for_a_video_is_saved(setup):
    from data_models import ImageItem

    f = setup["frame"]
    video = ImageItem(str(setup["tmp"] / "clip2.mp4"), item_type="video")
    f.workspace.add_item(video)
    f.current_image_item = video
    f.display_image_info(video)
    f.description_text.SetValue("A dog runs across a lawn.")
    f.on_save_description(None)
    assert [d.text for d in video.descriptions] == ["A dog runs across a lawn."]


def test_text_typed_above_a_videos_details_is_saved_without_them(setup):
    from data_models import ImageItem

    f = setup["frame"]
    video = ImageItem(str(setup["tmp"] / "clip3.mp4"), item_type="video")
    video.video_metadata = {"duration": 65, "fps": 30.0}
    f.workspace.add_item(video)
    f.current_image_item = video
    f.display_image_info(video)
    f.description_text.SetValue("A dog runs across a lawn.\n" + f.description_text.GetValue())
    f.on_save_description(None)
    assert [d.text for d in video.descriptions] == ["A dog runs across a lawn."]
