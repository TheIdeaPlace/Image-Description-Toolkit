"""
Claude chat with Thinking On on a model without adaptive thinking (#441).

Claude Haiku 4.5 refuses {"type": "adaptive"} ("adaptive thinking is not
supported on this model", the real API's words, 11/16/2026) and thinks with a
token budget. The chat stream loop switches to a budget, remembers that for the
model, and drops thinking only if the budget is refused too.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from idt_core import generation
from idt_core.chat.messages import ChatMessage
from idt_core.chat.providers import ClaudeChatProvider
from idt_core.providers.base import ChatRequest

REFUSAL = ("Error code: 400 - {'type': 'error', 'error': {'type': "
           "'invalid_request_error', 'message': 'adaptive thinking is not "
           "supported on this model'}}")


class BadRequest(Exception):
    status_code = 400


def _fake_anthropic(monkeypatch, outcomes):
    """Each stream() call takes the next outcome: an exception, or answer text."""
    calls = []

    class _Stream:
        def __init__(self, text):
            self._text = text

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        @property
        def text_stream(self):
            return iter([self._text])

        def get_final_message(self):
            return SimpleNamespace(usage=SimpleNamespace(input_tokens=5, output_tokens=7),
                                   stop_reason="end_turn")

    class _Messages:
        def stream(self, **kwargs):
            calls.append(kwargs)
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return _Stream(outcome)

    class Anthropic:
        def __init__(self, *a, **k):
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Anthropic))
    return calls


def _turn(model, max_tokens=4096):
    provider = ClaudeChatProvider(model, api_key="sk-ant-test-not-real")
    request = ChatRequest(messages=[ChatMessage(role="user", content="hi")], model=model,
                          think=True, max_output_tokens=max_tokens)
    return provider, request


def test_adaptive_refused_then_a_budget_and_it_is_remembered(monkeypatch):
    model = "claude-haiku-4-5-chat-budget-test"
    calls = _fake_anthropic(monkeypatch, [BadRequest(REFUSAL), "Hello.", "Again."])
    provider, request = _turn(model)
    text = "".join(getattr(e, "text", "") for e in provider.chat(request))
    assert text == "Hello."
    assert calls[0]["thinking"] == {"type": "adaptive"}
    assert calls[1]["thinking"] == {"type": "enabled", "budget_tokens": 2048}
    # The next turn goes straight to a budget.
    list(provider.chat(request))
    assert calls[2]["thinking"] == {"type": "enabled", "budget_tokens": 2048}
    generation._ACCEPTED.pop(("claude", model, "thinking"), None)


def test_a_refused_budget_too_drops_thinking(monkeypatch):
    model = "claude-old-chat-no-thinking-test"
    calls = _fake_anthropic(monkeypatch, [BadRequest(REFUSAL),
                                          BadRequest("thinking is not supported on this model"),
                                          "Hello."])
    provider, request = _turn(model)
    text = "".join(getattr(e, "text", "") for e in provider.chat(request))
    assert text == "Hello."
    assert "thinking" not in calls[2]
    generation._REJECTED.discard(("claude", model, "thinking"))


def test_no_room_for_a_budget_drops_thinking(monkeypatch):
    model = "claude-haiku-4-5-chat-small-limit-test"
    calls = _fake_anthropic(monkeypatch, [BadRequest(REFUSAL), "Hello."])
    provider, request = _turn(model, max_tokens=1100)
    list(provider.chat(request))
    assert "thinking" not in calls[1]
    generation._REJECTED.discard(("claude", model, "thinking"))
