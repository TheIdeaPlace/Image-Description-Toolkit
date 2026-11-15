"""
Generation settings in the apps (issue #392, part 3).

* The Configure dialog's Generation tab writes exactly what idt_core reads.
* Chat's Thinking choice reaches Claude, OpenAI and Claude Code, not just Ollama.
* Describe pickers flag thinking models and point to the -instruct edition.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from idt_core.generation import (  # noqa: E402
    CHAT_THINKING_CHOICES, THINKING_AUTO, THINKING_OFF, user_options,
)


def _require_wx():
    """The dialog modules import wx. Skip without it -- the macOS suite job
    has none -- unless IDT_REQUIRE_WX=1, where a skip would hide the tests
    (the convention from test_gui_smoke.py, issue #230)."""
    import os
    try:
        import wx  # noqa: F401
    except ImportError as exc:
        if os.environ.get("IDT_REQUIRE_WX") == "1":
            raise RuntimeError(f"IDT_REQUIRE_WX=1 but wxPython is missing: {exc}") from exc
        pytest.skip("wxPython is not installed")


@pytest.fixture
def cfg(monkeypatch):
    _require_wx()
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    import configure_dialog
    return configure_dialog


# --------------------------------------------------------------------------- #
# Configure dialog                                                             #
# --------------------------------------------------------------------------- #

class TestGenerationTab:
    def test_mac_only_providers_are_listed_only_on_a_mac(self, cfg):
        windows = set(cfg.generation_settings_metadata(include_mac=False))
        mac = set(cfg.generation_settings_metadata(include_mac=True))
        assert not [n for n in windows if n.startswith(("Apple", "MLX"))]
        assert mac - windows == {"Apple Intelligence temperature",
                                 "Apple Intelligence output limit", "MLX output limit"}

    def test_each_provider_offers_only_what_it_takes(self, cfg):
        names = set(cfg.generation_settings_metadata(include_mac=True))
        assert "Claude temperature" not in names            # the API rejects it
        assert "Apple Intelligence thinking" not in names   # nothing to control
        assert "Ollama effort" not in names
        assert {"Ollama thinking", "OpenAI effort", "Claude effort", "MLX output limit",
                "Claude Code thinking", "Apple Intelligence temperature"} <= names

    def test_names_read_well_aloud(self, cfg):
        # "top_p" is read as "top underscore p".
        assert not [n for n in cfg.generation_settings_metadata() if "_" in n]

    def test_every_setting_can_be_automatic(self, cfg):
        for name, info in cfg.generation_settings_metadata(include_mac=True).items():
            assert info["type"] in cfg._AUTO_TYPES, name
            assert cfg._display_value(info, None).startswith("Automatic"), name

    def test_what_the_dialog_writes_is_what_the_providers_read(self, cfg):
        """The point of the tab. Set every entry through the dialog's own
        set_setting_value, and the providers must see each value."""
        metadata = cfg.generation_settings_metadata(include_mac=True)
        config: dict = {}
        dialog = SimpleNamespace(configs={"image_describer": config})
        samples = {"choice_or_auto": None, "float_or_auto": 0.5, "int_or_auto": 800}
        for info in metadata.values():
            value = samples[info["type"]]
            if info["type"] == "choice_or_auto":
                value = info["choices"][1]          # the first real choice
            cfg.ConfigureDialog.set_setting_value(dialog, info, value)

        ollama = user_options("ollama", config=config)
        assert ollama.thinking == THINKING_OFF
        assert (ollama.temperature, ollama.top_p, ollama.repeat_penalty) == (0.5, 0.5, 0.5)
        assert (ollama.top_k, ollama.max_output_tokens) == (800, 800)
        openai = user_options("openai", config=config)
        assert (openai.thinking, openai.effort, openai.temperature) == (THINKING_OFF, "minimal", 0.5)
        claude = user_options("claude", config=config)
        assert (claude.effort, claude.max_output_tokens) == ("low", 800)
        assert user_options("claude-code", config=config).thinking == THINKING_OFF
        assert user_options("apple", config=config).temperature == 0.5
        assert user_options("mlx", config=config).max_output_tokens == 800
        assert not user_options("ollama", config=config).extra   # nothing unknown written

    def test_choosing_automatic_through_the_dialog_clears_the_setting(self, cfg):
        info = cfg.generation_settings_metadata()["Ollama temperature"]
        config = {"generation": {"ollama": {"temperature": 0.2}}}
        dialog = SimpleNamespace(configs={"image_describer": config})
        cfg.ConfigureDialog.set_setting_value(dialog, info, None)
        assert config == {}
        assert cfg.ConfigureDialog.get_setting_value(dialog, info) is None

    def test_hand_edited_values_are_shown_and_kept(self, cfg):
        """Spellings idt_core accepts must not be misread, or dropped on OK."""
        config = {"generation": {"ollama": {"thinking": False, "num_predict": 300,
                                            "num_ctx": 8192},
                                 "openai": {"think": "OFF"},
                                 "claude": {}}}
        cfg.normalise_generation_section(config)
        assert config["generation"] == {
            "ollama": {"thinking": "off", "max_output_tokens": 300, "extra": {"num_ctx": 8192}},
            "openai": {"thinking": "off"},
        }
        dialog = SimpleNamespace(configs={"image_describer": config})
        meta = cfg.generation_settings_metadata()
        assert cfg._display_value(meta["Ollama output limit"],
                                  cfg.ConfigureDialog.get_setting_value(
                                      dialog, meta["Ollama output limit"])) == 300
        # And idt_core still reads the normalised form the same way.
        opts = user_options("ollama", config=config)
        assert (opts.thinking, opts.max_output_tokens, dict(opts.extra)) == \
            (THINKING_OFF, 300, {"num_ctx": 8192})

    def test_normalising_an_empty_section_removes_it(self, cfg):
        config = {"generation": {"ollama": {"temperature": None}}, "x": 1}
        cfg.normalise_generation_section(config)
        assert config == {"x": 1}

    def test_ollama_model_default_is_a_choice(self, cfg):
        info = cfg.generation_settings_metadata()["Ollama thinking"]
        assert "auto" in info["choices"]
        config = {"generation": {"ollama": {"thinking": "auto"}}}
        assert user_options("ollama", config=config).thinking == THINKING_AUTO

    @pytest.mark.parametrize("text, expected", [
        ("", (None, None)), ("  ", (None, None)), ("automatic", (None, None)),
        ("0.2", (0.2, None)), ("2", (2.0, None)),
    ])
    def test_float_entry(self, cfg, text, expected):
        info = cfg.generation_settings_metadata()["Ollama temperature"]
        assert cfg._validate_auto_number(info, text) == expected

    @pytest.mark.parametrize("text", ["warm", "-1", "2.5"])
    def test_bad_float_entry_says_what_to_do(self, cfg, text):
        info = cfg.generation_settings_metadata()["Ollama temperature"]
        value, error = cfg._validate_auto_number(info, text)
        assert value is None and "leave it empty for Automatic" in error

    def test_int_entry(self, cfg):
        info = cfg.generation_settings_metadata()["Ollama output limit"]
        assert cfg._validate_auto_number(info, "800") == (800, None)
        assert "whole number" in cfg._validate_auto_number(info, "8.5")[1]
        assert cfg._validate_auto_number(info, "10")[1]    # below the range

    def test_automatic_removes_the_key_and_empty_sections(self, cfg):
        config = {"generation": {"ollama": {"temperature": 0.2}, "openai": {"effort": "low"}},
                  "default_provider": "ollama"}
        cfg._remove_path(config, ["generation", "ollama", "temperature"])
        assert config["generation"] == {"openai": {"effort": "low"}}
        cfg._remove_path(config, ["generation", "openai", "effort"])
        assert "generation" not in config
        assert config == {"default_provider": "ollama"}
        cfg._remove_path(config, ["generation", "claude", "effort"])   # absent: no error

    def test_dead_model_settings_entries_are_gone(self, cfg):
        source = (_ROOT / "imagedescriber" / "configure_dialog.py").read_text(encoding="utf-8")
        assert '["model_settings",' not in source


def test_shipped_config_has_no_legacy_settings():
    config = json.loads((_ROOT / "scripts" / "image_describer_config.json")
                        .read_text(encoding="utf-8"))
    assert "model_settings" not in config
    assert "prompt_model_settings" not in config


# --------------------------------------------------------------------------- #
# Chat                                                                         #
# --------------------------------------------------------------------------- #

def test_thinking_menu_choices():
    assert [value for value, _label, _status in CHAT_THINKING_CHOICES] == [None, True, False]
    labels = [label for _value, label, _status in CHAT_THINKING_CHOICES]
    assert all(label.count("&") == 1 for label in labels)
    assert len({label[label.index("&") + 1].lower() for label in labels}) == 3


def _request(think, model="m"):
    from idt_core.providers.base import ChatRequest
    return ChatRequest(messages=[], model=model, think=think)


class TestClaudeChat:
    def test_mapping(self):
        from idt_core.chat.providers import ClaudeChatProvider
        provider = ClaudeChatProvider("claude-opus-5-5", api_key="k")
        on = provider._request_kwargs(_request(True), [], "")
        off = provider._request_kwargs(_request(False), [], "")
        auto = provider._request_kwargs(_request(None), [], "")
        assert on["thinking"] == {"type": "adaptive"}
        assert off["output_config"] == {"effort": "low"} and "thinking" not in off
        assert "thinking" not in auto and "output_config" not in auto

    def test_rejected_effort_is_retried_without(self, monkeypatch):
        import anthropic

        from idt_core.chat.providers import ClaudeChatProvider

        class BadRequest(Exception):
            status_code = 400

        calls = []

        class Stream:
            text_stream = iter(["Hello"])

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1),
                                       stop_reason="end_turn")

        class FakeMessages:
            def stream(self, **kw):
                calls.append(kw)
                if "output_config" in kw:
                    raise BadRequest("output_config.effort is not supported on this model")
                return Stream()

        class FakeClient:
            def __init__(self, *a, **k):
                self.messages = FakeMessages()

        from idt_core import generation
        generation._REJECTED.clear()
        monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
        provider = ClaudeChatProvider("claude-haiku-4-5", api_key="k")
        out = list(provider.chat(_request(False, "claude-haiku-4-5")))
        assert [type(o).__name__ for o in out] == ["ChatDelta", "ChatUsage"]
        assert "output_config" in calls[0] and "output_config" not in calls[1]
        # Remembered: the next turn does not start with a failed request.
        Stream.text_stream = iter(["Again"])
        list(provider.chat(_request(False, "claude-haiku-4-5")))
        assert len(calls) == 3 and "output_config" not in calls[2]
        generation._REJECTED.clear()

    def test_an_error_after_text_started_is_raised_not_retried(self, monkeypatch):
        import anthropic

        from idt_core.chat.providers import ClaudeChatProvider

        class BadRequest(Exception):
            status_code = 400

        calls = []

        class Stream:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            @property
            def text_stream(self):
                yield "Partial"
                raise BadRequest("effort exploded mid-stream")

        class FakeClient:
            def __init__(self, *a, **k):
                self.messages = SimpleNamespace(
                    stream=lambda **kw: calls.append(kw) or Stream())

        monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
        gen = ClaudeChatProvider("m", api_key="k").chat(_request(False))
        assert next(gen).text == "Partial"
        with pytest.raises(BadRequest):
            next(gen)
        assert len(calls) == 1

    def test_server_errors_are_not_retried(self, monkeypatch):
        import anthropic

        from idt_core.chat.providers import ClaudeChatProvider

        class ServerError(Exception):
            status_code = 500

        calls = []

        def stream(**kw):
            calls.append(kw)
            raise ServerError("output_config overloaded")

        monkeypatch.setattr(anthropic, "Anthropic",
                            lambda *a, **k: SimpleNamespace(messages=SimpleNamespace(stream=stream)))
        with pytest.raises(ServerError):
            list(ClaudeChatProvider("m", api_key="k").chat(_request(False)))
        assert len(calls) == 1


def test_openai_chat_thinking_off_is_low_effort_on_reasoning_models(monkeypatch):
    import openai

    from idt_core.chat.providers import OpenAIChatProvider

    sent = []

    class FakeOpenAI:
        def __init__(self, *a, **k):
            self.chat = SimpleNamespace(completions=SimpleNamespace(
                create=lambda **kw: sent.append(kw) or iter([])))

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    for model in ("gpt-5.2", "o3", "gpt-4o"):
        list(OpenAIChatProvider(model, api_key="k").chat(_request(False, model)))
    # gpt-5.2 defaults to "none": "low" would make Off reason more than Automatic.
    assert sent[0]["reasoning_effort"] == "none"
    assert sent[1]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in sent[2]


def test_claude_code_chat_thinking_off_is_low_effort(monkeypatch):
    from idt_core.chat import claude_code as cc_chat

    seen = {}

    def fake_run(blocks, model, system, **kw):
        seen.update(kw)
        yield ("result", {"result": "hi", "is_error": False, "usage": {}})

    monkeypatch.setattr(cc_chat, "find_claude", lambda: "claude")
    monkeypatch.setattr(cc_chat, "check_subscription", lambda c: None)
    monkeypatch.setattr(cc_chat, "run_claude", fake_run)
    monkeypatch.setattr(cc_chat, "format_for_claude_code",
                        lambda messages, system: ("", [{"type": "text", "text": "hi"}]))
    provider = cc_chat.ClaudeCodeChatProvider("haiku")
    list(provider.chat(_request(False)))
    assert seen["effort"] == "low"
    list(provider.chat(_request(None)))
    assert seen["effort"] is None


# --------------------------------------------------------------------------- #
# Pickers                                                                      #
# --------------------------------------------------------------------------- #

@pytest.fixture
def caps(monkeypatch):
    from idt_core.providers import ollama as ollama_mod
    table = {"qwen3-vl:8b": ["completion", "vision", "thinking"],
             "qwen3-vl:8b-instruct": ["completion", "vision"]}
    monkeypatch.setattr(ollama_mod, "model_capabilities",
                        lambda name, host=None, client=None: table.get(name))
    return ollama_mod


def test_picker_label_flags_thinking_models(caps):
    assert caps.picker_label("qwen3-vl:8b") == "qwen3-vl:8b (thinks, slower)"
    assert caps.picker_label("qwen3-vl:8b-instruct") == "qwen3-vl:8b-instruct"
    assert caps.picker_label("unknown:1b") == "unknown:1b"     # probe failed: no flag


@pytest.mark.parametrize("name, installed, expected", [
    ("qwen3-vl:8b", ["qwen3-vl:8b", "qwen3-vl:8b-instruct"], "qwen3-vl:8b-instruct"),
    ("qwen3-vl:32b-thinking", ["qwen3-vl:32b-instruct"], "qwen3-vl:32b-instruct"),
    ("qwen3-vl:8b", ["qwen3-vl:8b"], None),
    ("qwen3-vl", ["qwen3-vl:latest-instruct"], "qwen3-vl:latest-instruct"),
    ("qwen3-vl:8b-instruct", ["qwen3-vl:8b-instruct"], None),
])
def test_instruct_alternative(name, installed, expected):
    from idt_core.providers.ollama import instruct_alternative
    assert instruct_alternative(name, installed) == expected


def test_thinking_hint(caps):
    hint = caps.thinking_hint("qwen3-vl:8b", ["qwen3-vl:8b-instruct"])
    assert "thinking model" in hint and "qwen3-vl:8b-instruct is installed" in hint
    assert "'-instruct' tag" in caps.thinking_hint("qwen3-vl:8b", [])
    assert caps.thinking_hint("qwen3-vl:8b-instruct", []) == ""


def test_pickers_make_no_requests(monkeypatch):
    """They run on the UI thread on every arrow press; one localhost request
    measured over 2 seconds. Only the cache from the listing probe is read."""
    _require_wx()
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    import ai_providers
    import dialogs_wx
    from idt_core.providers import ollama as ollama_mod

    def no_network(*a, **k):
        raise AssertionError("a picker made a network request")

    monkeypatch.setattr(ollama_mod, "model_capabilities", no_network)
    monkeypatch.setattr(ai_providers, "get_available_providers", no_network)
    monkeypatch.setattr(ai_providers.requests, "post", no_network)
    monkeypatch.setattr(ai_providers.requests, "get", no_network)
    monkeypatch.setattr(ai_providers._ollama_provider, "_thinking_cache",
                        {"qwen3-vl:8b": True, "qwen3-vl:8b-instruct": False})

    class Combo:
        items = []

        def Append(self, label, data=None):
            self.items.append((label, data))

    combo = Combo()
    dialogs_wx._append_ollama_models(combo, ["qwen3-vl:8b", "qwen3-vl:8b-instruct", "new:1b"])
    assert combo.items[0] == ("new:1b", "new:1b")              # unknown: unflagged, no probe
    assert combo.items[1] == ("qwen3-vl:8b (thinks, slower)", "qwen3-vl:8b")
    text = dialogs_wx._get_model_description_text(
        "ollama", "qwen3-vl:8b", ["qwen3-vl:8b", "qwen3-vl:8b-instruct"])
    assert "qwen3-vl:8b-instruct is installed" in text


def test_listing_probe_fills_the_thinking_cache(monkeypatch):
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    import ai_providers

    class Resp:
        status_code = 200

        def json(self):
            return {"capabilities": ["completion", "vision", "thinking"]}

    monkeypatch.setattr(ai_providers.requests, "post", lambda *a, **k: Resp())
    provider = ai_providers.OllamaProvider()
    assert provider._model_has_vision("qwen3-vl:8b") is True
    assert provider.known_thinking_model("qwen3-vl:8b") is True
    assert provider.known_thinking_model("never-probed") is False


def test_describe_picker_keeps_the_model_name_as_data(caps, monkeypatch):
    _require_wx()
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    import ai_providers
    import dialogs_wx
    monkeypatch.setattr(ai_providers._ollama_provider, "_thinking_cache",
                        {"qwen3-vl:8b": True})

    class Combo:
        def __init__(self):
            self.items = []
            self.selection = None

        def Append(self, label, data=None):
            self.items.append((label, data))

        def GetCount(self):
            return len(self.items)

        def GetClientData(self, i):
            return self.items[i][1]

        def SetSelection(self, i):
            self.selection = i

    combo = Combo()
    dialogs_wx._append_ollama_models(combo, ["qwen3-vl:8b-instruct", "qwen3-vl:8b"])
    assert combo.items == [("qwen3-vl:8b (thinks, slower)", "qwen3-vl:8b"),
                           ("qwen3-vl:8b-instruct", "qwen3-vl:8b-instruct")]
    assert dialogs_wx._select_by_data(combo, "qwen3-vl:8b-instruct") and combo.selection == 1
