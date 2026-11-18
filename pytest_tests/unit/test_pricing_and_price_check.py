"""The shared price table, the batch window's cost meter, and the weekly
check that compares the table with the providers' pricing pages.

Providers don't report prices, so the table is copied by hand and goes stale:
before 11/17/2026 it had no price for any Claude 5.x model and charged Opus
4.8 three times its real price.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for p in (str(_ROOT), str(_ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from idt_core import pricing  # noqa: E402
import check_model_prices as checker  # noqa: E402

pytestmark = pytest.mark.unit

ANTHROPIC_PAGE = """---
title: Pricing
---
## Model pricing

| Model | Base input tokens | 5m cache writes | 1h cache writes | Cache hits and refreshes | Output tokens |
| --- | --- | --- | --- | --- | --- |
| Claude Fable 5.2 | $8 / MTok | $10 / MTok | $16 / MTok | $0.20 / MTok | $40 / MTok |
| Claude Mythos 5.2 ([limited availability](https://example.com)) | $8 / MTok | $10 / MTok | $16 / MTok | $0.20 / MTok | $40 / MTok |
| Claude Opus 5.5 | $4 / MTok | $5 / MTok | $8 / MTok | $0.20 / MTok<sup>2</sup> | $20 / MTok |
| Claude Opus 4.1 ([retired, except on Bedrock](https://example.com)) | $15 / MTok | $18.75 / MTok | $30 / MTok | $1.50 / MTok | $75 / MTok |
| Claude Sonnet 5 | $2 / MTok<sup>3</sup> | $2.50 / MTok | $4 / MTok | $0.20 / MTok | $10 / MTok |
| Claude Haiku 5.5 (for prompts up to 100,000 tokens) | $0.10 / MTok | $0.125 / MTok | $0.20 / MTok | $0.01 / MTok | $0.50 / MTok |
| Claude Haiku 5.5 (for prompts over 100,000 tokens) | $0.50 / MTok | $0.625 / MTok | $1 / MTok | $0.05 / MTok | $2.50 / MTok |
| Claude Nova 6 | $3 / MTok | $3.75 / MTok | $6 / MTok | $0.30 / MTok | $15 / MTok |

## Cloud platform pricing

| Model | Input | Output |
| --- | --- | --- |
| Claude Opus 5.5 | $99 / MTok | $99 / MTok |
"""

OPENAI_PAGE = """# Pricing
### Standard pricing data
| Model | Short context input | Short context output | Short context cached input |
| --- | --- | --- | --- |
| gpt-6-luna | $0.10 | $0.50 | $0.01 |
| gpt-5.5 (<272K context length) | $5.00 | $30.00 | $0.50 |
| gpt-5.5-pro (<272K context length) | $30.00 | $180.00 | - |

| Model | Input | Output | Cached input |
| --- | --- | --- | --- |
| gpt-5.2 | $1.75 | $14.00 | $0.175 |
| gpt-5-mini | $0.25 | $2.00 | $0.025 |
### Batch pricing data
| Model | Input | Output |
| --- | --- | --- |
| gpt-5.2 | $0.88 | $7.00 |
"""


# --- The table -------------------------------------------------------------

def test_every_offered_claude_model_has_a_price():
    from idt_core.providers.claude import CLAUDE_MODELS
    for model in CLAUDE_MODELS:
        assert model in pricing.PRICES["claude"], model


def test_dated_snapshot_is_priced_as_its_model():
    assert pricing.rates_for("gpt-5-mini-2025-08-07") == pricing.rates_for("gpt-5-mini")


@pytest.mark.parametrize("provider, model, note", [
    ("ollama", "moondream", "no charge"),
    ("ollama", "kimi-k2.5:cloud", "Ollama plan"),
    ("claude-code", "haiku", "your plan"),
    ("claude", "claude-future-9", "no price"),
])
def test_estimate_says_why_there_is_no_price(provider, model, note):
    assert pricing.estimate(provider, model, 1000, 100) == (None, note)


def test_estimate_prices_tokens():
    cost, note = pricing.estimate("claude", "claude-haiku-5-5", 3925, 932)
    assert note == "" and cost == pytest.approx((3925 * 0.10 + 932 * 0.50) / 1e6)


@pytest.mark.parametrize("amount, text", [
    (0.36, "$0.36"), (12.5, "$12.50"), (1234.5, "$1,234.50"),
    (0, "$0.00"),
    # Under a cent, in cents: reads better aloud, never rounds to zero.
    (0.00096, "0.096 cents"), (0.000005, "0.0005 cents"), (0.004999, "0.5 cents"),
    (0.009996, "$0.01"),        # rounds to a cent: dollars, not "1 cents"
])
def test_format_dollars(amount, text):
    assert pricing.format_dollars(amount) == text


def test_cost_meter_prices_each_picture_once_and_canonicalizes(monkeypatch):
    calls = []
    real = pricing.estimate
    monkeypatch.setattr(pricing, "estimate", lambda *a: calls.append(a) or real(*a))
    meter = pricing.CostMeter()
    for _ in range(3):
        meter.add("anthropic", "claude-haiku-5-5", 3925, 932)   # CLI's name for Claude
    reading = meter.reading()
    reading2 = meter.reading()            # reading again prices nothing
    assert len(calls) == 3
    assert calls[0][0] == "claude"
    assert reading == reading2
    assert reading["cost"] == pytest.approx(3 * (3925 * 0.10 + 932 * 0.50) / 1e6)


def test_cost_meter_is_fast_for_a_big_batch():
    import time
    meter = pricing.CostMeter()
    for _ in range(7000):
        meter.add("claude", "claude-haiku-5-5", 3925, 932)
    start = time.perf_counter()
    for _ in range(100):
        meter.reading()
    assert time.perf_counter() - start < 0.05      # constant work per update


# --- The meter ---------------------------------------------------------------

def test_running_cost_adds_up_the_batch_so_far():
    recs = [{"provider": "claude", "model": "claude-haiku-5-5", "input": 3925, "output": 932}] * 38
    meter = pricing.running_cost(recs)
    one = (3925 * 0.10 + 932 * 0.50) / 1e6
    assert meter["cost"] == pytest.approx(38 * one)
    assert meter["avg"] == pytest.approx(one)
    assert meter["note"] == ""


def test_running_cost_for_a_free_model_says_why():
    meter = pricing.running_cost([{"provider": "ollama", "model": "moondream",
                                   "input": 500, "output": 50}])
    assert meter == {"cost": None, "avg": None, "note": "no charge"}


def test_cost_rows_read_like_a_taxi_meter(monkeypatch):
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    pytest.importorskip("wx")
    from batch_progress_dialog import cost_rows

    stats = {"cost": 0.0365, "avg_cost": 0.00096, "cost_note": ""}
    rows = cost_rows(stats, total=6083, current=38)
    # Projected: the 38 done, exactly, plus the average for the 6,045 to go.
    assert rows == ["  Estimated Cost So Far:    $0.04",
                    "  Average Cost per Image:   0.096 cents",
                    "  Projected Batch Cost:     about $5.84"]
    # No projection while videos are still extracting (the total is still growing).
    assert len(cost_rows(stats, total=6083, extracting=True)) == 2
    assert cost_rows({"cost": None, "cost_note": "no charge"}, total=10) == [
        "  Estimated Cost:           no charge (runs on your computer)"]
    assert cost_rows({"cost": None, "cost_note": ""}, total=10) == []


# --- The weekly check --------------------------------------------------------

def test_anthropic_page_is_read_from_the_model_pricing_table_only():
    page = checker.parse_anthropic(ANTHROPIC_PAGE)
    assert page["Claude Opus 5.5"] == (4.0, 20.0, False)        # not the cloud table's $99
    assert page["Claude Haiku 5.5"] == (0.10, 0.50, False)      # the up-to-100K row
    assert page["Claude Sonnet 5"] == (2.0, 10.0, False)        # footnote marker ignored
    assert page["Claude Mythos 5.2"][:2] == (8.0, 40.0)         # link text kept, link dropped
    assert page["Claude Opus 4.1"][2] is True                   # retired


def test_openai_page_is_read_from_the_standard_tables_only():
    page = checker.parse_openai(OPENAI_PAGE)
    assert page["gpt-5.2"] == (1.75, 14.0, False)               # not the batch $0.88
    assert page["gpt-5.5"] == (5.0, 30.0, False)                # context note stripped
    assert page["gpt-6-luna"] == (0.10, 0.50, False)


def test_compare_finds_changed_new_unpriced_and_gone(monkeypatch):
    monkeypatch.setattr(pricing, "PRICES", {"claude": {
        "claude-opus-5-5": pricing.Price("Claude Opus 5.5", 5.0, 25.0),     # page: 4 / 20
        "claude-haiku-5-5": pricing.Price("Claude Haiku 5.5", 0.10, 0.50),  # matches
        "claude-gone-1": pricing.Price("Claude Gone 1", 1.0, 5.0),          # not on page
    }})
    page = checker.parse_anthropic(ANTHROPIC_PAGE)
    found = checker.compare("claude", page, ["claude-opus-5-5", "claude-new-offered"])
    kinds = {}
    for kind, text in found:
        kinds.setdefault(kind, []).append(text)
    assert any("claude-opus-5-5" in t and "$4 / $20" in t for t in kinds["price"])
    assert any("Claude Nova 6" in t for t in kinds["new"])
    assert not any("Mythos" in t for t in kinds["new"])            # ignored on purpose
    assert not any("Opus 4.1" in t for t in kinds["new"])          # retired rows aren't new
    assert any("claude-gone-1" in t for t in kinds["gone"])
    assert any("claude-new-offered" in t for t in kinds["unpriced"])


def test_ignored_pro_models_are_not_reported(monkeypatch):
    monkeypatch.setattr(pricing, "PRICES", {"openai": {
        "gpt-5.2": pricing.Price("gpt-5.2", 1.75, 14.0)}})
    found = checker.compare("openai", checker.parse_openai(OPENAI_PAGE), ["gpt-5.2"])
    assert not any("pro" in t for _, t in found)
    assert any("gpt-6-luna" in t for _, t in found)


def test_report_says_ok_when_everything_matches():
    assert checker.report({"claude": [], "openai": []}, []).startswith("OK")


def test_a_page_that_cant_be_read_is_reported_not_ignored(tmp_path):
    empty = tmp_path / "empty.md"
    empty.write_text("# nothing here", encoding="utf-8")
    out = tmp_path / "report.md"
    code = checker.main(["--anthropic", str(empty), "--openai", str(empty), "--report", str(out)])
    text = out.read_text(encoding="utf-8")
    # ERROR, not DIFFERS, and a failing exit: the workflow fails the run and
    # leaves an open issue's real findings alone.
    assert code == 1
    assert text.startswith("ERROR")
    assert "Couldn't check" in text and "layout" in text


# --- The real pages, as of 11/18/2026 ----------------------------------------
# Copies in pytest_tests/fixtures/pricing/, so a parser change that breaks on
# the real layout fails here, not only on a Monday.

_FIXTURES = _ROOT / "pytest_tests" / "fixtures" / "pricing"


def test_the_real_anthropic_page_parses():
    page = checker.parse_anthropic((_FIXTURES / "anthropic-pricing-2026-11-18.md")
                                   .read_text(encoding="utf-8"))
    assert page["Claude Haiku 5.5"][:2] == (0.10, 0.50)        # the up-to-100K row
    assert page["Claude Opus 5.5"][:2] == (4.0, 20.0)
    assert page["Claude Sonnet 5"][:2] == (2.0, 10.0)          # footnote marker
    assert page["Claude Opus 4.1"][2] is True                  # retired
    assert len(page) >= 15


def test_the_real_openai_page_parses():
    page = checker.parse_openai((_FIXTURES / "openai-pricing-2026-11-18.md")
                                .read_text(encoding="utf-8"))
    assert page["gpt-5.2"][:2] == (1.75, 14.0)                  # standard, not batch
    assert page["gpt-5-nano"][:2] == (0.05, 0.40)
    assert page["gpt-5.5"][:2] == (5.0, 30.0)                   # long-context table, short rate
    assert page["gpt-6-luna"][:2] == (0.10, 0.50)


def test_every_claude_price_matches_the_real_page():
    page = checker.parse_anthropic((_FIXTURES / "anthropic-pricing-2026-11-18.md")
                                   .read_text(encoding="utf-8"))
    from idt_core.providers.claude import CLAUDE_MODELS
    assert [f for f in checker.compare("claude", page, list(CLAUDE_MODELS))] == []


def test_kept_for_old_workspaces_are_not_reported_gone():
    page = checker.parse_anthropic(ANTHROPIC_PAGE)
    found = checker.compare("claude", page, [])
    assert not any("claude-haiku-3-5" in t for _, t in found)
