"""Issue #446: ImageDescriber's token counts reach the workspace and `idt stats`.

ImageDescriber kept a described picture's token counts only in the
description's ``metadata`` dict. The bridge that saves to the .idtw bundle
read only ``token_usage``, which only chat turns set, so ``input_tokens`` was
saved as null (or 0, after a reload synthesized a token_usage of zeros) and
`idt stats` left out the input cost: more than half the bill for Fable 5.2 on
the picture where it was found.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from idt_core.gui_bridge import BundleCheckpointWriter, _gui_desc_to_ws  # noqa: E402
from idt_core.workspace import Workspace, WorkspaceDescription, first_token_count  # noqa: E402

pytestmark = pytest.mark.unit


def _described(metadata, **extra):
    """A description as ImageDescriber's ImageDescription.to_dict writes it."""
    return {"id": "1794938128802", "text": "A salmon leaps.", "model": "claude-fable-5-2",
            "prompt_style": "narrative", "created": "2026-11-17T11:55:28",
            "custom_prompt": "", "provider": "claude", "detection_data": [],
            "metadata": metadata, **extra}


def test_counts_in_metadata_reach_the_workspace_description():
    ws = _gui_desc_to_ws(_described({"input_tokens": 3925, "output_tokens": 593,
                                     "total_tokens": 4518}, completion_tokens=593))
    assert ws.input_tokens == 3925
    assert ws.output_tokens == 593


def test_a_zero_left_by_an_earlier_reload_does_not_hide_the_real_count():
    """After one save and reload the GUI carried token_usage {prompt_tokens: 0}."""
    ws = _gui_desc_to_ws(_described(
        {"input_tokens": 1535, "output_tokens": 274},
        token_usage={"prompt_tokens": 0, "completion_tokens": 274, "total_tokens": 274}))
    assert ws.input_tokens == 1535
    assert ws.output_tokens == 274


def test_chat_turns_keep_using_token_usage():
    ws = _gui_desc_to_ws(_described({}, token_usage={"input_tokens": 120, "output_tokens": 40}))
    assert (ws.input_tokens, ws.output_tokens) == (120, 40)


def test_no_counts_anywhere_stays_unknown():
    ws = _gui_desc_to_ws(_described({}))
    assert ws.input_tokens is None
    assert ws.output_tokens is None


def test_descriptions_already_saved_are_read_correctly():
    """The exact shape in the iPhone.idtw sidecar where #446 was found."""
    saved = {"id": "1794877270038", "text": "Salmon.", "provider": "claude",
             "model": "claude-haiku-4-5-20251001", "prompt_name": "accessibility",
             "input_tokens": 0, "output_tokens": 274,
             "extra": {"metadata": {"input_tokens": 1535, "output_tokens": 274},
                       "token_usage": {"prompt_tokens": 0, "completion_tokens": 274}}}
    d = WorkspaceDescription.from_dict(saved)
    assert d.input_tokens == 1535
    assert d.output_tokens == 274

    saved_null = dict(saved, input_tokens=None, extra={"metadata": {"input_tokens": 3925}})
    assert WorkspaceDescription.from_dict(saved_null).input_tokens == 3925


def test_a_recorded_count_wins_over_metadata():
    d = WorkspaceDescription.from_dict({"id": "x", "text": "t", "input_tokens": 900,
                                        "extra": {"metadata": {"input_tokens": 5}}})
    assert d.input_tokens == 900


@pytest.mark.parametrize("candidates, expected", [
    ((None, 0, "12"), 12),
    ((0, None), None),
    (("abc", 7), 7),
    ((-3, 4), 4),
])
def test_first_token_count(candidates, expected):
    assert first_token_count(*candidates) == expected


def test_idt_stats_prices_a_picture_imagedescriber_described(tmp_path, capsys):
    """End to end: the checkpoint writer saves as during a batch, then `idt stats`."""
    from cli import main as cli_main

    src = tmp_path / "photos"
    src.mkdir()
    (src / "salmon.png").write_bytes(b"x")
    ws = Workspace.create(tmp_path / "run.idtw")
    ws.add_source_folder(src)

    gui_item = {"file_path": str(src / "salmon.png"), "item_type": "image",
                "subfolder": None, "processing_state": "completed",
                "descriptions": [_described({"input_tokens": 3925, "output_tokens": 593,
                                             "total_tokens": 4518}, completion_tokens=593)]}
    writer = BundleCheckpointWriter()
    writer.enqueue_item(ws.path, str(src / "salmon.png"), gui_item, {"total_queued": 1},
                        writer.snapshot_seq())
    assert writer.flush(5)

    saved = Workspace(ws.path).get_item("salmon.png", None).descriptions[0]
    assert saved.input_tokens == 3925

    cli_main.cmd_stats(SimpleNamespace(source=str(ws.path), all=False, json_out=True))
    row = json.loads(capsys.readouterr().out)["token_breakdown"][0]
    assert row["input_tokens"] == 3925
    rate_in, rate_out = cli_main.STATS_COST_TABLE["claude-fable-5-2"]
    expected = 3925 / 1e6 * rate_in + 593 / 1e6 * rate_out
    assert row["estimated_cost_usd"] == pytest.approx(expected, abs=0.0001)
    assert row["estimated_cost_usd"] > 593 / 1e6 * rate_out   # the input is in it


def test_a_stale_zero_is_repaired_when_a_description_is_loaded():
    """A workspace saved before the fix carries token_usage {prompt_tokens: 0}.
    Loading it must hand the GUI the real count, so nothing sees the 0 again."""
    from idt_core.gui_bridge import _ws_desc_to_gui

    saved = WorkspaceDescription.from_dict(
        {"id": "x", "text": "Salmon.", "input_tokens": 0, "output_tokens": 274,
         "extra": {"metadata": {"input_tokens": 1535, "output_tokens": 274},
                   "token_usage": {"prompt_tokens": 0, "completion_tokens": 274,
                                   "total_tokens": 274}}})
    tu = _ws_desc_to_gui(saved)["token_usage"]
    assert tu == {"prompt_tokens": 1535, "completion_tokens": 274, "total_tokens": 1809}


def test_counts_survive_save_reload_save_through_the_real_gui_model(tmp_path):
    """A description built as ImageDescriber builds one after describing a
    picture (counts in metadata only), saved, loaded into the GUI's own
    workspace class, and saved again."""
    sys.path.insert(0, str(_ROOT / "imagedescriber"))
    from PIL import Image
    from data_models import ImageDescription, ImageItem, ImageWorkspace

    from idt_core.gui_bridge import bundle_to_gui_workspace_dict, gui_workspace_to_bundle

    src = tmp_path / "Photos"
    src.mkdir()
    Image.new("RGB", (8, 8)).save(src / "salmon.jpg", "JPEG")
    gui = ImageWorkspace(new_workspace=True)
    gui.add_directory(str(src))
    item = ImageItem(str(src / "salmon.jpg"))
    item.add_description(ImageDescription(
        text="A salmon leaps.", model="claude-fable-5-2", prompt_style="narrative",
        provider="claude", completion_tokens=593,
        metadata={"input_tokens": 3925, "output_tokens": 593, "total_tokens": 4518}))
    gui.add_item(item)

    first = gui_workspace_to_bundle(gui.to_dict(), tmp_path / "One")
    assert next(i for i in first.items() if i.described).active_description.input_tokens == 3925

    reloaded = ImageWorkspace.from_dict(bundle_to_gui_workspace_dict(first))
    second = gui_workspace_to_bundle(reloaded.to_dict(), tmp_path / "Two")
    d = next(i for i in second.items() if i.described).active_description
    assert (d.input_tokens, d.output_tokens) == (3925, 593)
