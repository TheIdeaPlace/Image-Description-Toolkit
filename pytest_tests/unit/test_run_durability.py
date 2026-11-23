"""
A long run in a cloud-synced folder: the manifest must never be silently
recreated, the run log must survive its file being replaced, and an image the
provider refuses on its guardrails falls back to another prompt style.

From an 11,559-image Apple Intelligence run kept in OneDrive: the manifest was
rebuilt with default settings at the end, the run log stopped at hour 3 of 29,
and 9 images were refused that the technical or artistic prompt described.
"""
import json
import os
import threading
import time
from pathlib import Path

import pytest

import idt_core.workspace as workspace_mod
from idt_core.logger import close_run_log, open_run_log
from idt_core.pipeline import (
    REFUSAL_FALLBACK_STYLES, RunOptions, WorkspacePipeline,
    describe_with_refusal_fallback, metadata_preamble,
)
from idt_core.providers.apple import AppleFMError, GUARDRAIL_HINT
from idt_core.providers.base import DescriptionResult
from idt_core.workspace import Workspace, WorkspaceManifestError

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# Workspace.open never replaces a missing manifest                             #
# --------------------------------------------------------------------------- #

def _bundle_with_content(tmp_path) -> Workspace:
    ws = Workspace.create(tmp_path / "Run")
    ws.defaults.provider, ws.defaults.model = "apple", "system"
    ws.save_manifest()
    (ws.descriptions_dir / "a.jpg.json").write_text("{}", encoding="utf-8")
    return ws


def test_open_raises_rather_than_recreating_a_bundle_with_content(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_mod, "MANIFEST_WAIT_SECONDS", 0.3)
    ws = _bundle_with_content(tmp_path)
    ws.manifest_path.unlink()

    with pytest.raises(WorkspaceManifestError):
        Workspace.open(ws.path)
    assert not ws.manifest_path.exists()       # nothing written over it


def test_open_waits_for_a_manifest_that_comes_back(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_mod, "MANIFEST_WAIT_SECONDS", 5.0)
    ws = _bundle_with_content(tmp_path)
    saved = ws.manifest_path.read_text(encoding="utf-8")
    ws.manifest_path.unlink()

    def restore():
        time.sleep(0.5)
        ws.manifest_path.write_text(saved, encoding="utf-8")
    t = threading.Thread(target=restore)
    t.start()
    reopened = Workspace.open(ws.path)
    t.join()

    assert reopened.defaults.provider == "apple"
    assert reopened.created == ws.created


def test_open_waits_out_a_half_written_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace_mod, "MANIFEST_WAIT_SECONDS", 5.0)
    ws = _bundle_with_content(tmp_path)
    saved = ws.manifest_path.read_text(encoding="utf-8")
    ws.manifest_path.write_text(saved[:20], encoding="utf-8")

    def restore():
        time.sleep(0.5)
        ws.manifest_path.write_text(saved, encoding="utf-8")
    t = threading.Thread(target=restore)
    t.start()
    reopened = Workspace.open(ws.path)
    t.join()
    assert reopened.defaults.model == "system"


def test_open_still_creates_a_new_bundle(tmp_path):
    ws = Workspace.open(tmp_path / "Fresh")
    assert Workspace.is_bundle(ws.path)

    empty = tmp_path / "Empty.idtw"
    (empty / "descriptions").mkdir(parents=True)
    assert Workspace.is_bundle(Workspace.open(empty).path)


# --------------------------------------------------------------------------- #
# Run log survives its file being replaced                                     #
# --------------------------------------------------------------------------- #

def test_run_log_keeps_writing_after_its_file_is_replaced(tmp_path):
    log = open_run_log(tmp_path)
    log.info("before")
    path = next(tmp_path.glob("run_*.log"))

    # What a sync client does: swap in another copy of the file by rename.
    copy = tmp_path / "copy"
    copy.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    os.replace(copy, path)

    log.info("after")
    close_run_log(log)
    text = path.read_text(encoding="utf-8")
    assert "before" in text and "after" in text


# --------------------------------------------------------------------------- #
# Refusal fallback                                                             #
# --------------------------------------------------------------------------- #

def _refusal():
    return AppleFMError(GUARDRAIL_HINT, per_image=True, prompt_may_help=True)


class Scripted:
    """describe(prompt): refuses while the prompt contains any refused word."""
    def __init__(self, refuse=(), error=None):
        self.refuse, self.error, self.prompts = refuse, error, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        if any(word in prompt for word in self.refuse):
            raise _refusal()
        return f"described with: {prompt}"


PROMPTS = {"narrative": "NARRATIVE", "technical": "TECHNICAL", "artistic": "ARTISTIC"}


def test_refusal_falls_back_to_the_next_style():
    d = Scripted(refuse=("NARRATIVE",))
    result, name, text = describe_with_refusal_fallback(
        d, "narrative", "NARRATIVE", "", PROMPTS.get)
    assert (name, text) == ("technical", "TECHNICAL")
    assert result == "described with: TECHNICAL"


def test_fallback_keeps_the_location_context():
    d = Scripted(refuse=("NARRATIVE",))
    preamble = metadata_preamble("Mobile, Alabama")
    describe_with_refusal_fallback(d, "narrative", "NARRATIVE", preamble, PROMPTS.get)
    assert d.prompts == [preamble + "NARRATIVE", preamble + "TECHNICAL"]


def test_fallback_goes_on_to_artistic():
    d = Scripted(refuse=("NARRATIVE", "TECHNICAL"))
    _, name, _ = describe_with_refusal_fallback(
        d, "narrative", "NARRATIVE", "", PROMPTS.get)
    assert name == "artistic"


def test_every_style_refused_raises_the_original_refusal():
    d = Scripted(refuse=("NARRATIVE", "TECHNICAL", "ARTISTIC"))
    with pytest.raises(AppleFMError) as info:
        describe_with_refusal_fallback(d, "narrative", "NARRATIVE", "", PROMPTS.get)
    assert info.value.per_image
    assert len(d.prompts) == 1 + len(REFUSAL_FALLBACK_STYLES)


def test_the_refused_style_is_not_tried_twice():
    d = Scripted(refuse=("TECHNICAL",))
    _, name, _ = describe_with_refusal_fallback(
        d, "technical", "TECHNICAL", "", PROMPTS.get)
    assert name == "artistic"
    assert d.prompts == ["TECHNICAL", "ARTISTIC"]


def test_custom_prompt_never_falls_back():
    d = Scripted(refuse=("MINE",))
    with pytest.raises(AppleFMError):
        describe_with_refusal_fallback(d, "custom", "MINE", "", PROMPTS.get)
    assert d.prompts == ["MINE"]


def test_other_failures_are_not_retried():
    d = Scripted(error=AppleFMError("Apple Intelligence timed out"))
    with pytest.raises(AppleFMError):
        describe_with_refusal_fallback(d, "narrative", "NARRATIVE", "", PROMPTS.get)
    assert len(d.prompts) == 1


def test_a_refusal_a_prompt_cannot_change_is_not_retried():
    """Windows AI takes no prompt; its refusals carry per_image only."""
    def describe(prompt):
        raise AppleFMError("declined", per_image=True)
    with pytest.raises(AppleFMError):
        describe_with_refusal_fallback(describe, "narrative", "NARRATIVE", "", PROMPTS.get)


def test_wrapped_refusal_is_recognized():
    """The GUI wraps provider errors ("AI processing failed: ...")."""
    def describe(prompt):
        if "NARRATIVE" in prompt:
            try:
                raise _refusal()
            except AppleFMError as exc:
                raise RuntimeError(f"AI processing failed: {exc}") from exc
        return "ok"
    _, name, _ = describe_with_refusal_fallback(
        describe, "narrative", "NARRATIVE", "", PROMPTS.get)
    assert name == "technical"


def test_workspace_pipeline_records_the_style_that_described(tmp_path):
    from PIL import Image
    src = tmp_path / "Pics"
    src.mkdir()
    Image.new("RGB", (16, 16), (10, 20, 30)).save(src / "a.jpg", "JPEG")
    ws = Workspace.create(tmp_path / "WS")
    ws.add_source_folder(src, recursive=True)

    class Provider:
        provider_name, model_name = "apple", "system"

        def describe(self, image_bytes, mime_type, prompt):
            if "narrative" in prompt.lower():
                raise _refusal()
            return DescriptionResult(text="A gun turret.", provider="apple",
                                     model="system")

    events = list(WorkspacePipeline(ws, Provider()).run(RunOptions(
        prompt_name="narrative",
        prompt_text="Describe this image in a narrative style.")))
    assert events[0].success
    desc = ws.items()[0].active_description
    assert desc.prompt_name == "technical"
    assert desc.text == "A gun turret."
    log = next(ws.logs_dir.glob("run_*.log")).read_text(encoding="utf-8")
    assert "[narrative refused; used technical]" in log
