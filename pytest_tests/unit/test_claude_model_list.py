"""The built-in (offline) Claude model list.

It is what every picker shows before a live refresh, and what anyone without
network access ever sees. In November 2026 it still ended at Opus 5 and Haiku
4.5, two months after Anthropic released the 5.5 models, and it offered two
Mythos models this account can't use. These pin the list to what
GET /v1/models reported on 11/17/2026.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from idt_core.providers import catalog  # noqa: E402
from idt_core.providers.claude import (  # noqa: E402
    CLAUDE_MODEL_METADATA,
    CLAUDE_MODELS,
    DEFAULT_MODEL,
)

pytestmark = pytest.mark.unit

NEW_MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5",
              "claude-fable-5-2", "claude-fable-5-1"]


@pytest.mark.parametrize("model_id", NEW_MODELS)
def test_the_current_models_are_offered_offline(model_id):
    assert model_id in CLAUDE_MODELS


def test_the_newest_models_come_first():
    """Pickers fall back to the first entry, so the first must be current."""
    assert CLAUDE_MODELS[:3] == ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]


def test_the_default_is_offered_and_current():
    assert DEFAULT_MODEL == "claude-opus-5-5"
    assert DEFAULT_MODEL in CLAUDE_MODELS


@pytest.mark.parametrize("model_id", ["claude-mythos-5", "claude-mythos-preview",
                                      "claude-opus-4-1-20250805"])
def test_models_most_accounts_cannot_use_are_not_offered(model_id):
    assert model_id not in CLAUDE_MODELS


@pytest.mark.parametrize("model_id", ["claude-mythos-5", "claude-opus-4-1-20250805"])
def test_a_model_no_longer_offered_still_shows_its_name(model_id):
    """Old workspaces recorded these ids; they must not turn into raw strings."""
    assert catalog.model_entry("claude", model_id).name.startswith("Claude ")


def test_every_offered_model_has_complete_metadata():
    for model_id in CLAUDE_MODELS:
        meta = CLAUDE_MODEL_METADATA[model_id]
        for field in ("name", "description", "context_window", "max_output", "cost"):
            assert meta.get(field), f"{model_id} has no {field}"
        assert meta["supports_vision"] is True


def test_limits_match_what_the_api_reports():
    """1M context on 4.6 and later, 200K on the 4.5 models (GET /v1/models)."""
    assert catalog.model_entry("claude", "claude-haiku-5-5").context_window == 1_000_000
    assert catalog.model_entry("claude", "claude-haiku-5-5").max_output == 128_000
    assert catalog.model_entry("claude", "claude-sonnet-4-6").context_window == 1_000_000
    assert catalog.model_entry("claude", "claude-haiku-4-5-20251001").context_window == 200_000
    assert catalog.model_entry("claude", "claude-haiku-4-5-20251001").max_output == 64_000


def test_idt_stats_has_a_price_for_every_offered_model():
    """`idt stats` showed no cost for any 5.x model and charged Opus 4.8 at
    three times its real price. Opus 4.1 is retired but still priced, for old
    workspaces. The Mythos models are deliberately unpriced: they're for
    verified organizations only and we have no confirmed price for them."""
    from cli import main as cli_main

    for model_id in [*CLAUDE_MODELS, "claude-opus-4-1-20250805"]:
        assert model_id in cli_main.STATS_COST_TABLE, f"no price for {model_id}"
    assert cli_main.STATS_COST_TABLE["claude-opus-4-8"] == (5.0, 25.0)
    assert cli_main.STATS_COST_TABLE["claude-haiku-5-5"] == (0.10, 0.50)


def test_recommended_models_are_the_current_tier():
    recommended = [m for m in CLAUDE_MODELS if CLAUDE_MODEL_METADATA[m]["recommended"]]
    assert recommended == ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
