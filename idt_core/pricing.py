"""What a description costs: the one price table for `idt stats` and ImageDescriber.

Providers don't report prices: their model lists give names and limits only,
and real billing needs an admin key. So IDT keeps list prices here, in US
dollars per million tokens (input, output), copied from each provider's
pricing page. They go stale whenever a provider changes a price or releases a
model, so `.github/workflows/model-prices.yml` compares them with the pages
every week (`tools/check_model_prices.py`) and files an issue when they differ.

Each entry also records the model's name as the pricing page writes it, which
is how the weekly check finds the row. Standard (not batch, priority or
cached) rates; Haiku 5.5's is the rate for prompts up to 100K tokens, which
every image description is.
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional


class Price(NamedTuple):
    page_name: str      # the row label on the provider's pricing page
    input: float        # USD per million input tokens
    output: float       # USD per million output tokens


#: Checked against the pricing pages on 11/18/2026.
PRICES: dict = {
    "claude": {
        "claude-fable-5-2":           Price("Claude Fable 5.2", 8.0, 40.0),
        "claude-fable-5-1":           Price("Claude Fable 5.1", 10.0, 50.0),
        "claude-fable-5":             Price("Claude Fable 5", 10.0, 50.0),
        "claude-opus-5-5":            Price("Claude Opus 5.5", 4.0, 20.0),
        "claude-opus-5":              Price("Claude Opus 5", 5.0, 25.0),
        "claude-opus-4-8":            Price("Claude Opus 4.8", 5.0, 25.0),
        "claude-opus-4-7":            Price("Claude Opus 4.7", 5.0, 25.0),
        "claude-opus-4-6":            Price("Claude Opus 4.6", 5.0, 25.0),
        "claude-opus-4-5-20251101":   Price("Claude Opus 4.5", 5.0, 25.0),
        "claude-opus-4-1-20250805":   Price("Claude Opus 4.1", 15.0, 75.0),
        "claude-sonnet-5-5":          Price("Claude Sonnet 5.5", 2.0, 10.0),
        "claude-sonnet-5":            Price("Claude Sonnet 5", 2.0, 10.0),
        "claude-sonnet-4-6":          Price("Claude Sonnet 4.6", 3.0, 15.0),
        "claude-sonnet-4-5-20250929": Price("Claude Sonnet 4.5", 3.0, 15.0),
        "claude-haiku-5-5":           Price("Claude Haiku 5.5", 0.10, 0.50),
        "claude-haiku-4-5-20251001":  Price("Claude Haiku 4.5", 1.0, 5.0),
        "claude-haiku-3-5-20241022":  Price("Claude Haiku 3.5", 0.8, 4.0),
    },
    # OpenAI: the "Standard pricing data" table of
    # https://developers.openai.com/api/docs/pricing.md (saved as
    # pytest_tests/fixtures/pricing/openai-pricing-2026-11-18.md). For the
    # models with a long-context price, the short-context rate (prompts under
    # 272K tokens), which every image description is.
    "openai": {
        "gpt-6.2-astra": Price("gpt-6.2-astra", 8.0, 40.0),
        "gpt-6.2-sol":   Price("gpt-6.2-sol", 2.0, 10.0),
        "gpt-6.1-sol":   Price("gpt-6.1-sol", 2.0, 10.0),
        "gpt-6.1-terra": Price("gpt-6.1-terra", 1.0, 5.0),
        "gpt-6-astra":   Price("gpt-6-astra", 10.0, 50.0),
        "gpt-6-sol":     Price("gpt-6-sol", 2.0, 10.0),
        "gpt-6-luna":    Price("gpt-6-luna", 0.10, 0.50),
        # A promotional price "available until November 30, 2026" (pricing
        # page and model page); the list price is $5 / $30. Kept at what
        # OpenAI charges today; the weekly price check flags the change.
        "gpt-5.6-sol":   Price("gpt-5.6-sol", 4.0, 20.0),
        "gpt-5.6-terra": Price("gpt-5.6-terra", 2.0, 12.0),
        "gpt-5.6-luna":  Price("gpt-5.6-luna", 0.20, 1.20),
        "gpt-5.5":       Price("gpt-5.5", 5.0, 30.0),
        "gpt-5.4":       Price("gpt-5.4", 2.5, 15.0),
        "gpt-5.4-mini":  Price("gpt-5.4-mini", 0.75, 4.50),
        "gpt-5.4-nano":  Price("gpt-5.4-nano", 0.20, 1.25),
        "gpt-5.2":      Price("gpt-5.2", 1.75, 14.0),
        "gpt-5.1":      Price("gpt-5.1", 1.25, 10.0),
        "gpt-5":        Price("gpt-5", 1.25, 10.0),
        "gpt-5-mini":   Price("gpt-5-mini", 0.25, 2.0),
        "gpt-5-nano":   Price("gpt-5-nano", 0.05, 0.40),
        "o3":           Price("o3", 2.0, 8.0),
        "gpt-4.1":      Price("gpt-4.1", 2.0, 8.0),
        "gpt-4.1-mini": Price("gpt-4.1-mini", 0.40, 1.60),
        "gpt-4o":       Price("gpt-4o", 2.5, 10.0),
        "gpt-4o-mini":  Price("gpt-4o-mini", 0.15, 0.60),
        # Shut down; no longer on the pricing page. Their last prices, from
        # each model's own page (docs/models/<id>.md, "Text tokens"), 11/18/2026.
        "o4-mini":      Price("o4-mini", 1.10, 4.40),
        "o1":           Price("o1", 15.0, 60.0),
        "gpt-4.1-nano": Price("gpt-4.1-nano", 0.10, 0.40),
    },
}

#: Priced only so old workspaces described with them can still be costed;
#: their providers no longer list them, so the weekly check doesn't expect them.
KEPT_FOR_OLD_WORKSPACES = {"claude-haiku-3-5-20241022", "o4-mini", "o1", "gpt-4.1-nano"}

#: Providers that don't bill per token, and what's shown instead of a price.
NO_PER_TOKEN_CHARGE = {
    "ollama": "no charge",
    "ollama cloud": "Ollama plan",
    "windows-ai": "no charge",
    "apple": "no charge",
    "mlx": "no charge",
    "claude-code": "your plan",
}

_DATED_SNAPSHOT = re.compile(r"-(\d{4}-\d{2}-\d{2}|\d{8})$")


_FLAT: Optional[dict] = None


def flat_prices() -> dict:
    """{model_id: (input, output)} across every provider. Built once."""
    global _FLAT
    if _FLAT is None:
        _FLAT = {model: (p.input, p.output)
                 for table in PRICES.values() for model, p in table.items()}
    return _FLAT


def rates_for(model: str) -> Optional[tuple]:
    """(input, output) per million tokens, or None. A dated snapshot such as
    "gpt-5-mini-2025-08-07" is priced as its model."""
    prices = flat_prices()
    if model in prices:
        return prices[model]
    return prices.get(_DATED_SNAPSHOT.sub("", model or ""))


def no_charge_note(provider: str, model: str) -> str:
    """Why a provider/model has no per-token price, or "" if it should have one.
    ``provider`` is the canonical name (registry's capabilities_for(...).provider)."""
    from .providers.ollama import is_cloud_model

    note = NO_PER_TOKEN_CHARGE.get(provider, "")
    if provider in ("ollama", "ollama cloud") and is_cloud_model(model or ""):
        note = "Ollama plan"
    return note


class CostMeter:
    """A batch's running cost, like a taxi meter: add each described picture
    as it finishes, read the total any time.

    Each picture is priced once, when it's added. Re-pricing every picture on
    every progress update grew with the square of the batch, about 0.2 s of
    blocked UI per picture late in a 7,000-picture batch (#451 review).
    Provider names are made canonical, so "anthropic" and "claude" price alike.
    """

    def __init__(self):
        self.cost = 0.0
        self.priced = 0
        self.note = ""          # why nothing could be priced, if so

    def add(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
        from .providers.registry import capabilities_for

        canonical = capabilities_for(provider or "").provider
        c, n = estimate(canonical, model or "", input_tokens, output_tokens)
        if c is None:
            self.note = self.note or n
            return
        self.cost += c
        self.priced += 1

    def reading(self) -> dict:
        """{"cost", "avg", "note"}: cost and avg are None when nothing was
        priced, and note then says why."""
        if not self.priced:
            return {"cost": None, "avg": None, "note": self.note}
        return {"cost": self.cost, "avg": self.cost / self.priced, "note": ""}


def running_cost(records) -> dict:
    """The meter's reading for a list of records (dicts with provider, model,
    input, output). For a batch in progress use CostMeter, which keeps the
    total as it goes."""
    meter = CostMeter()
    for r in records:
        meter.add(r.get("provider", ""), r.get("model", ""), r.get("input", 0), r.get("output", 0))
    return meter.reading()


def format_dollars(amount: float) -> str:
    """A cost, read aloud easily: under a dollar in cents, from a dollar up in
    dollars and cents.

    "0.096 cents", "2.1 cents", "62 cents", "$1.24", "$1,234.50". Under ten
    cents it keeps two significant figures, so a real cost is never rounded
    to nothing. All in cents under a dollar so the batch window's lines can
    be compared by ear: it read "Estimated Cost So Far: $0.02" beside
    "Average Cost per Image: 0.11 cents", which sounded as if they didn't add
    up (Kelly, 11/19/2026; it was 2.1 cents over 19 pictures).
    """
    amount = max(amount, 0.0)              # a cost is never negative
    if amount == 0:
        return "0 cents"
    # Decided on the rounded figure: 0.995 is stored as 0.99499..., which
    # passed ">= 0.995" and then printed as "$0.99" (#495 review).
    if round(amount, 2) >= 1:
        return f"${amount:,.2f}"
    cents = amount * 100
    if cents < 0.0001:                     # :.2g would switch to "1e-05"
        return "less than 0.0001 cents"
    text = f"{cents:.0f}" if cents >= 9.95 else f"{cents:.2g}"
    return "1 cent" if text == "1" else f"{text} cents"


def estimate(provider: str, model: str, input_tokens: int, output_tokens: int):
    """(cost or None, note) for this many tokens.

    note is "" when there's a cost, else the reason there isn't one:
    "no charge", "Ollama plan", "your plan" or "no price".
    """
    note = no_charge_note(provider, model)
    if note:
        return None, note
    rates = rates_for(model)
    if rates is None:
        return None, "no price"
    return ((input_tokens or 0) / 1_000_000 * rates[0]
            + (output_tokens or 0) / 1_000_000 * rates[1]), ""
