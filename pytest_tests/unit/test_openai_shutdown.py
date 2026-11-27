"""OpenAI's 12/11/2026 shutdown of GPT-5, GPT-5 mini, GPT-5 nano and o3.

They leave the offered list (RETIRED_MODELS; test_openai_model_list.py covers
what that means for pickers, names and prices), and a request that fails
because the model is gone says so, in the command line and in ImageDescriber.
OpenAI's own message ("The model `gpt-5-mini` does not exist or you do not have
access to it") says neither why nor what to do.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from idt_core import generation  # noqa: E402
from idt_core import pricing  # noqa: E402
from idt_core.providers import openai_provider as oai  # noqa: E402

pytestmark = pytest.mark.unit

SHUT_DOWN_12_11 = ("gpt-5", "gpt-5-mini", "gpt-5-nano", "o3")


class NotFoundError(Exception):
    """Shaped like the SDK's: a status_code attribute and OpenAI's wording."""
    status_code = 404

    def __init__(self, model):
        super().__init__(f"Error code: 404 - {{'error': {{'message': 'The model `{model}` "
                         f"does not exist or you do not have access to it.', "
                         f"'code': 'model_not_found'}}}}")


class ServerError(Exception):
    status_code = 500


@pytest.mark.parametrize("model", SHUT_DOWN_12_11)
def test_retired_and_still_priced(model):
    assert model in oai.RETIRED_MODELS
    assert model not in oai.OPENAI_MODELS
    assert model in pricing.KEPT_FOR_OLD_WORKSPACES
    assert "12/11/2026" in oai.get_openai_model_info(model)["description"]


def test_the_hint_names_the_model_and_a_replacement():
    assert oai.shut_down_hint("gpt-5-mini") == (
        "OpenAI has shut down GPT-5 Mini. Choose another OpenAI model, such as GPT-6 Luna.")


def test_no_hint_for_a_model_still_offered():
    assert oai.shut_down_hint(oai.DEFAULT_MODEL) == ""
    assert oai.shut_down_hint("gpt-5.2") == ""


def _core(model, error):
    provider = oai.OpenAIProvider.__new__(oai.OpenAIProvider)
    provider._model, provider._options = model, None

    def create(**kw):
        raise error
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return provider


def test_cli_404_for_a_shut_down_model_says_so():
    error = NotFoundError("gpt-5-mini")
    with pytest.raises(RuntimeError) as info:
        _core("gpt-5-mini", error).describe(b"x", "image/jpeg", "Describe.")
    assert "does not exist" in str(info.value)              # OpenAI's words kept
    assert "OpenAI has shut down GPT-5 Mini" in str(info.value)
    assert info.value.__cause__ is error                     # chain kept for classifiers


def test_cli_other_failures_are_unchanged():
    with pytest.raises(ServerError):
        _core("gpt-5-mini", ServerError("boom")).describe(b"x", "image/jpeg", "Describe.")
    with pytest.raises(NotFoundError):
        _core("gpt-6-luna", NotFoundError("gpt-6-luna")).describe(b"x", "image/jpeg", "Describe.")


@pytest.fixture
def ai_providers(monkeypatch):
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    monkeypatch.setattr(generation, "_load_config", lambda: {})
    import ai_providers as module
    monkeypatch.setattr(module.time, "sleep", lambda s: None)
    return module


def _gui_describe(ai_providers, tmp_path, model, error):
    from PIL import Image
    img = tmp_path / "a.jpg"
    Image.new("RGB", (8, 8)).save(img)

    def create(**kw):
        raise error
    provider = ai_providers.OpenAIProvider(api_key="sk-test-not-real")
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    with pytest.raises(ai_providers.ProviderError) as info:
        provider.describe_image(str(img), "Describe.", model)
    return str(info.value)


def test_imagedescriber_404_for_a_shut_down_model_says_so(ai_providers, tmp_path):
    message = _gui_describe(ai_providers, tmp_path, "o3", NotFoundError("o3"))
    assert "OpenAI has shut down O3. Choose another OpenAI model, such as GPT-6 Luna." in message
    assert "(status code: 404)" in message                   # the retry contract's token


def test_imagedescriber_404_for_a_current_model_has_no_hint(ai_providers, tmp_path):
    message = _gui_describe(ai_providers, tmp_path, "gpt-6-luna", NotFoundError("gpt-6-luna"))
    assert "shut down" not in message
