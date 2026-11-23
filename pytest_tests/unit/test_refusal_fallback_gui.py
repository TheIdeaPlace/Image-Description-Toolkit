"""ImageDescriber's worker falls back to another prompt style when Apple
Intelligence refuses one image, and records the style that described it.

The core helper is tested in test_run_durability.py; this covers the GUI
worker's wiring: the event's prompt style, the metadata note, the location
context, and that a custom prompt is left alone.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

wx = pytest.importorskip("wx", reason="wxPython not installed in this environment")

import workers_wx  # noqa: E402
from idt_core.pipeline import META_PREFIX  # noqa: E402
from idt_core.providers.apple import AppleFMError, GUARDRAIL_HINT  # noqa: E402

pytestmark = pytest.mark.unit


def _worker(monkeypatch, refuse, custom_prompt="", context=""):
    posted, prompts = [], []
    monkeypatch.setattr(workers_wx.wx, "PostEvent", lambda win, evt: posted.append(evt))
    w = workers_wx.ProcessingWorker(None, "C:/p/a.jpg", "apple", "system",
                                    "narrative", custom_prompt, None)
    monkeypatch.setattr(w, "_extract_metadata", lambda p: {})
    prefix = f"{META_PREFIX}{context}\n\n" if context else ""
    monkeypatch.setattr(w, "_inject_exif_context",
                        lambda p: (prefix + p, context), raising=False)

    def describe(path, prompt, api_key=None):
        prompts.append(prompt)
        if any(word in prompt.lower() for word in refuse):
            try:
                raise AppleFMError(GUARDRAIL_HINT, per_image=True, prompt_may_help=True)
            except AppleFMError as e:
                raise Exception(f"AI processing failed: {e}") from e
        return "A deck gun.", object()
    monkeypatch.setattr(w, "_process_with_ai", describe)
    return w, posted, prompts


def _completed(posted):
    return [e for e in posted if isinstance(e, workers_wx.ProcessingCompleteEventData)]


def test_refused_image_is_described_with_the_technical_prompt(monkeypatch):
    w, posted, prompts = _worker(monkeypatch, refuse=("narrative",))
    w.run()
    assert w.result_ok
    assert w.result_fallback_style == "technical"
    done = _completed(posted)
    assert done and done[0].prompt_style == "technical"
    assert done[0].metadata["prompt_fallback_from"] == "narrative"
    assert len(prompts) == 2


def test_fallback_keeps_the_location_context(monkeypatch):
    w, posted, prompts = _worker(monkeypatch, refuse=("narrative",),
                                 context="Mobile, Alabama")
    w.run()
    assert w.result_ok
    assert all(p.startswith(META_PREFIX + "Mobile, Alabama") for p in prompts)


def test_no_refusal_changes_nothing(monkeypatch):
    w, posted, prompts = _worker(monkeypatch, refuse=())
    w.run()
    assert w.result_fallback_style is None
    assert _completed(posted)[0].prompt_style == "narrative"
    assert len(prompts) == 1


def test_custom_prompt_is_not_replaced(monkeypatch):
    w, posted, prompts = _worker(monkeypatch, refuse=("mine",),
                                 custom_prompt="Mine: describe it.")
    w.run()
    assert not w.result_ok
    assert w.result_per_image
    assert len(prompts) == 1


def test_every_style_refused_is_still_a_per_image_failure(monkeypatch):
    w, posted, prompts = _worker(monkeypatch, refuse=("",))   # refuses every prompt
    w.run()
    assert not w.result_ok
    assert w.result_per_image            # counts toward the refusal streak, not a halt
    assert len(prompts) == 3
