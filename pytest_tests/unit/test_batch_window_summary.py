"""The batch progress window, as the 4.9.0 bug bashes heard it.

- #475: the summary left out the batch's last picture ("Last Image
  Described", the token total and the cost).
- #427: lines of "─" were list items, read aloud as such.
- #412: the title said only the stage, so Insert+T couldn't say how far the
  batch had got.

These open real wx windows: CI and the test VM run them, not a developer's PC.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if os.environ.get("IDT_REQUIRE_WX") == "1":
    import wx
else:
    wx = pytest.importorskip("wx", reason="wxPython not installed")

pytestmark = pytest.mark.unit


def _stats(n, total_each=100):
    return {"avg_input": 60, "avg_output": 40, "avg_total": total_each,
            "total": n * total_each, "peak_total": total_each, "peak_name": "a.jpg",
            "cost": None, "avg_cost": None, "cost_note": None}


@pytest.fixture
def owner():
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None, title="ImageDescriber")
    frame.image_list = wx.ListBox(frame)
    yield frame
    frame.Destroy()
    wx.SafeYield()
    del app


@pytest.fixture
def dialog(owner):
    from batch_progress_dialog import BatchProgressDialog
    dlg = BatchProgressDialog(owner, 3, batch_provider="ollama", batch_model="llava",
                              batch_prompt="detailed")
    yield dlg
    if dlg:
        dlg.Destroy()


def _rows(dlg):
    return [dlg.stats_list.GetString(i) for i in range(dlg.stats_list.GetCount())]


def _value(rows, label):
    return next(r.split(":", 1)[1].strip() for r in rows if r.startswith(label))


# ----- #475 ----- #

def test_the_summary_includes_the_last_picture(dialog):
    dialog.begin_stage("Describing", 3, stage_index=1, stage_count=1, can_interrupt=True)
    dialog.update_progress(3, 3, file_path="c.jpg", last_image="b.jpg",
                           last_description="A cat.", token_stats=_stats(2))
    # c.jpg is described; the batch ends with no further progress update.
    dialog.note_completed("c.jpg", "A dog.", _stats(3))
    dialog.mark_complete("3 images described")
    rows = _rows(dialog)
    assert _value(rows, "Last Image Described") == "c.jpg"
    assert _value(rows, "Last Description") == "A dog."
    assert _value(rows, "  Total Tokens") == "300"


def test_a_completion_before_any_progress_is_ignored(dialog):
    dialog.note_completed("a.jpg", "A dog.", _stats(1))   # nothing to update yet
    assert dialog._last_progress is None


# ----- #427 ----- #

def test_no_row_is_a_line_of_box_drawing(dialog):
    dialog.begin_stage("Describing", 3, stage_index=1, stage_count=1, can_interrupt=True)
    dialog.update_progress(2, 3, file_path="b.jpg", avg_time=2.0, last_image="a.jpg",
                           last_description="A cat.", token_stats=_stats(1),
                           status_message="Loading model")
    dialog.note_failure("x.jpg", "bad")
    dialog.mark_stopping()
    dialog.mark_complete("2 images described")
    rows = _rows(dialog)
    assert rows
    assert not [r for r in rows if "─" in r], rows
    assert "Token Usage" in rows


def test_workspace_statistics_has_headings_not_rules():
    from data_models import ImageDescription, ImageItem, ImageWorkspace
    from workspace_stats_dialog import compute_workspace_stats

    ws = ImageWorkspace(new_workspace=True)
    item = ImageItem("C:/photos/a.jpg")
    item.descriptions.append(ImageDescription(text="A dog on a beach.", model="llava",
                                              provider="ollama", prompt_style="detailed"))
    ws.add_item(item)
    lines = compute_workspace_stats(ws)
    assert lines[0] == "Workspace Overview"
    assert "Descriptions" in lines
    assert not [line for line in lines if "─" in line], lines


# ----- #412 ----- #

def test_the_title_counts_images_described(dialog):
    dialog.begin_stage("Describing", 20, stage_index=2, stage_count=2, can_interrupt=True)
    dialog.update_progress(10, 20, file_path="j.jpg")       # 9 done, the 10th going
    assert dialog.GetTitle() == ("45%, 9 of 20 images described — "
                                 "Describing (step 2 of 2) — Batch Processing")


def test_a_failure_is_not_counted_as_described(dialog):
    dialog.begin_stage("Describing", 4, can_interrupt=True)
    dialog.note_failure("b.jpg", "bad")
    dialog.update_progress(3, 4, file_path="c.jpg")
    # The percentage is of the same count the title says.
    assert dialog.GetTitle().startswith("25%, 1 of 4 images described — ")


def test_a_failed_video_is_not_taken_off_images_described(dialog):
    """A video whose frames couldn't be extracted never took a place in the
    describe count, so it counts in Failed but not against the title."""
    dialog.begin_stage("Describing", 4, can_interrupt=True)
    dialog.note_failure("clip.mp4", "no frames", video=True)
    dialog.update_progress(3, 4, file_path="c.jpg")
    assert dialog.GetTitle().startswith("50%, 2 of 4 images described — ")
    assert any(r.startswith("Failed:") and r.endswith("1") for r in _rows(dialog))


def test_starting_to_describe_while_extracting_shows_no_percentage(dialog):
    """begin_stage runs before begin_extraction; the title must not flash a
    percentage in between (#412 review)."""
    titles = []
    real = dialog.SetTitle
    dialog.SetTitle = lambda t: (titles.append(t), real(t))
    dialog.begin_stage("Describing and extracting frames", 2, stage_index=2,
                       stage_count=2, can_interrupt=True)
    dialog.begin_extraction(3)
    assert titles and not [t for t in titles if "%" in t], titles
    assert len(titles) == 1, titles


def test_other_stages_keep_their_title(dialog):
    dialog.begin_stage("Extracting frames", 5, stage_index=1, stage_count=2,
                       can_interrupt=False)
    dialog.update_progress(2, 5)
    assert dialog.GetTitle() == "Extracting frames (step 1 of 2) — Batch Processing"


def test_while_videos_extract_there_is_no_percentage(dialog):
    dialog.begin_stage("Describing and extracting frames", 1, stage_index=2,
                       stage_count=2, can_interrupt=True)
    dialog.begin_extraction(3)
    dialog.update_progress(4, 6, file_path="d.jpg")
    title = dialog.GetTitle()
    assert title.startswith("3 images described so far — "), title
    assert "%" not in title


def test_a_batch_without_stages_counts_too(owner):
    """A resumed batch, video frames and downloaded images open the window
    with no stages."""
    from batch_progress_dialog import BatchProgressDialog
    dlg = BatchProgressDialog(owner, 4, describing=True)
    try:
        dlg.update_progress(3, 4, file_path="c.jpg")
        assert dlg.GetTitle() == "50%, 2 of 4 images described — Batch Processing Progress"
    finally:
        dlg.Destroy()


def test_a_download_says_nothing_about_descriptions(owner):
    from batch_progress_dialog import BatchProgressDialog
    dlg = BatchProgressDialog(owner, 10)
    try:
        dlg.update_progress(3, 10, image_name="page image 3")
        assert dlg.GetTitle() == "Batch Processing Progress"
    finally:
        dlg.Destroy()


def test_stopping_and_complete_titles_win(dialog):
    dialog.begin_stage("Describing", 4, can_interrupt=True)
    dialog.update_progress(2, 4, file_path="b.jpg")
    dialog.mark_stopping()
    assert dialog.GetTitle() == "Stopping: describing — Batch Processing"
    dialog.mark_complete("1 image described", stopped=True)
    assert dialog.GetTitle().startswith("Batch Stopped")
