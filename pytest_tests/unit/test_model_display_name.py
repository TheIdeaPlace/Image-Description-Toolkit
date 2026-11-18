"""Models are shown and spoken by name, not by API ID.

ImageDescriber's description details and batch progress said
"Model: claude-haiku-5-5", read aloud as "claude dash haiku dash 5 dash 5",
where the model is called "Claude Haiku 5.5" everywhere else (11/17/2026).
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from idt_core.providers.catalog import model_display_name  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("provider, model, expected", [
    ("claude", "claude-haiku-5-5", "Claude Haiku 5.5"),
    ("anthropic", "claude-opus-5-5", "Claude Opus 5.5"),
    ("Claude", "claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
    ("claude", "claude-mythos-5", "Claude Mythos 5"),      # not offered, still named
    ("openai", "gpt-5.2", "GPT-5.2"),
    ("claude-code", "haiku", "Haiku (subscription)"),
    ("windows-ai", "accessible", "Accessible"),
])
def test_known_models_show_their_names(provider, model, expected):
    assert model_display_name(provider, model) == expected


@pytest.mark.parametrize("provider, model", [
    ("ollama", "moondream"),             # an Ollama tag is its own name
    ("claude", "claude-future-9"),       # released after this build
    ("", "claude-haiku-5-5"),            # provider unknown: never guess
    ("no-such-provider", "x"),
])
def test_anything_without_a_name_shows_its_id(provider, model):
    assert model_display_name(provider, model) == model


def test_no_model_shows_nothing():
    assert model_display_name("claude", "") == ""
    assert model_display_name(None, None) == ""
