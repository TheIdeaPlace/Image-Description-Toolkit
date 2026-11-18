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

Standard library only: the weekly check imports this without IDT's
dependencies installed.
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
    "openai": {
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
    },
}

#: Priced only so old workspaces described with them can still be costed;
#: their providers no longer list them, so the weekly check doesn't expect them.
KEPT_FOR_OLD_WORKSPACES = {"claude-haiku-3-5-20241022"}

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


def flat_prices() -> dict:
    """{model_id: (input, output)} across every provider."""
    return {model: (p.input, p.output)
            for table in PRICES.values() for model, p in table.items()}


def rates_for(model: str) -> Optional[tuple]:
    """(input, output) per million tokens, or None. A dated snapshot such as
    "gpt-5-mini-2025-08-07" is priced as its model."""
    prices = flat_prices()
    if model in prices:
        return prices[model]
    return prices.get(_DATED_SNAPSHOT.sub("", model or ""))


def _is_ollama_cloud(model: str) -> bool:
    # Same rule as providers.ollama.is_cloud_model, kept here so this module
    # stays standard-library only.
    return ":cloud" in model or model.endswith("-cloud")


def no_charge_note(provider: str, model: str) -> str:
    """Why a provider/model has no per-token price, or "" if it should have one.
    ``provider`` is the canonical name (registry's capabilities_for(...).provider)."""
    note = NO_PER_TOKEN_CHARGE.get(provider, "")
    if provider in ("ollama", "ollama cloud") and _is_ollama_cloud(model or ""):
        note = "Ollama plan"
    return note


def running_cost(records) -> dict:
    """The meter for a batch in progress: what the described pictures cost so
    far, the average per picture, and what the whole batch will come to.

    ``records`` are dicts with provider (canonical name), model, input and
    output. Returns {"cost": float or None, "avg": float or None,
    "note": str}. When no record has a price, cost is None and note says why
    (the first record's: a batch uses one provider and model).
    """
    cost = 0.0
    priced = 0
    note = ""
    for r in records:
        c, n = estimate(r.get("provider", ""), r.get("model", ""),
                        r.get("input", 0), r.get("output", 0))
        if c is None:
            note = note or n
            continue
        cost += c
        priced += 1
    if not priced:
        return {"cost": None, "avg": None, "note": note}
    return {"cost": cost, "avg": cost / priced, "note": ""}


def format_dollars(amount: float) -> str:
    """$0.36, $12.50, or $0.00096 for a fraction of a cent, so a cheap
    model's per-picture cost doesn't read as $0.00."""
    if amount >= 0.01 or amount == 0:
        return f"${amount:,.2f}"
    return f"${amount:.5f}"


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
