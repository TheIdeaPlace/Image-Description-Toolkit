"""The built-in (offline) OpenAI model list (issue #453).

It is what every picker shows before a live refresh, and what anyone without
network access ever sees. In November 2026 it still ended at GPT-5.2, a year
of releases behind, and offered three models OpenAI had shut down (o1,
o4-mini, gpt-4.1-nano). These pin the list to what GET /v1/models and
OpenAI's model pages reported on 11/18/2026.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from idt_core import pricing  # noqa: E402
from idt_core.providers import catalog  # noqa: E402
from idt_core.providers import openai_provider as oai  # noqa: E402
from idt_core.providers.openai_provider import (  # noqa: E402
    DEFAULT_MODEL,
    OPENAI_MODEL_METADATA,
    OPENAI_MODELS,
    RETIRED_MODELS,
)

pytestmark = pytest.mark.unit

#: Every image-input chat model GET /v1/models listed on 11/18/2026 that isn't
#: a -pro, codex or live model.
CURRENT = ["gpt-6.2-astra", "gpt-6.2-sol", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-astra",
           "gpt-6-sol", "gpt-6-luna", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
           "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"]


@pytest.mark.parametrize("model_id", CURRENT)
def test_the_current_models_are_offered_offline(model_id):
    assert model_id in OPENAI_MODELS


def test_the_default_is_offered_and_first():
    """GPT-6 Luna: the cheapest current model, at Haiku 5.5's price. First in
    the list too, so a picker's index-0 fallback agrees with the default."""
    assert DEFAULT_MODEL == "gpt-6-luna"
    assert OPENAI_MODELS[0] == DEFAULT_MODEL


def test_the_newest_models_come_first():
    assert OPENAI_MODELS[:4] == ["gpt-6-luna", "gpt-6.1-terra", "gpt-6.2-sol", "gpt-6.2-astra"]


@pytest.mark.parametrize("model_id", RETIRED_MODELS)
def test_shut_down_models_are_not_offered(model_id):
    assert model_id not in OPENAI_MODELS


@pytest.mark.parametrize("model_id", RETIRED_MODELS)
def test_a_shut_down_model_still_shows_its_name(model_id):
    """Old workspaces recorded these ids; they must not turn into raw strings."""
    entry = catalog.model_entry("openai", model_id)
    assert entry.name != model_id
    assert entry.context_window


@pytest.mark.parametrize("model_id", RETIRED_MODELS)
def test_a_shut_down_model_is_still_priced_for_old_workspaces(model_id):
    assert pricing.rates_for(model_id) is not None
    assert model_id in pricing.KEPT_FOR_OLD_WORKSPACES


def test_a_shut_down_model_does_not_return_after_a_refresh():
    """A live listing without it must not bring it back into the picker."""
    merged = catalog.merge("openai", [{"id": m, "name": "", "created": 0} for m in CURRENT])
    ids = [e.id for e in merged]
    assert not set(RETIRED_MODELS) & set(ids)
    assert ids[0] == DEFAULT_MODEL


def test_every_offered_model_has_complete_metadata():
    for model_id in OPENAI_MODELS:
        meta = OPENAI_MODEL_METADATA[model_id]
        for field in ("name", "description", "context_window", "max_output", "cost"):
            assert meta.get(field), f"{model_id} has no {field}"
        assert meta["supports_vision"] is True


def test_no_live_only_model_is_offered_without_a_name():
    """Every new model in a live listing is curated, not 'new — details unknown'."""
    merged = catalog.merge("openai", [{"id": m, "name": "", "created": 0} for m in CURRENT])
    unknown = [e.id for e in merged if not e.is_known]
    assert unknown == []


def test_limits_match_the_model_pages():
    """docs/models/<id>.md, "Model details", 11/18/2026."""
    assert catalog.model_entry("openai", "gpt-6-luna").context_window == 1_050_000
    assert catalog.model_entry("openai", "gpt-6-luna").max_output == 128_000
    assert catalog.model_entry("openai", "gpt-5.4-mini").context_window == 400_000
    assert catalog.model_entry("openai", "gpt-5.4").context_window == 1_050_000
    assert catalog.model_entry("openai", "gpt-5.2").context_window == 400_000
    assert catalog.model_entry("openai", "o3").max_output == 100_000


def test_cost_buckets_follow_the_input_price():
    """$ under $1, $$ under $3, $$$ under $6, $$$$ above, as for Claude."""
    for model_id in OPENAI_MODELS:
        price = pricing.PRICES["openai"][model_id].input
        expected = "$" if price < 1 else "$$" if price < 3 else "$$$" if price < 6 else "$$$$"
        assert OPENAI_MODEL_METADATA[model_id]["cost"] == expected, model_id


def test_recommended_models_are_the_current_tier():
    recommended = [m for m in OPENAI_MODELS if OPENAI_MODEL_METADATA[m]["recommended"]]
    assert recommended == ["gpt-6-luna", "gpt-6.1-terra", "gpt-6.2-sol"]


def test_idt_stats_has_a_price_for_every_offered_model():
    from cli import main as cli_main

    for model_id in OPENAI_MODELS:
        assert model_id in cli_main.STATS_COST_TABLE, f"no price for {model_id}"
    assert cli_main.STATS_COST_TABLE["gpt-6-luna"] == (0.10, 0.50)


@pytest.mark.parametrize("model_id", OPENAI_MODELS)
def test_every_offered_model_is_classed_as_reasoning_or_not(model_id):
    """Every GPT-5 and later model and o3 reasons; only the GPT-4 models don't.
    Real requests on 11/18/2026: every GPT-6 and GPT-5.5/5.6 model rejected a
    temperature of 0.2."""
    assert oai.is_reasoning_model(model_id) is (not model_id.startswith("gpt-4"))


@pytest.mark.parametrize("model_id, least", [
    ("gpt-6.2-sol-2026-10-01", "low"),          # a dated snapshot of a no-"none" model
    ("gpt-6-luna-2026-10-01", "none"),
])
def test_dated_snapshots_take_their_models_least_effort(model_id, least):
    assert oai.lowest_effort(model_id) == least
