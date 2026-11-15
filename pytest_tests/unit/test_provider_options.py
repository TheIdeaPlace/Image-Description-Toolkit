"""
Generation settings for OpenAI, Claude, Claude Code and Apple (issue #392, part 2).

Each provider maps the provider-neutral GenerationOptions onto what its models
take, drops the rest with one note, and retries without an optional parameter
a model rejects. These tests also pin three bugs the mapping replaced:

* the CLI sent ``max_tokens`` to OpenAI reasoning models, which reject it;
* ImageDescriber capped non-reasoning OpenAI models at 300 tokens;
* both Claude paths read ``content[0].text``, which is a thinking block on
  current models (thinking is on by default there).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from idt_core import generation  # noqa: E402
from idt_core.generation import (  # noqa: E402
    THINKING_OFF, THINKING_ON, GenerationOptions, note_dropped, send_with_fallback,
)


@pytest.fixture(autouse=True)
def _fresh_memory():
    generation._NOTED.clear()
    generation._REJECTED.clear()
    yield
    generation._NOTED.clear()
    generation._REJECTED.clear()


class BadRequest(Exception):
    status_code = 400


class ServerError(Exception):
    status_code = 500


# --------------------------------------------------------------------------- #
# Shared helpers                                                               #
# --------------------------------------------------------------------------- #

class TestSendWithFallback:
    def test_rejected_optional_parameter_is_dropped_and_remembered(self, caplog):
        calls = []

        def call(**kw):
            calls.append(dict(kw))
            if "temperature" in kw:
                raise BadRequest("Unsupported parameter: 'temperature' is not supported "
                                 "with this model.")
            return "ok"

        with caplog.at_level(logging.INFO, logger="idt_core.providers"):
            assert send_with_fallback(call, {"model": "m", "temperature": 0.2},
                                      ("temperature",), "openai", "m") == "ok"
            assert send_with_fallback(call, {"model": "m", "temperature": 0.2},
                                      ("temperature",), "openai", "m") == "ok"
        # Second request leaves it out up front: one failure per run, not per image.
        assert [("temperature" in c) for c in calls] == [True, False, False]
        assert caplog.text.count("sending again without temperature") == 1

    def test_a_rejected_value_is_not_remembered(self):
        # Once the user fixes the value it must be sent again, without a restart.
        calls = []

        def call(**kw):
            calls.append(dict(kw))
            if kw.get("temperature") == 3.0:
                raise BadRequest("Invalid value for 'temperature': must be between 0 and 2")
            return "ok"

        send_with_fallback(call, {"temperature": 3.0}, ("temperature",), "openai", "m")
        send_with_fallback(call, {"temperature": 0.5}, ("temperature",), "openai", "m")
        assert calls[-1] == {"temperature": 0.5}

    def test_unknown_settings_in_extra_body_are_dropped_on_rejection(self):
        from idt_core.generation import with_extra_body
        calls = []

        def call(**kw):
            calls.append(dict(kw))
            if "extra_body" in kw:
                raise BadRequest("Unrecognized request argument supplied: num_ctx")
            return "ok"

        params = {"model": "m", "extra_body": {"num_ctx": 8192}}
        send_with_fallback(call, params, with_extra_body(("temperature",), params), "openai", "m")
        assert "extra_body" not in calls[-1]

    def test_a_400_about_something_else_is_raised(self):
        def call(**kw):
            raise BadRequest("Invalid image data")

        with pytest.raises(BadRequest):
            send_with_fallback(call, {"temperature": 0.2}, ("temperature",), "openai", "m")

    def test_server_errors_are_never_treated_as_rejections(self):
        def call(**kw):
            raise ServerError("temperature sensor overheated")

        with pytest.raises(ServerError):
            send_with_fallback(call, {"temperature": 0.2}, ("temperature",), "openai", "m")

    def test_nested_parameters_are_found_by_their_words(self):
        calls = []

        def call(**kw):
            calls.append(dict(kw))
            if "output_config" in kw:
                raise BadRequest("effort is not supported on this model")
            return "ok"

        send_with_fallback(call, {"output_config": {"effort": "low"}},
                           {"output_config": ("effort",)}, "claude", "claude-haiku-4-5")
        assert "output_config" not in calls[-1]

    def test_memory_is_per_model(self):
        def call(**kw):
            if "temperature" in kw and kw["model"] == "a":
                raise BadRequest("temperature")
            return kw

        send_with_fallback(call, {"model": "a", "temperature": 1.0}, ("temperature",), "openai", "a")
        result = send_with_fallback(call, {"model": "b", "temperature": 1.0},
                                    ("temperature",), "openai", "b")
        assert result["temperature"] == 1.0


def test_note_dropped_logs_once_per_setting(caplog):
    with caplog.at_level(logging.INFO, logger="idt_core.providers"):
        for _ in range(3):
            note_dropped("claude", "m", "temperature", "why")
        note_dropped("claude", "m", "top_p", "why")
    assert caplog.text.count("not sending temperature") == 1
    assert caplog.text.count("not sending top_p") == 1


# --------------------------------------------------------------------------- #
# OpenAI                                                                       #
# --------------------------------------------------------------------------- #

from idt_core.providers import openai_provider as oai  # noqa: E402


@pytest.mark.parametrize("model, reasoning", [
    ("gpt-5.2", True), ("gpt-5-nano", True), ("gpt-6-sol", True), ("gpt-5.4-mini", True),
    ("o3", True), ("o4-mini", True), ("o1", True),
    ("gpt-4o", False), ("gpt-4o-mini", False), ("gpt-4.1-nano", False), ("omni-moderation", False),
])
def test_reasoning_model_rule(model, reasoning):
    assert oai.is_reasoning_model(model) is reasoning


class TestOpenAIParams:
    def test_always_max_completion_tokens_never_max_tokens(self):
        for model in ("gpt-5.2", "gpt-4o"):
            params = oai.describe_request_params(model, None)
            assert "max_tokens" not in params
            assert params["max_completion_tokens"] == oai.DESCRIBE_MAX_OUTPUT_TOKENS

    def test_non_reasoning_models_are_not_capped_at_300(self):
        # ImageDescriber's old cap cut detailed descriptions off.
        assert oai.describe_request_params("gpt-4o", None)["max_completion_tokens"] > 300

    def test_user_cap(self):
        opts = GenerationOptions(max_output_tokens=900)
        assert oai.describe_request_params("gpt-4o", opts)["max_completion_tokens"] == 900

    def test_temperature_reaches_classic_models_only(self, caplog):
        opts = GenerationOptions(temperature=0.2, top_p=0.9)
        assert oai.describe_request_params("gpt-4o", opts)["temperature"] == 0.2
        with caplog.at_level(logging.INFO, logger="idt_core.providers"):
            params = oai.describe_request_params("gpt-5.2", opts)
        assert "temperature" not in params and "top_p" not in params
        assert "not sending temperature" in caplog.text

    @pytest.mark.parametrize("model, sent", [
        ("gpt-5.2", "none"), ("gpt-6-sol", "none"),     # default "none": low would add reasoning
        ("gpt-5-mini", "minimal"), ("o3", "low"),
    ])
    def test_thinking_off_is_the_least_effort_each_family_takes(self, model, sent):
        opts = GenerationOptions(thinking=THINKING_OFF)
        assert oai.describe_request_params(model, opts)["reasoning_effort"] == sent

    def test_thinking_off_sends_nothing_to_classic_models(self):
        opts = GenerationOptions(thinking=THINKING_OFF)
        assert "reasoning_effort" not in oai.describe_request_params("gpt-4o", opts)

    def test_a_rejected_none_is_retried_at_low_before_dropping(self):
        calls = []

        def create(**kw):
            calls.append(dict(kw))
            if kw.get("reasoning_effort") == "none":
                raise BadRequest("Unsupported value: 'reasoning_effort' does not support 'none'")
            return _openai_response("A desk.")

        provider, _ = _core_openai([], options=GenerationOptions(thinking=THINKING_OFF))
        provider._client = SimpleNamespace(chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)))
        assert provider.describe(b"x", "image/jpeg", "Describe.").text == "A desk."
        assert [c.get("reasoning_effort") for c in calls] == ["none", "low"]

    def test_explicit_effort_wins(self):
        opts = GenerationOptions(thinking=THINKING_OFF, effort="high")
        assert oai.describe_request_params("o3", opts)["reasoning_effort"] == "high"

    def test_automatic_sends_no_effort(self):
        assert "reasoning_effort" not in oai.describe_request_params("gpt-5.2", None)

    def test_ollama_only_settings_are_noted(self, caplog):
        with caplog.at_level(logging.INFO, logger="idt_core.providers"):
            params = oai.describe_request_params("gpt-4o", GenerationOptions(top_k=40))
        assert "top_k" not in params
        assert "not sending top_k" in caplog.text

    @pytest.mark.parametrize("model, sent", [
        ("gpt-5", "minimal"), ("gpt-5-mini", "minimal"), ("gpt-5-nano-2025-08-07", "minimal"),
        ("gpt-5.2", "none"), ("o3", "low"), ("gpt-6-sol", "none"),
    ])
    def test_minimal_effort_is_the_least_each_family_takes(self, model, sent):
        opts = GenerationOptions(effort="minimal")
        assert oai.describe_request_params(model, opts)["reasoning_effort"] == sent

    def test_out_of_range_temperature_is_not_sent(self):
        params = oai.describe_request_params("gpt-4o", GenerationOptions(temperature=3.0))
        assert "temperature" not in params

    def test_unknown_settings_go_in_the_body_not_as_keywords(self):
        # As keyword arguments they were a TypeError that failed every image.
        opts = GenerationOptions.from_dict({"temprature": 0.2})
        params = oai.describe_request_params("gpt-4o", opts)
        assert "temprature" not in params
        assert params["extra_body"] == {"temprature": 0.2}


def _openai_response(content, finish="stop", completion=50, reasoning=None):
    details = SimpleNamespace(reasoning_tokens=reasoning) if reasoning is not None else None
    return SimpleNamespace(
        id="r1", model="m",
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, role="assistant"),
                                 finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=completion, total_tokens=60,
                              completion_tokens_details=details))


def _core_openai(responses, options=None, model="gpt-5.2"):
    provider = oai.OpenAIProvider.__new__(oai.OpenAIProvider)
    provider._model = model
    provider._options = options
    calls = []

    def create(**kw):
        calls.append(kw)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return provider, calls


class TestOpenAIDescribe:
    def test_success_reports_reasoning_tokens(self):
        provider, calls = _core_openai([_openai_response("A desk.", reasoning=192)])
        result = provider.describe(b"x", "image/jpeg", "Describe.")
        assert result.text == "A desk." and result.thinking_tokens == 192
        assert calls[0]["max_completion_tokens"] == oai.DESCRIBE_MAX_OUTPUT_TOKENS

    def test_all_reasoning_no_answer_is_an_error_not_a_blank(self):
        provider, _ = _core_openai([_openai_response("", finish="length", reasoning=4096)])
        with pytest.raises(RuntimeError, match="reasoning effort"):
            provider.describe(b"x", "image/jpeg", "Describe.")

    @pytest.mark.parametrize("content, finish", [("", "stop"), (None, "stop"), ("  ", "stop")])
    def test_any_empty_answer_is_an_error(self, content, finish):
        from idt_core.providers.base import EmptyAnswerError
        provider, _ = _core_openai([_openai_response(content, finish=finish)])
        with pytest.raises(EmptyAnswerError):
            provider.describe(b"x", "image/jpeg", "Describe.")

    def test_a_refusal_is_a_declined_picture(self):
        from idt_core.pipeline import is_per_image_failure
        from idt_core.providers.base import DeclinedError
        response = _openai_response(None)
        response.choices[0].message.refusal = "I can't help with that."
        provider, _ = _core_openai([response])
        with pytest.raises(DeclinedError) as info:
            provider.describe(b"x", "image/jpeg", "Describe.")
        assert is_per_image_failure(info.value)

    def test_content_filter_is_a_declined_picture(self):
        from idt_core.providers.base import DeclinedError
        provider, _ = _core_openai([_openai_response("", finish="content_filter")])
        with pytest.raises(DeclinedError):
            provider.describe(b"x", "image/jpeg", "Describe.")

    def test_truncation_is_reported(self):
        provider, _ = _core_openai([_openai_response("A desk with", finish="length")])
        assert provider.describe(b"x", "image/jpeg", "Describe.").truncated

    def test_rejected_temperature_is_retried_without(self):
        provider, calls = _core_openai(
            [BadRequest("Unsupported parameter: 'temperature'"), _openai_response("A desk.")],
            options=GenerationOptions(temperature=0.2), model="gpt-4o")
        assert provider.describe(b"x", "image/jpeg", "Describe.").text == "A desk."
        assert "temperature" in calls[0] and "temperature" not in calls[1]


# --------------------------------------------------------------------------- #
# Claude                                                                       #
# --------------------------------------------------------------------------- #

from idt_core.providers import claude as claude_mod  # noqa: E402


class TestClaudeParams:
    def test_defaults(self):
        params = claude_mod.describe_request_params("claude-opus-5-5", None)
        assert params == {"model": "claude-opus-5-5",
                          "max_tokens": claude_mod.DESCRIBE_MAX_OUTPUT_TOKENS}

    def test_sampling_settings_are_never_sent(self, caplog):
        opts = GenerationOptions(temperature=0.2, top_p=0.9, top_k=40)
        with caplog.at_level(logging.INFO, logger="idt_core.providers"):
            params = claude_mod.describe_request_params("claude-opus-5-5", opts)
        assert not {"temperature", "top_p", "top_k"} & set(params)
        assert "not sending temperature" in caplog.text

    def test_thinking_on_is_adaptive(self):
        opts = GenerationOptions(thinking=THINKING_ON)
        assert claude_mod.describe_request_params("m", opts)["thinking"] == {"type": "adaptive"}

    def test_thinking_off_is_low_effort_never_disabled(self):
        # {"type": "disabled"} is a 400 on Opus 5.5 and Sonnet 5.5.
        params = claude_mod.describe_request_params("m", GenerationOptions(thinking=THINKING_OFF))
        assert params["output_config"] == {"effort": "low"}
        assert "thinking" not in params

    def test_minimal_effort_maps_to_low(self):
        params = claude_mod.describe_request_params("m", GenerationOptions(effort="minimal"))
        assert params["output_config"] == {"effort": "low"}


def _block(kind, text=None):
    return SimpleNamespace(type=kind, text=text) if text is not None else SimpleNamespace(type=kind)


def _claude_message(blocks, stop="end_turn"):
    return SimpleNamespace(content=blocks, stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=10, output_tokens=40))


def test_response_text_skips_thinking_blocks():
    message = _claude_message([_block("thinking"), _block("text", "A desk."), _block("text", " Two cups.")])
    assert claude_mod.response_text(message) == "A desk. Two cups."


def _core_claude(responses, options=None):
    provider = claude_mod.ClaudeProvider.__new__(claude_mod.ClaudeProvider)
    provider._model = "claude-opus-5-5"
    provider._options = options
    calls = []

    def create(**kw):
        calls.append(kw)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return provider, calls


class TestClaudeDescribe:
    def test_a_thinking_block_first_still_yields_the_description(self):
        provider, _ = _core_claude([_claude_message([_block("thinking"), _block("text", "A desk.")])])
        assert provider.describe(b"x", "image/jpeg", "Describe.").text == "A desk."

    def test_all_thinking_no_answer_is_an_error(self):
        provider, _ = _core_claude([_claude_message([_block("thinking")], stop="max_tokens")])
        with pytest.raises(RuntimeError, match="output allowance"):
            provider.describe(b"x", "image/jpeg", "Describe.")

    @pytest.mark.parametrize("stop", ["end_turn", "pause_turn", "model_context_window_exceeded"])
    def test_any_empty_answer_is_an_error_not_a_saved_blank(self, stop):
        from idt_core.providers.base import EmptyAnswerError
        provider, _ = _core_claude([_claude_message([_block("thinking")], stop=stop)])
        with pytest.raises(EmptyAnswerError, match="Claude"):
            provider.describe(b"x", "image/jpeg", "Describe.")

    def test_a_refusal_is_a_declined_picture_that_does_not_stop_the_run(self):
        from idt_core.pipeline import is_per_image_failure
        from idt_core.providers.base import DeclinedError
        provider, _ = _core_claude([_claude_message([], stop="refusal")])
        with pytest.raises(DeclinedError) as info:
            provider.describe(b"x", "image/jpeg", "Describe.")
        assert is_per_image_failure(info.value)

    def test_unknown_settings_go_in_the_body(self):
        opts = GenerationOptions.from_dict({"num_ctx": 8192})
        params = claude_mod.describe_request_params("m", opts)
        assert "num_ctx" not in params and params["extra_body"] == {"num_ctx": 8192}

    def test_rejected_effort_is_retried_without(self):
        provider, calls = _core_claude(
            [BadRequest("output_config.effort: not supported for claude-haiku-4-5"),
             _claude_message([_block("text", "A desk.")])],
            options=GenerationOptions(effort="low"))
        assert provider.describe(b"x", "image/jpeg", "Describe.").text == "A desk."
        assert "output_config" in calls[0] and "output_config" not in calls[1]

    def test_oversized_images_are_shrunk_before_sending(self):
        import base64
        import io
        import os

        from PIL import Image

        noisy = Image.frombytes("RGB", (3000, 2400), os.urandom(3000 * 2400 * 3))
        buf = io.BytesIO()
        noisy.save(buf, format="PNG")
        assert len(buf.getvalue()) > 5 * 1024 * 1024
        provider, calls = _core_claude([_claude_message([_block("text", "Noise.")])])
        provider.describe(buf.getvalue(), "image/png", "Describe.")
        sent = calls[0]["messages"][0]["content"][0]["source"]["data"]
        assert len(base64.b64decode(sent)) < 5 * 1024 * 1024


# --------------------------------------------------------------------------- #
# Claude Code and Apple                                                        #
# --------------------------------------------------------------------------- #

class TestClaudeCode:
    def test_settings(self, caplog):
        from idt_core.providers.claude_code import describe_settings
        assert describe_settings("haiku", None) == (None, None)
        assert describe_settings("haiku", GenerationOptions(thinking=THINKING_OFF)) == ("low", None)
        assert describe_settings("haiku", GenerationOptions(effort="high",
                                                            max_output_tokens=800)) == ("high", 800)
        with caplog.at_level(logging.INFO, logger="idt_core.providers"):
            describe_settings("haiku", GenerationOptions(temperature=0.3))
            assert describe_settings("haiku", GenerationOptions(thinking=THINKING_ON)) == (None, None)
        assert "not sending temperature" in caplog.text
        assert "not sending thinking on" in caplog.text

    def test_effort_reaches_the_command_line(self):
        from idt_core.providers.claude_code import build_command
        cmd = build_command("claude", "haiku", "p.txt", effort="low")
        assert cmd[-2:] == ["--effort", "low"]
        assert "--effort" not in build_command("claude", "haiku", "p.txt")


class TestApple:
    def test_settings(self, caplog):
        from idt_core.providers.apple import DESCRIBE_MAX_OUTPUT_TOKENS, describe_settings
        assert describe_settings("m", None) == (DESCRIBE_MAX_OUTPUT_TOKENS, None)
        assert describe_settings("m", GenerationOptions(max_output_tokens=300,
                                                        temperature=0.2)) == (300, 0.2)
        with caplog.at_level(logging.INFO, logger="idt_core.providers"):
            describe_settings("m", GenerationOptions(thinking=THINKING_ON))
        assert "not sending thinking" in caplog.text


# --------------------------------------------------------------------------- #
# ImageDescriber uses the same mapping                                         #
# --------------------------------------------------------------------------- #

@pytest.fixture
def gui(monkeypatch):
    """ai_providers importable, and no real settings file read."""
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    monkeypatch.setattr(generation, "_load_config", lambda: {})
    import ai_providers
    monkeypatch.setattr(ai_providers.time, "sleep", lambda s: None)
    return ai_providers


def _gui_image(tmp_path):
    from PIL import Image
    img = tmp_path / "a.jpg"
    Image.new("RGB", (8, 8)).save(img)
    return str(img)


class TestImageDescriber:
    @pytest.fixture(autouse=True)
    def _gui(self, gui):
        return gui
    def test_openai_uses_the_shared_request(self, tmp_path, monkeypatch):
        img = _gui_image(tmp_path)
        import ai_providers
        monkeypatch.setattr(generation, "_load_config",  # overrides the fixture's {}
                            lambda: {"generation": {"openai": {"temperature": 0.3}}})
        calls = []

        def create(**kw):
            calls.append(kw)
            return _openai_response("A square.")

        gui = ai_providers.OpenAIProvider(api_key="sk-test-not-real")
        gui.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        assert gui.describe_image(img, "Describe.", "gpt-4o") == "A square."
        assert calls[0]["max_completion_tokens"] == oai.DESCRIBE_MAX_OUTPUT_TOKENS
        assert calls[0]["temperature"] == 0.3
        assert "max_tokens" not in calls[0]

    def test_claude_reads_past_a_thinking_block(self, tmp_path):
        img = _gui_image(tmp_path)
        import ai_providers
        gui = ai_providers.ClaudeProvider(api_key="sk-ant-test-not-real")
        gui.client = SimpleNamespace(messages=SimpleNamespace(
            create=lambda **kw: _claude_message([_block("thinking"), _block("text", "A square.")])))
        assert gui.describe_image(img, "Describe.", "claude-opus-5-5") == "A square."

    def test_sdk_clients_retry_once_at_most(self):
        # One SDK retry (for retry-after) inside the decorator's four: at most
        # 8 attempts per failing image, not the 16 it was.
        import ai_providers
        assert ai_providers._SDK_RETRIES == 1

    def test_a_dropped_connection_is_retried_by_the_decorator(self, tmp_path):
        # With the SDK's retries cut down, the decorator must catch these.
        img = _gui_image(tmp_path)
        import ai_providers

        class APIConnectionError(Exception):
            pass

        outcomes = [APIConnectionError("Connection error."), _openai_response("A square.")]

        def create(**kw):
            item = outcomes.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        provider = ai_providers.OpenAIProvider(api_key="sk-test-not-real")
        provider.client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        assert provider.describe_image(img, "Describe.", "gpt-4o") == "A square."

    def test_claude_empty_answer_message_is_a_full_sentence(self, tmp_path):
        img = _gui_image(tmp_path)
        import ai_providers
        provider = ai_providers.ClaudeProvider(api_key="sk-ant-test-not-real")
        provider.client = SimpleNamespace(messages=SimpleNamespace(
            create=lambda **kw: _claude_message([_block("thinking")], stop="max_tokens")))
        with pytest.raises(ai_providers.ProviderError) as info:
            provider.describe_image(img, "Describe.", "claude-opus-5-5")
        assert "Claude (claude-opus-5-5) used its whole output allowance" in str(info.value)
        assert "generation settings" in str(info.value)


# --------------------------------------------------------------------------- #
# Chat                                                                         #
# --------------------------------------------------------------------------- #

def test_openai_chat_never_sends_temperature_to_reasoning_models(monkeypatch):
    import openai

    from idt_core.chat.providers import OpenAIChatProvider
    from idt_core.providers.base import ChatRequest

    sent = []

    class FakeOpenAI:
        def __init__(self, *a, **k):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kw):
            sent.append(kw)
            return iter([])

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    for model in ("gpt-5.2", "gpt-4o"):
        list(OpenAIChatProvider(model, api_key="k").chat(
            ChatRequest(messages=[], model=model, temperature=0.2)))
    assert "temperature" not in sent[0]
    assert sent[1]["temperature"] == 0.2
