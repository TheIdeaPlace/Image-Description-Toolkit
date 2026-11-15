"""
Generation options and the Ollama thinking policy (issue #392).

Descriptions used to send no options and no ``think`` to Ollama, so thinking
models reasoned at their default on every image: 60-75% of the output and most
of the time, all of it discarded. One run returned an empty description after
13,000 characters of reasoning. These tests pin the policy that replaced it:
automatic defaults per provider, thinking off for descriptions, user and
command-line overrides on top, and no silent blank descriptions.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from idt_core.generation import (  # noqa: E402
    THINKING_AUTO, THINKING_OFF, THINKING_ON, GenerationOptions, think_flag,
    thinking_mode, user_options,
)
from idt_core.providers import ollama as ollama_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_show_cache():
    """Capability answers are cached per (host, model); no test may see another's."""
    ollama_mod._SHOW_CACHE.clear()
    ollama_mod._NEGATIVE_AT.clear()
    yield
    ollama_mod._SHOW_CACHE.clear()
    ollama_mod._NEGATIVE_AT.clear()


# --------------------------------------------------------------------------- #
# GenerationOptions                                                            #
# --------------------------------------------------------------------------- #

class TestFromDict:
    def test_empty_is_automatic(self):
        assert GenerationOptions.from_dict(None).is_automatic()
        assert GenerationOptions.from_dict({}).is_automatic()

    def test_none_and_blank_mean_automatic(self):
        opts = GenerationOptions.from_dict({"temperature": None, "thinking": ""})
        assert opts.is_automatic()

    def test_aliases(self):
        opts = GenerationOptions.from_dict(
            {"num_predict": 700, "think": False, "reasoning_effort": "low"})
        assert opts.max_output_tokens == 700
        assert opts.thinking == THINKING_OFF
        assert opts.effort == "low"

    @pytest.mark.parametrize("raw, expected", [
        (True, THINKING_ON), (False, THINKING_OFF), ("On", THINKING_ON),
        ("false", THINKING_OFF), ("automatic", THINKING_AUTO), ("auto", THINKING_AUTO),
    ])
    def test_thinking_spellings(self, raw, expected):
        assert GenerationOptions.from_dict({"thinking": raw}).thinking == expected

    def test_numbers_are_coerced(self):
        opts = GenerationOptions.from_dict({"temperature": "0.2", "top_k": "40"})
        assert opts.temperature == 0.2
        assert opts.top_k == 40

    @pytest.mark.parametrize("data", [
        {"temperature": "warm"}, {"max_output_tokens": 0}, {"max_output_tokens": -1},
        {"temperature": -0.5}, {"thinking": "sometimes"}, {"effort": "extreme"},
        {"top_k": True},
    ])
    def test_bad_values_are_skipped_not_raised(self, data, caplog):
        # A typo in a settings file must never stop a batch.
        with caplog.at_level(logging.WARNING, logger="idt_core.generation"):
            opts = GenerationOptions.from_dict(data)
        assert opts.is_automatic()
        assert "Ignoring generation setting" in caplog.text

    def test_unknown_keys_pass_through_as_extra(self):
        opts = GenerationOptions.from_dict({"num_ctx": 8192, "extra": {"seed": 1}})
        assert dict(opts.extra) == {"num_ctx": 8192, "seed": 1}


class TestMerge:
    def test_override_wins_only_where_set(self):
        base = GenerationOptions(thinking=THINKING_OFF, temperature=0.5)
        merged = base.merged(GenerationOptions(temperature=0.1))
        assert merged.thinking == THINKING_OFF
        assert merged.temperature == 0.1

    def test_zero_temperature_is_an_override(self):
        assert GenerationOptions(temperature=0.7).merged(
            GenerationOptions(temperature=0.0)).temperature == 0.0

    def test_extra_is_combined(self):
        merged = GenerationOptions(extra={"a": 1, "b": 1}).merged(
            GenerationOptions(extra={"b": 2}))
        assert dict(merged.extra) == {"a": 1, "b": 2}

    def test_merge_none(self):
        base = GenerationOptions(top_p=0.9)
        assert base.merged(None) is base

    def test_to_dict_lists_only_set_fields(self):
        assert GenerationOptions(thinking=THINKING_OFF).to_dict() == {"thinking": "off"}


def test_think_flag_round_trip():
    for mode in (THINKING_ON, THINKING_OFF, THINKING_AUTO):
        assert thinking_mode(think_flag(mode)) == mode
    assert think_flag(None) is None


class TestUserOptions:
    def test_reads_the_provider_section(self):
        config = {"generation": {"ollama": {"thinking": "on", "temperature": 0.3},
                                 "openai": {"effort": "low"}}}
        opts = user_options("ollama", config=config)
        assert opts.thinking == THINKING_ON and opts.temperature == 0.3

    def test_missing_section_is_automatic(self):
        assert user_options("ollama", config={}).is_automatic()
        assert user_options("ollama", config={"generation": "junk"}).is_automatic()

    def test_legacy_model_settings_are_not_read(self):
        # Tuned for 2025 models; num_predict 500 would cut today's descriptions.
        config = {"model_settings": {"temperature": 0.1, "num_predict": 600},
                  "prompt_model_settings": {"narrative": {"num_predict": 500}}}
        assert user_options("ollama", config=config).is_automatic()

    def test_shipped_config_is_automatic_and_descriptions_default_to_no_thinking(self):
        import json
        config = json.loads((_ROOT / "scripts" / "image_describer_config.json")
                            .read_text(encoding="utf-8"))
        opts = user_options("ollama", config=config)
        assert opts.is_automatic()
        # Thinking off comes from the provider's description defaults, not the file.
        provider = ollama_mod.OllamaProvider(model="m", options=opts)
        assert provider.options.thinking == THINKING_OFF
        assert provider.options.max_output_tokens is None


# --------------------------------------------------------------------------- #
# Ollama: resolve_think and request_options                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def caps(monkeypatch):
    """Set what /api/show reports: caps.value = list, or None for a failed probe."""
    holder = SimpleNamespace(value=["completion", "vision"])
    monkeypatch.setattr(ollama_mod, "model_capabilities",
                        lambda name, host=None, client=None: holder.value)
    return holder


class TestResolveThink:
    def test_on_is_passed_through_unprobed(self, caps):
        caps.value = ["completion"]
        assert ollama_mod.resolve_think(THINKING_ON, "m") is True

    def test_off_sent_only_to_thinking_models(self, caps):
        caps.value = ["completion", "vision", "thinking"]
        assert ollama_mod.resolve_think(THINKING_OFF, "m") is False
        caps.value = ["completion", "vision"]
        assert ollama_mod.resolve_think(THINKING_OFF, "m") is None

    def test_auto_separates_thinking_models(self, caps):
        caps.value = ["thinking"]
        assert ollama_mod.resolve_think(THINKING_AUTO, "m") is True
        assert ollama_mod.resolve_think(None, "m") is True
        caps.value = ["completion"]
        assert ollama_mod.resolve_think(THINKING_AUTO, "m") is None

    def test_failed_probe_fails_closed(self, caps):
        caps.value = None
        assert ollama_mod.resolve_think(THINKING_OFF, "m") is None
        assert ollama_mod.resolve_think(THINKING_AUTO, "m") is None

    def test_probe_exception_fails_closed(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("down")
        monkeypatch.setattr(ollama_mod, "model_capabilities", boom)
        assert ollama_mod.resolve_think(THINKING_AUTO, "m") is None


class TestRequestOptions:
    def test_automatic_sends_nothing(self):
        assert ollama_mod.request_options(GenerationOptions(), "m") == {}

    def test_fields_map_to_ollama_names(self):
        opts = GenerationOptions(temperature=0.1, top_p=0.9, top_k=40,
                                 repeat_penalty=1.1, max_output_tokens=800)
        assert ollama_mod.request_options(opts, "qwen3-vl:8b-instruct") == {
            "temperature": 0.1, "top_p": 0.9, "top_k": 40, "repeat_penalty": 1.1,
            "num_predict": 800}

    @pytest.mark.parametrize("name", ["kimi-k2.5:cloud", "gpt-oss:20b-cloud"])
    def test_no_num_predict_for_cloud_models(self, name):
        opts = GenerationOptions(max_output_tokens=800)
        assert "num_predict" not in ollama_mod.request_options(opts, name)

    def test_no_num_predict_while_thinking(self):
        opts = GenerationOptions(max_output_tokens=800)
        assert "num_predict" not in ollama_mod.request_options(opts, "m", think=True)
        assert ollama_mod.request_options(opts, "m", think=False)["num_predict"] == 800

    def test_extra_passes_through(self):
        opts = GenerationOptions(extra={"num_ctx": 8192})
        assert ollama_mod.request_options(opts, "m") == {"num_ctx": 8192}


# --------------------------------------------------------------------------- #
# Ollama: describe                                                             #
# --------------------------------------------------------------------------- #

def _response(content="", thinking="", done_reason="stop", prompt=100, out=50):
    return SimpleNamespace(
        message=SimpleNamespace(content=content, thinking=thinking),
        done_reason=done_reason, prompt_eval_count=prompt, eval_count=out)


class _ScriptedClient:
    """Stands in for ollama.Client; returns queued responses, records calls."""
    calls: list = []
    queue: list = []

    def __init__(self, host=None, **kwargs):
        self.kwargs = kwargs

    def chat(self, **kwargs):
        _ScriptedClient.calls.append(kwargs)
        return _ScriptedClient.queue.pop(0)


@pytest.fixture
def client(monkeypatch):
    import ollama
    _ScriptedClient.calls = []
    _ScriptedClient.queue = []
    monkeypatch.setattr(ollama, "Client", _ScriptedClient)
    ollama_mod._WARNED_IGNORED_THINK.clear()
    return _ScriptedClient


def _describe(options=None, model="qwen3-vl:8b"):
    provider = ollama_mod.OllamaProvider(model=model, options=options)
    return provider.describe(b"img", "image/jpeg", "Describe.")


class TestDescribe:
    def test_thinking_model_gets_think_false_by_default(self, client, caps):
        caps.value = ["completion", "vision", "thinking"]
        client.queue = [_response("A desk.")]
        result = _describe()
        assert client.calls[0]["think"] is False
        assert "options" not in client.calls[0]      # everything else automatic
        assert result.text == "A desk." and result.thinking_chars == 0

    def test_non_thinking_model_gets_no_think_field(self, client, caps):
        client.queue = [_response("A desk.")]
        _describe(model="qwen3-vl:8b-instruct")
        assert "think" not in client.calls[0]

    def test_user_settings_reach_the_request(self, client, caps):
        client.queue = [_response("A desk.")]
        _describe(GenerationOptions(temperature=0.2, max_output_tokens=900))
        assert client.calls[0]["options"] == {"temperature": 0.2, "num_predict": 900}

    def test_thinking_on_is_honoured_and_drops_the_cap(self, client, caps):
        client.queue = [_response("A desk.", thinking="hmm")]
        _describe(GenerationOptions(thinking=THINKING_ON, max_output_tokens=900))
        assert client.calls[0]["think"] is True
        assert "num_predict" not in client.calls[0].get("options", {})

    def test_empty_answer_with_thinking_is_retried_without_cap(self, client, caps, caplog):
        client.queue = [_response("", thinking="x" * 13000, out=2990),
                        _response("A desk.", out=300)]
        with caplog.at_level(logging.WARNING):
            result = _describe(GenerationOptions(max_output_tokens=600))
        assert len(client.calls) == 2
        assert client.calls[0]["options"]["num_predict"] == 600
        assert "num_predict" not in client.calls[1].get("options", {})
        assert result.text == "A desk."
        assert result.output_tokens == 3290           # both attempts counted
        assert "no description" in caplog.text

    def test_empty_answer_twice_raises_instead_of_saving_a_blank(self, client, caps):
        client.queue = [_response("", thinking="x"), _response("", thinking="y")]
        with pytest.raises(ollama_mod.EmptyDescriptionError, match="instruct"):
            _describe()

    def test_empty_answer_without_thinking_is_returned_for_the_caller(self, client, caps):
        # Not ours to judge: the callers already retry plain empty replies.
        client.queue = [_response("")]
        assert _describe().text == ""
        assert len(client.calls) == 1

    def test_ignored_think_false_is_logged_once_per_model(self, client, caps, caplog):
        caps.value = ["thinking", "vision"]
        client.queue = [_response("A.", thinking="t" * 50), _response("B.", thinking="t")]
        with caplog.at_level(logging.WARNING):
            _describe()
            _describe()
        assert caplog.text.count("kept thinking although thinking was turned off") == 1

    def test_inline_think_tags_never_reach_the_description(self, client, caps):
        client.queue = [_response("<think>let me look</think>\n\nA desk.")]
        result = _describe()
        assert result.text == "A desk."
        assert result.thinking_chars == len("let me look")

    def test_closing_tag_without_opening_tag(self, client, caps):
        # Templates that put <think> in the prompt reply "reasoning</think> answer".
        client.queue = [_response("let me look</think>\nA desk.")]
        result = _describe()
        assert result.text == "A desk."
        assert result.thinking_chars == len("let me look")

    def test_unclosed_think_tag_is_all_reasoning(self, client, caps):
        # Cut off mid-thought: nothing in it is a description, so it is retried.
        client.queue = [_response("<think>still looking at the", done_reason="length"),
                        _response("A desk.")]
        assert _describe().text == "A desk."
        assert len(client.calls) == 2

    def test_a_literal_tag_inside_a_description_is_left_alone(self, client, caps):
        text = "A sign reading <think> and </think> hangs on the wall."
        client.queue = [_response(text)]
        assert _describe().text == text

    def test_truncation_is_reported(self, client, caps, caplog):
        client.queue = [_response("A desk with a", done_reason="length")]
        with caplog.at_level(logging.WARNING):
            result = _describe()
        assert result.truncated is True
        assert "cut off" in caplog.text

    def test_requests_carry_a_timeout(self, client, caps):
        seen = {}

        class Recording(_ScriptedClient):
            def __init__(self, host=None, **kwargs):
                super().__init__(host, **kwargs)
                seen.update(kwargs)

        import ollama
        ollama.Client = Recording  # monkeypatch fixture restores it
        client.queue = [_response("A desk.")]
        _describe()
        assert seen["timeout"] == ollama_mod.OllamaProvider.DESCRIBE_TIMEOUT_SECONDS


# --------------------------------------------------------------------------- #
# Chat shares the policy                                                       #
# --------------------------------------------------------------------------- #

class TestChatUsesTheSamePolicy:
    def _request(self, think):
        from idt_core.providers.base import ChatRequest
        return ChatRequest(messages=[], model="m", think=think)

    def test_chat_auto_still_turns_separation_on(self, caps):
        from idt_core.chat.providers import OllamaChatProvider
        caps.value = ["thinking"]
        assert OllamaChatProvider("m")._effective_think(self._request(None)) is True

    def test_chat_off_gated_on_capability(self, caps):
        from idt_core.chat.providers import OllamaChatProvider
        caps.value = ["completion"]
        assert OllamaChatProvider("m")._effective_think(self._request(False)) is None


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

class TestCli:
    def _args(self, **kw):
        base = {"thinking": None, "temperature": None, "max_tokens": None}
        base.update(kw)
        return SimpleNamespace(**base)

    def test_flags_override_saved_settings(self, monkeypatch):
        from cli import main as cli_main
        gen = sys.modules["idt_core.generation"]
        monkeypatch.setattr(gen, "_load_config", lambda: {
            "generation": {"ollama": {"thinking": "on", "temperature": 0.5}}})
        opts = cli_main._generation_options(self._args(thinking="off"), "ollama")
        assert opts.thinking == THINKING_OFF
        assert opts.temperature == 0.5

    def test_claude_settings_use_the_public_name(self, monkeypatch):
        from cli import main as cli_main
        gen = sys.modules["idt_core.generation"]
        monkeypatch.setattr(gen, "_load_config", lambda: {
            "generation": {"claude": {"effort": "low"}}})
        assert cli_main._generation_options(self._args(), "anthropic").effort == "low"

    def test_parser_accepts_the_flags(self):
        from cli import main as cli_main
        args = cli_main.build_parser().parse_args(
            ["describe", "x", "--no-think", "--max-tokens", "800", "--temperature", "0.2"])
        assert (args.thinking, args.max_tokens, args.temperature) == ("off", 800, 0.2)

    @pytest.mark.parametrize("flags", [
        ["--max-tokens", "0"], ["--max-tokens", "-5"], ["--max-tokens", "lots"],
        ["--temperature", "-1"], ["--temperature", "warm"],
    ])
    def test_bad_flag_values_fail_at_the_prompt(self, flags, capsys):
        # Not silently dropped: the user asked for something they would not get.
        from cli import main as cli_main
        with pytest.raises(SystemExit):
            cli_main.build_parser().parse_args(["describe", "x", *flags])
        assert "error" in capsys.readouterr().err

    def test_zero_temperature_is_allowed(self):
        from cli import main as cli_main
        args = cli_main.build_parser().parse_args(["describe", "x", "--temperature", "0"])
        assert args.temperature == 0.0

    def test_every_provider_receives_the_settings(self, monkeypatch):
        from cli import main as cli_main
        import idt_core.providers.claude as claude_mod
        import idt_core.providers.openai_provider as oai
        seen = {}

        def capture(name):
            def init(self, model=None, options=None, **kw):
                seen[name] = options
            return init

        monkeypatch.setattr(oai.OpenAIProvider, "__init__", capture("openai"))
        monkeypatch.setattr(claude_mod.ClaudeProvider, "__init__", capture("claude"))
        opts = GenerationOptions(effort="low")
        cli_main._make_provider("openai", "gpt-5.2", "http://x", options=opts)
        cli_main._make_provider("anthropic", "claude-opus-5-5", "http://x", options=opts)
        assert seen == {"openai": opts, "claude": opts}

    def test_windows_ai_note_says_settings_are_ignored(self, capsys, monkeypatch):
        from cli import main as cli_main
        monkeypatch.setattr(cli_main.sys, "exit", lambda code=0: None)
        try:
            cli_main._make_provider("windows-ai", None, "http://x",
                                    options=GenerationOptions(thinking=THINKING_OFF))
        except Exception:
            pass   # no Windows AI on the test machine; only the note matters
        note = capsys.readouterr().err.splitlines()[0]
        assert note == "Note: Windows-AI takes no generation settings; they were ignored."

    def test_no_note_for_providers_that_take_settings(self, capsys, monkeypatch):
        from cli import main as cli_main
        import idt_core.providers.openai_provider as oai
        monkeypatch.setattr(oai.OpenAIProvider, "__init__",
                            lambda self, model=None, options=None: None)
        cli_main._make_provider("openai", "gpt-5.2", "http://x",
                                options=GenerationOptions(temperature=0.2))
        assert "Note:" not in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# ImageDescriber goes through idt_core                                         #
# --------------------------------------------------------------------------- #

class TestImageDescriberRouting:
    def test_describe_image_uses_the_core_provider(self, client, caps, tmp_path, monkeypatch):
        sys.path.insert(0, str(_ROOT / "imagedescriber"))
        gen = sys.modules["idt_core.generation"]
        monkeypatch.setattr(gen, "_load_config", lambda: {
            "generation": {"ollama": {"temperature": 0.3}}})
        from PIL import Image
        img = tmp_path / "a.jpg"
        Image.new("RGB", (8, 8), "red").save(img)

        import ai_providers
        GuiOllama = ai_providers.OllamaProvider
        caps.value = ["thinking", "vision"]
        client.queue = [_response("A red square.", thinking="t" * 10, prompt=7, out=9)]
        gui = GuiOllama()
        text = gui.describe_image(str(img), "Describe.", "qwen3-vl:8b")

        assert text == "A red square."
        call = client.calls[0]
        assert call["think"] is False
        assert call["options"] == {"temperature": 0.3}
        assert gui.last_usage["thinking_chars"] == 10
        assert gui.last_usage["completion_tokens"] == 9
        assert gui.last_usage["finish_reason"] is None

    def test_http_errors_keep_their_status_for_retry(self, monkeypatch, caps, tmp_path):
        sys.path.insert(0, str(_ROOT / "imagedescriber"))
        import ollama
        from PIL import Image
        img = tmp_path / "a.jpg"
        Image.new("RGB", (8, 8)).save(img)

        class Failing(_ScriptedClient):
            def chat(self, **kwargs):
                raise ollama.ResponseError("model not found", 404)

        monkeypatch.setattr(ollama, "Client", Failing)
        import ai_providers
        monkeypatch.setattr(ai_providers.time, "sleep", lambda s: None, raising=False)
        with pytest.raises(ai_providers.ProviderError) as info:
            ai_providers.OllamaProvider().describe_image(str(img), "x", "nope")
        assert info.value.status_code == 404


def _gui_image(tmp_path):
    sys.path.insert(0, str(_ROOT / "imagedescriber"))
    from PIL import Image
    img = tmp_path / "a.jpg"
    Image.new("RGB", (8, 8)).save(img)
    return str(img)


class TestImageDescriberRetries:
    """What each failure costs: a retried 30-minute request is a long wait."""

    def test_reasoning_without_description_is_not_retried_again(self, client, caps,
                                                                tmp_path, monkeypatch):
        import ai_providers
        monkeypatch.setattr(ai_providers.time, "sleep", lambda s: None)
        img = _gui_image(tmp_path)
        client.queue = [_response("", thinking="x")] * 8
        with pytest.raises(ai_providers.ProviderError):
            ai_providers.OllamaProvider().describe_image(img, "x", "qwen3-vl:2b")
        # The core provider's own single retry, and no decorator retries on top.
        assert len(client.calls) == 2

    def test_a_full_length_timeout_is_not_retried(self, caps, tmp_path, monkeypatch):
        import httpx
        import ollama
        import ai_providers
        monkeypatch.setattr(ai_providers.time, "sleep", lambda s: None)
        img = _gui_image(tmp_path)
        calls = []

        class Hanging(_ScriptedClient):
            def chat(self, **kwargs):
                calls.append(kwargs)
                raise httpx.ReadTimeout("timed out")

        monkeypatch.setattr(ollama, "Client", Hanging)
        with pytest.raises(ai_providers.ProviderError) as info:
            ai_providers.OllamaProvider().describe_image(img, "x", "m")
        assert len(calls) == 1
        # Still transient for the batch's stop rules; just not repeated here.
        assert info.value.kind == ai_providers.ErrorKind.TIMEOUT
        assert info.value.is_retryable

    def test_cloud_provider_reports_usage(self, client, caps, tmp_path):
        import ai_providers
        img = _gui_image(tmp_path)
        client.queue = [_response("A dock.", thinking="t" * 12, prompt=3, out=4)]
        cloud = ai_providers.OllamaCloudProvider()
        assert cloud.describe_image(img, "x", "gemma4:31b-cloud") == "A dock."
        assert cloud.last_usage["completion_tokens"] == 4
        assert cloud.last_usage["thinking_chars"] == 12


class TestRunLog:
    def test_provider_notices_are_written_while_a_run_is_open(self, tmp_path):
        from idt_core.logger import close_run_log, open_run_log
        source = logging.getLogger("idt_core.providers.ollama")
        log = open_run_log(tmp_path)
        source.info("Not sending num_predict to cloud model x")
        source.warning("m kept thinking although thinking was turned off")
        close_run_log(log)
        source.info("after the run")
        text = "".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.log"))
        assert "Not sending num_predict to cloud model x" in text
        assert "kept thinking" in text
        assert "after the run" not in text
        assert not logging.getLogger("idt_core.providers").handlers or all(
            getattr(h, "_idt_console", False)
            for h in logging.getLogger("idt_core.providers").handlers)
