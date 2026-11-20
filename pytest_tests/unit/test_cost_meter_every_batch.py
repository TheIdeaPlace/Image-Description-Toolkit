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
        before = "\n".join(lines[max(0, i - 25):i])
        assert "self._start_batch_meters()" in before, (
            f"line {i + 1} opens a batch window without resetting the cost meter")


def test_the_meter_is_reset_in_one_place_only():
    """Two copies of the reset drifted apart once; keep one."""
    assert _SOURCE.count("self._cost_meter = CostMeter()") == 2   # __init__ and the helper
    assert _SOURCE.count("def _start_batch_meters(self)") == 1


wx = pytest.importorskip("wx", reason="wxPython not installed in this environment")

import workers_wx  # noqa: E402
import imagedescriber_wx  # noqa: E402


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


def test_no_cost_in_the_log_for_a_provider_with_no_charge(monkeypatch, tmp_path):
    log = _run(monkeypatch, tmp_path, "ollama", "moondream", {"a.jpg": (900, 120)})
    assert "described  (900 in, 120 out)" in log
    assert "  cost " not in log and "cost=" not in log and "so far" not in log
