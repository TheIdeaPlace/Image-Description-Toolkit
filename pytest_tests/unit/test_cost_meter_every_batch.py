"""The batch window's cost meter starts fresh for every batch, and the run log
records the same meter so the window can be checked against it.

Seen in a resumed 6,657-picture Claude Haiku 5.5 run: the window's average
opened at 11 to 12 hundredths of a cent and took many pictures to settle,
while the pictures it was describing cost about 0.035 cents each. Resuming a
batch opened a new batch window without resetting the meter, so it carried
the previous batch's cost and picture count. A download, auto-processing
downloaded images and auto-processing extracted frames had the same gap.
"""
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SOURCE = (_ROOT / "imagedescriber" / "imagedescriber_wx.py").read_text(encoding="utf-8")


def test_every_new_batch_window_starts_the_meter_afresh():
    """Wherever a batch window is made, the meter is reset just before it."""
    lines = _SOURCE.splitlines()
    sites = [i for i, line in enumerate(lines)
             if re.search(r"self\.batch_progress_dialog = BatchProgressDialog\(", line)]
    assert len(sites) >= 5, sites
    for i in sites:
        # Close above, in the same function: not merely somewhere earlier.
        window = lines[max(0, i - 15):i]
        start = max((k for k, line in enumerate(window) if line.lstrip().startswith("def ")),
                    default=-1)
        before = "\n".join(window[start + 1:])
        assert "self._start_batch_meters(" in before, (
            f"line {i + 1} opens a batch window without resetting the cost meter")


def test_the_meter_is_reset_in_one_place_only():
    """Two copies of the reset drifted apart once; keep one."""
    assert _SOURCE.count("self._cost_meter = CostMeter()") == 2   # __init__ and the helper
    assert _SOURCE.count("def _start_batch_meters(self") == 1


def test_batches_that_skip_the_options_dialog_still_name_their_provider():
    """Resume, downloaded images and extracted frames pass their own provider,
    model and prompt; without them the window named the previous batch's."""
    calls = re.findall(r"self\._start_batch_meters\(([^)]*)", _SOURCE)
    with_options = [c for c in calls if c.strip()]
    # _ensure_progress_dialog, downloaded images, frames: (options); resume: ({...
    assert sum(c.strip() == "options" for c in with_options) >= 3, calls
    assert any(c.strip().startswith("{") for c in with_options), calls


# wx only for the tests below; the source checks above run without it.
try:
    import workers_wx          # imports wx itself
    import imagedescriber_wx
except ImportError:  # pragma: no cover - CI and the VM have wx
    workers_wx = imagedescriber_wx = None

needs_wx = pytest.mark.skipif(workers_wx is None, reason="wxPython not installed")


@needs_wx
def test_counts_toward_batch():
    from types import SimpleNamespace

    running, stopped, other = object(), object(), object()
    counts = imagedescriber_wx.ImageDescriberFrame._counts_toward_batch
    frame = SimpleNamespace(batch_worker=running, _stopping_worker=stopped)
    assert counts(frame, running)
    assert not counts(frame, None)            # P, a follow-up, an auto-rename
    assert not counts(frame, other)
    assert not counts(frame, stopped)         # a newer batch is running
    frame.batch_worker = None
    assert counts(frame, stopped)             # the stopped batch's last picture


@needs_wx
def test_start_batch_meters_names_the_batch():
    from types import SimpleNamespace
    from idt_core.pricing import CostMeter

    frame = SimpleNamespace(_token_records=[], _cost_meter=CostMeter(),
                            _batch_provider="ollama", _batch_model="moondream",
                            _batch_prompt="simple")
    imagedescriber_wx.ImageDescriberFrame._start_batch_meters(
        frame, {"provider": "claude", "model": "claude-haiku-5-5",
                "prompt_style": "narrative"})
    assert (frame._batch_provider, frame._batch_model, frame._batch_prompt) == \
        ("claude", "claude-haiku-5-5", "narrative")


@needs_wx
def test_start_batch_meters_drops_the_last_batch():
    from types import SimpleNamespace
    from idt_core.pricing import CostMeter

    frame = SimpleNamespace(_token_records=[{"input": 1, "output": 1, "total": 2,
                                             "name": "old.jpg"}],
                            _cost_meter=CostMeter())
    frame._cost_meter.add("claude", "claude-haiku-5-5", 2023, 1913)
    imagedescriber_wx.ImageDescriberFrame._start_batch_meters(frame)
    assert frame._token_records == []
    assert frame._cost_meter.reading() == {"cost": None, "avg": None, "note": ""}


class _FakeImageWorker:
    tokens = {}

    def __init__(self, parent, file_path, *a, **k):
        self.file_path = file_path
        self.result_input_tokens, self.result_output_tokens = \
            self.tokens.get(Path(file_path).name, (0, 0))
        self.result_ok = True
        self.result_error = None
        self.result_kind = None
        self.result_signature = None
        self.result_per_image = False
        self.result_thinking_chars = 0
        self.result_truncated = False

    def start(self):
        pass

    def join(self):
        pass


def _run(monkeypatch, tmp_path, provider, model, tokens):
    monkeypatch.setattr(workers_wx, "ProcessingWorker", _FakeImageWorker)
    monkeypatch.setattr(workers_wx.wx, "PostEvent", lambda win, evt: None)
    _FakeImageWorker.tokens = tokens
    worker = workers_wx.BatchProcessingWorker(
        None, [f"C:/p/{n}" for n in tokens], provider, model, "narrative",
        "", None, False, logs_dir=tmp_path)
    worker.run()
    return "".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.log"))


@needs_wx
def test_the_run_log_records_the_cost_meter(monkeypatch, tmp_path):
    """Haiku 5.5 at $0.10 / $0.50 per million: 2,023 in and 255 out is
    0.033 cents; 2,023 in and 1,913 out is 0.12 cents."""
    log = _run(monkeypatch, tmp_path, "claude", "claude-haiku-5-5",
               {"a.jpg": (2023, 255), "b.jpg": (2023, 1913)})
    assert ("1/2  a.jpg: described  (2023 in, 255 out)  cost 0.033 cents;"
            " so far 0.033 cents, average 0.033 cents over 1") in log
    assert ("2/2  b.jpg: described  (2023 in, 1913 out)  cost 0.12 cents;"
            " so far 0.15 cents, average 0.074 cents over 2") in log
    assert "cost=0.15 cents  average=0.074 cents" in log


@needs_wx
def test_no_cost_in_the_log_for_a_provider_with_no_charge(monkeypatch, tmp_path):
    log = _run(monkeypatch, tmp_path, "ollama", "moondream", {"a.jpg": (900, 120)})
    assert "described  (900 in, 120 out)" in log
    assert "  cost " not in log and "cost=" not in log and "so far" not in log


# --------------------------------------------------------------------------- #
# The pictures that stand out: largest token use and most expensive            #
# --------------------------------------------------------------------------- #

@needs_wx
def test_standout_rows_give_names_costs_and_descriptions():
    from batch_progress_dialog import standout_rows

    rows = standout_rows({
        "peak_total": 3936, "peak_name": "screen.jpg",
        "peak_description": "A settings screen with a long list.\n\n"
                            "[Token Usage: 3,936 total (2,023 prompt + 1,913 completion)]",
        "priciest_name": "screen.jpg", "priciest_cost": 0.0011588,
        "priciest_description": "A settings screen with a long list.",
    })
    assert rows == [
        "  Largest Token Use:        3,936 (screen.jpg)",
        "  Largest Token Use Description: A settings screen with a long list.",
        "  Most Expensive Picture:   0.12 cents (screen.jpg)",
        "  Most Expensive Description: A settings screen with a long list.",
    ]


@needs_wx
def test_no_most_expensive_row_without_prices():
    from batch_progress_dialog import standout_rows

    rows = standout_rows({"peak_total": 1020, "peak_name": "a.jpg",
                          "peak_description": "A dog.", "priciest_name": None,
                          "priciest_cost": None, "priciest_description": ""})
    assert rows == ["  Largest Token Use:        1,020 (a.jpg)",
                    "  Largest Token Use Description: A dog."]


@needs_wx
def test_token_stats_pick_the_standouts():
    """The most tokens isn't always the most money: input is cheaper than
    output, so a long prompt with a short answer uses more tokens for less."""
    from types import SimpleNamespace
    from idt_core.pricing import CostMeter

    frame = SimpleNamespace(_cost_meter=CostMeter(), _token_records=[
        {"input": 9000, "output": 100, "total": 9100, "name": "big-in.jpg",
         "description": "Many tokens in.", "cost": 0.00095},
        {"input": 2023, "output": 1913, "total": 3936, "name": "long-out.jpg",
         "description": "A long answer.", "cost": 0.0011588},
        {"input": 500, "output": 50, "total": 550, "name": "free.jpg",
         "description": "Unpriced.", "cost": None},
    ])
    stats = imagedescriber_wx.ImageDescriberFrame._compute_token_stats(frame)
    assert (stats["peak_name"], stats["peak_description"]) == ("big-in.jpg", "Many tokens in.")
    assert (stats["priciest_name"], stats["priciest_cost"], stats["priciest_description"]) == \
        ("long-out.jpg", 0.0011588, "A long answer.")


def _meter_frame(batch_worker):
    from types import SimpleNamespace
    from idt_core.pricing import CostMeter

    frame = SimpleNamespace(_token_records=[], _cost_meter=CostMeter(),
                            batch_worker=batch_worker, _stopping_worker=None)
    cls = imagedescriber_wx.ImageDescriberFrame
    frame._counts_toward_batch = lambda b: cls._counts_toward_batch(frame, b)
    return frame, lambda event, md: cls._meter_picture(frame, event, md)


def _event(batch, provider="claude", model="claude-haiku-5-5", name="a.jpg"):
    from types import SimpleNamespace
    return SimpleNamespace(batch=batch, provider=provider, model=model,
                           file_path=f"C:/p/{name}", description=f"About {name}.")


@needs_wx
def test_meter_picture_counts_the_batchs_own_and_prices_each():
    batch = object()
    frame, meter = _meter_frame(batch)
    meter(_event(batch), {"input_tokens": 2023, "output_tokens": 1913, "total_tokens": 3936})
    meter(_event(None, name="p.jpg"), {"input_tokens": 2023, "output_tokens": 1913,
                                       "total_tokens": 3936})       # P during the batch
    meter(_event(batch, provider="ollama", model="moondream", name="o.jpg"),
          {"input_tokens": 900, "output_tokens": 120, "total_tokens": 1020})
    meter(_event(batch, name="none.jpg"), {"total_tokens": 0})       # no usage reported

    names = [r["name"] for r in frame._token_records]
    assert names == ["a.jpg", "o.jpg"]
    assert frame._token_records[0]["cost"] == pytest.approx(0.0011588)
    assert frame._token_records[0]["description"] == "About a.jpg."
    assert frame._token_records[1]["cost"] is None                   # unpriced
    assert frame._cost_meter.priced == 1


@needs_wx
def test_list_rows_keep_a_description_on_one_line():
    from batch_progress_dialog import one_line, standout_rows

    text = ("Madison, Wisconsin - A lake at dusk.\n\nThe far shore is lit.\n\n"
            "[Token Usage: 3,936 total (2,023 prompt + 1,913 completion)]")
    assert one_line(text) == "Madison, Wisconsin - A lake at dusk. The far shore is lit."
    rows = standout_rows({"peak_total": 3936, "peak_name": "a.jpg", "peak_description": text,
                          "priciest_name": None, "priciest_cost": None})
    assert all("\n" not in r for r in rows)
