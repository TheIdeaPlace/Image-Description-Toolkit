"""ImageDescriber: the usage line stays in its views, off the clipboard and exports.

Kelly (11/18/2026): the "[Token Usage: ... | Time: ...]" line "should be kept
with the description but out everyplace else". These cover the wx paths:
Copy Description and Copy Image + Description (Editor and Viewer mode), the
Viewer's Copy Text button, Export Descriptions (text and HTML), Embed
Descriptions with "all", chat history sent back to a model, and the
statistics dialog's word counts (which missed the Time-only form).

The clipboard, dialogs and message boxes are replaced by recorders, so nothing
here needs a real clipboard or a person. The wx-free boundaries are in
test_usage_line_outside.py.
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

BODY = "Madison, Wisconsin - A red barn under a grey sky."
USAGE = "\n\n[Token Usage: 4,196 total (3,000 prompt + 1,196 completion) | Time: 8.12s]"
OLDER = "An older description."
OLDER_USAGE = "\n\n[Time: 3.40s]"


def _no_usage(text):
    assert "[Token Usage" not in text
    assert "[Time:" not in text


@pytest.fixture(scope="module")
def frame():
    import imagedescriber_wx
    app = wx.App.Get() or wx.App(False)
    f = imagedescriber_wx.ImageDescriberFrame()
    f.Show()
    yield f
    f.Destroy()
    app.ProcessPendingEvents()


class _FakeClipboard:
    def __init__(self):
        self.data = []

    def Open(self):
        return True

    def SetData(self, obj):
        self.data.append(obj)
        return True

    def Close(self):
        pass


@pytest.fixture
def setup(frame, monkeypatch, tmp_path):
    import imagedescriber_wx
    from data_models import ImageDescription, ImageItem, ImageWorkspace
    from PIL import Image

    pic = tmp_path / "barn.jpg"
    Image.new("RGB", (8, 8), "red").save(pic)
    ws = ImageWorkspace(new_workspace=True)
    item = ImageItem(str(pic))
    item.add_description(ImageDescription(OLDER + OLDER_USAGE, "claude-haiku-5-5", "narrative",
                                          provider="claude"))
    item.add_description(ImageDescription(BODY + USAGE, "claude-haiku-5-5", "narrative",
                                          provider="claude"))
    ws.add_item(item)
    frame.workspace = ws
    frame.switch_mode("editor")
    frame.current_image_item = item
    frame.display_image_info(item)

    copied, warnings, texts = [], [], []
    monkeypatch.setattr(frame, "_copy_text_to_clipboard",
                        lambda text: copied.append(text) or True)
    monkeypatch.setattr(imagedescriber_wx, "show_warning",
                        lambda parent, msg, *a, **k: warnings.append(msg))
    monkeypatch.setattr(imagedescriber_wx, "show_info", lambda *a, **k: None)
    clipboard = _FakeClipboard()
    monkeypatch.setattr(wx, "TheClipboard", clipboard)
    real_text_obj = wx.TextDataObject
    monkeypatch.setattr(wx, "TextDataObject",
                        lambda text="": texts.append(text) or real_text_obj(text))
    yield {"frame": frame, "item": item, "copied": copied, "warnings": warnings,
           "texts": texts, "tmp": tmp_path, "pic": pic}
    frame.viewer_panel.current_dir = None
    frame.switch_mode("editor")
    frame.current_mode = "editor"


def _select(frame, index):
    frame.desc_list.SetSelection(index)
    frame.on_description_selected(None)


def _show_viewer(frame, starts_with):
    frame.switch_mode("viewer", frame.workspace)
    panel = frame.viewer_panel
    index = next(i for i, e in enumerate(panel.entries)
                 if e["description"].startswith(starts_with))
    panel.desc_list.SetSelection(index)
    panel.on_selection_changed(None)
    return panel


# ------------------------------------------------------------------ #
# The reading views keep it                                            #
# ------------------------------------------------------------------ #

def test_the_editor_still_shows_it(setup):
    f = setup["frame"]
    _select(f, 1)
    assert "[Token Usage: 4,196 total" in f.description_text.GetValue()


def test_viewer_mode_still_shows_it(setup):
    panel = _show_viewer(setup["frame"], BODY)
    assert "[Token Usage: 4,196 total" in panel.desc_text.GetValue()


def test_the_stored_text_keeps_it(setup):
    f = setup["frame"]
    _select(f, 1)
    f.on_copy_description(None)
    assert setup["item"].descriptions[1].text == BODY + USAGE


# ------------------------------------------------------------------ #
# Copy Description / Copy Image + Description                          #
# ------------------------------------------------------------------ #

def test_copy_description_in_editor_mode(setup):
    f = setup["frame"]
    _select(f, 1)
    f.on_copy_description(None)
    assert setup["copied"] == [BODY]


def test_copy_description_time_only_form(setup):
    f = setup["frame"]
    _select(f, 0)
    f.on_copy_description(None)
    assert setup["copied"] == [OLDER]


def test_copy_description_in_viewer_mode(setup):
    f = setup["frame"]
    _show_viewer(f, BODY)
    f.on_copy_description(None)
    assert setup["copied"] == [BODY]


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS puts UTF-8 bytes on the clipboard")
def test_copy_image_and_description(setup):
    f = setup["frame"]
    _select(f, 1)
    f.on_copy_image_and_description(None)
    assert setup["texts"] == [BODY]
    assert setup["warnings"] == []


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS copies through pbcopy")
def test_viewer_copy_text_button(setup):
    panel = _show_viewer(setup["frame"], BODY)
    shown = panel.desc_text.GetValue()
    panel.on_copy_text(None)
    assert len(setup["texts"]) == 1
    copied = setup["texts"][0]
    _no_usage(copied)
    assert copied.startswith(BODY)
    # The details footer the box shows is still copied, as before.
    assert copied == shown.replace(USAGE, "")


# ------------------------------------------------------------------ #
# Export Descriptions and Embed Descriptions                           #
# ------------------------------------------------------------------ #

def test_export_descriptions_text(setup):
    out = setup["tmp"] / "export.txt"
    setup["frame"].export_descriptions_to_text(str(out))
    text = out.read_text(encoding="utf-8")
    _no_usage(text)
    assert f"Description: {BODY}\n" in text
    assert f"Description: {OLDER}\n" in text


def test_export_descriptions_html(setup):
    out = setup["tmp"] / "export.html"
    setup["frame"].export_descriptions_to_html(str(out))
    html = out.read_text(encoding="utf-8")
    _no_usage(html)
    assert "Madison, Wisconsin - A red barn" in html


@pytest.mark.parametrize("selection", ["latest", "all"])
def test_embed_descriptions(setup, monkeypatch, selection):
    import imagedescriber_wx
    import idt_core.embedder as embedder
    f = setup["frame"]
    out_dir = setup["tmp"] / "embedded"

    class _Dlg:
        def __init__(self, *a, **k):
            pass

        def ShowModal(self):
            return wx.ID_OK

        def get_mode(self):
            return "copy"

        def get_output_dir(self):
            return out_dir

        def get_description_selection(self):
            return selection

        def Destroy(self):
            pass

    embedded = []
    monkeypatch.setattr(imagedescriber_wx, "EmbedDescriptionsDialog", _Dlg)
    monkeypatch.setattr(embedder, "embed_image_file",
                        lambda src, text, dest, **k: embedded.append(text))
    monkeypatch.setattr(f, "_run_with_progress",
                        lambda title, total, work: work(lambda *a: None))
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: wx.NO)
    f.on_embed_descriptions(None)
    assert len(embedded) == 1
    _no_usage(embedded[0])
    if selection == "all":
        assert embedded[0] == f"{OLDER}\n\n---\n\n{BODY}"
    else:
        assert embedded[0] == BODY


# ------------------------------------------------------------------ #
# Chat history sent back to a model                                    #
# ------------------------------------------------------------------ #

def test_chat_history_sent_to_the_model(setup):
    from chat_window_wx import ChatWindow
    from data_models import ImageDescription, ImageItem
    chat = ImageItem("chat:1", item_type="chat")
    chat.add_description(ImageDescription("What colour is it?", "m", "user_question"))
    chat.add_description(ImageDescription("Red." + USAGE, "m", "ai_response"))
    messages = ChatWindow._build_messages_from_descriptions(None, chat)
    assert [m["content"] for m in messages] == ["What colour is it?", "Red."]


# ------------------------------------------------------------------ #
# Workspace statistics                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("suffix", [USAGE, OLDER_USAGE,
                                    "\n\n[Token Usage: 10 total (5 prompt + 5 completion)]"])
def test_stats_word_counts_leave_out_every_form(suffix):
    from workspace_stats_dialog import _strip_metadata_affixes
    assert _strip_metadata_affixes(BODY + suffix) == "A red barn under a grey sky."
