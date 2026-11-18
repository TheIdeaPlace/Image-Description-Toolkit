"""Test Key (Configure > API Keys): idt_core.key_check, without wx or a network.

The SDK clients are stand-ins; their errors carry the same attributes the real
SDK errors do (status_code, body, message), so every failure mapping is checked
without spending anything. A real run against live keys is a manual check
(see the PR), because it costs money.
"""
from __future__ import annotations

import io
import urllib.error
from types import SimpleNamespace

import pytest

from idt_core import key_check

FAKE_KEY = "sk-ant-api03-" + "Q" * 40


# --------------------------------------------------------------------------- #
# Stand-ins                                                                    #
# --------------------------------------------------------------------------- #

class APIStatusError(Exception):
    """Shaped like anthropic/openai APIStatusError."""

    def __init__(self, status, message, body=None):
        # The real SDKs' str() is "Error code: 400 - {body}", message included.
        super().__init__(f"Error code: {status} - {body or message!r}")
        self.status_code = status
        self.message = message
        self.body = body


class APIConnectionError(Exception):
    pass


class APITimeoutError(APIConnectionError):
    pass


class _Recorder:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def create(self, **params):
        self.calls.append(params)
        if self.error is not None:
            raise self.error
        return self.response


def claude_client(response=None, error=None):
    recorder = _Recorder(response, error)
    client = SimpleNamespace(messages=recorder)
    return (lambda key: client), recorder


def openai_client(response=None, error=None):
    recorder = _Recorder(response, error)
    client = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    return (lambda key: client), recorder


def claude_response(input_tokens=14, output_tokens=4):
    return SimpleNamespace(usage=SimpleNamespace(input_tokens=input_tokens,
                                                 output_tokens=output_tokens))


def openai_response(prompt=12, completion=20):
    return SimpleNamespace(usage=SimpleNamespace(prompt_tokens=prompt,
                                                 completion_tokens=completion))


def anthropic_error(status, message, type_="error", **extra):
    return APIStatusError(status, message,
                          {"type": "error", "error": {"type": type_, "message": message, **extra}})


def openai_error(status, message, code=None):
    return APIStatusError(status, message, {"message": message, "type": "x", "code": code})


def run(provider, factory, key=FAKE_KEY):
    return key_check.test_api_key(provider, api_key=key, client_factory=factory)


# --------------------------------------------------------------------------- #
# Success and cost                                                             #
# --------------------------------------------------------------------------- #

def test_claude_works_and_reports_the_cost():
    from idt_core.pricing import estimate, format_dollars

    factory, rec = claude_client(claude_response(14, 4))
    result = run("claude", factory)
    assert result.ok
    expected, _ = estimate("claude", result.model, 14, 4)
    assert result.cost == pytest.approx(expected)
    assert result.message == f"Your Claude key works. That test cost {format_dollars(expected)}."
    sent = rec.calls[0]
    assert sent["model"] == key_check.cheapest_model("claude")
    assert sent["max_tokens"] <= 32
    assert sent["messages"][0]["content"] == key_check.PROMPT


def test_claude_tests_on_its_cheapest_priced_model():
    assert key_check.cheapest_model("claude") == "claude-haiku-5-5"


def test_openai_works_with_little_reasoning_and_completion_tokens():
    factory, rec = openai_client(openai_response(12, 20))
    result = run("openai", factory)
    assert result.ok and result.cost and result.cost > 0
    sent = rec.calls[0]
    assert "max_tokens" not in sent, "reasoning models reject max_tokens"
    assert sent["max_completion_tokens"] >= 32
    from idt_core.providers.openai_provider import is_reasoning_model, lowest_effort
    if is_reasoning_model(sent["model"]):
        assert sent["reasoning_effort"] == lowest_effort(sent["model"])


def test_openai_model_is_the_price_tables_cheapest():
    from idt_core.pricing import KEPT_FOR_OLD_WORKSPACES, PRICES

    model = key_check.cheapest_model("openai")
    table = PRICES["openai"]
    assert model in table and model not in KEPT_FOR_OLD_WORKSPACES
    assert all(table[model].input + table[model].output <= p.input + p.output
               for m, p in table.items() if m not in KEPT_FOR_OLD_WORKSPACES)


def test_unpriced_model_still_works_with_cost_unknown(monkeypatch):
    monkeypatch.setattr(key_check, "cheapest_model", lambda provider: "claude-unpriced-9")
    factory, _ = claude_client(claude_response())
    result = run("claude", factory)
    assert result.ok and result.cost is None
    assert "isn't known" in result.message


def test_openai_rejected_effort_is_retried_not_reported(monkeypatch):
    """A model that rejects the lowest effort is retried (send_with_fallback),
    so the test doesn't fail on a parameter rather than the key."""
    from idt_core import generation

    # send_with_fallback remembers rejections process-wide; keep this test's
    # memory out of every other test.
    monkeypatch.setattr(generation, "_REJECTED", set())
    monkeypatch.setattr(generation, "_ACCEPTED", {})
    calls = []

    class Completions:
        def create(self, **params):
            calls.append(dict(params))
            if len(calls) == 1:
                raise APIStatusError(400, "Unsupported value: 'reasoning_effort' does not "
                                          "support 'minimal' with this model.")
            return openai_response()

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    result = run("openai", lambda key: client)
    assert result.ok
    assert len(calls) == 2


def test_ollama_web_search_works_at_no_charge():
    seen = []

    def call(endpoint, payload, key):
        seen.append((endpoint, payload, key))
        return {"results": []}

    result = run("ollama.com", call, key="abc")
    assert result.ok and result.cost is None
    assert seen == [("web_search", {"query": "test", "max_results": 1}, "abc")]
    assert "web search" in result.message


# --------------------------------------------------------------------------- #
# No key, unknown provider                                                     #
# --------------------------------------------------------------------------- #

def test_no_key_says_so_without_a_request(monkeypatch):
    import idt_core.keys as keys

    monkeypatch.setattr(keys, "resolve_api_key", lambda provider: None)
    factory, rec = claude_client(claude_response())
    result = key_check.test_api_key("claude", client_factory=factory)
    assert not result.ok and "no Claude key" in result.message
    assert rec.calls == []


def test_resolved_key_is_the_one_used(monkeypatch):
    import idt_core.keys as keys

    monkeypatch.setattr(keys, "resolve_api_key", lambda provider: "resolved-" + provider)
    got = []
    factory, _ = claude_client(claude_response())
    key_check.test_api_key("claude", client_factory=lambda key: (got.append(key), factory(key))[1])
    assert got == ["resolved-claude"]


def test_unrecognised_provider_cannot_be_tested():
    assert not key_check.can_test("gemini")
    result = key_check.test_api_key("gemini", api_key="x")
    assert not result.ok and "can't test" in result.message
    assert all(key_check.can_test(p) for p in ("claude", "openai", "ollama.com", "Claude"))


def test_not_collected_by_pytest():
    assert key_check.test_api_key.__test__ is False


# --------------------------------------------------------------------------- #
# Failure mapping                                                              #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("provider,error,words", [
    ("claude", anthropic_error(401, "invalid x-api-key", "authentication_error"),
     "didn't accept this key"),
    ("openai", openai_error(401, "Incorrect API key provided: sk-proj-****abcd.", "invalid_api_key"),
     "didn't accept this key"),
    ("claude", anthropic_error(400, "Your credit balance is too low to access the "
                                    "Anthropic API.", "invalid_request_error"),
     "out of credit"),
    ("claude", anthropic_error(400, "Plans & Billing", "billing_error"), "out of credit"),
    ("claude", anthropic_error(429, "Spend limit reached", "rate_limit_error",
                               error_code="enforced_spend_limit_reached"), "spending limit"),
    ("openai", openai_error(429, "You exceeded your current quota, please check your plan "
                                 "and billing details.", "insufficient_quota"),
     "out of credit"),
    ("openai", openai_error(402, "Payment required"), "out of credit"),
    ("claude", anthropic_error(403, "This API key is not assigned to a workspace.",
                               "permission_error"), "isn't in a workspace"),
    ("claude", anthropic_error(403, "Organization on hold", "permission_error",
                               error_code="organization_on_hold"), "on hold"),
    ("openai", openai_error(403, "Project does not have access to model"), "refused the request"),
    ("openai", openai_error(404, "The model does not exist", "model_not_found"), "can't use"),
    ("claude", anthropic_error(429, "Number of requests has exceeded your rate limit",
                               "rate_limit_error"), "rate limited"),
    ("claude", anthropic_error(529, "Overloaded", "overloaded_error"), "overloaded"),
    ("openai", openai_error(500, "The server had an error"), "problem on its side"),
    ("claude", APIConnectionError("Connection error."), "couldn't reach Claude"),
    ("openai", APITimeoutError("Request timed out."), "didn't answer in time"),
    ("claude", ConnectionRefusedError(10061, "refused"), "couldn't reach Claude"),
    ("openai", openai_error(418, "teapot"), "refused the test request (HTTP 418)"),
])
def test_failures_are_plain_words(provider, error, words):
    factory = (claude_client if provider == "claude" else openai_client)(error=error)[0]
    result = run(provider, factory)
    assert not result.ok
    assert words in result.message
    assert result.cost is None
    # A short verdict first, so a screen reader's first line is the answer.
    assert result.verdict and result.message.startswith(result.verdict)
    assert len(result.verdict) <= 70, result.verdict


def test_success_has_a_verdict_too():
    factory, _ = claude_client(claude_response())
    result = run("claude", factory)
    assert result.verdict == "Your Claude key works."
    assert result.detail.startswith("That test cost")


def test_provider_message_is_quoted_after_the_explanation():
    factory, _ = claude_client(error=anthropic_error(401, "invalid x-api-key",
                                                     "authentication_error"))
    result = run("claude", factory)
    assert result.message.endswith("Claude said: invalid x-api-key")


@pytest.mark.parametrize("status,words", [
    (401, "didn't accept this key"),
    (403, "didn't accept this key"),
    (429, "search limit"),
    (502, "problem on its side"),
])
def test_ollama_http_failures(status, words):
    def call(endpoint, payload, key):
        raise urllib.error.HTTPError("https://ollama.com/api/web_search", status, "x", {},
                                     io.BytesIO(b'{"error": "unauthorized"}'))

    result = run("ollama.com", call, key="k")
    assert not result.ok and words in result.message


def test_ollama_network_down():
    def call(endpoint, payload, key):
        raise urllib.error.URLError(OSError(11001, "getaddrinfo failed"))

    result = run("ollama.com", call, key="k")
    assert not result.ok and "couldn't reach ollama.com" in result.message


def test_ollama_timeout():
    def call(endpoint, payload, key):
        raise urllib.error.URLError(TimeoutError("timed out"))

    result = run("ollama.com", call, key="k")
    assert "didn't answer in time" in result.message


# --------------------------------------------------------------------------- #
# Never any key material                                                       #
# --------------------------------------------------------------------------- #

def test_the_key_itself_is_never_echoed():
    error = anthropic_error(401, f"Key {FAKE_KEY} is invalid", "authentication_error")
    factory, _ = claude_client(error=error)
    result = run("claude", factory)
    assert FAKE_KEY not in result.message
    assert "QQQQ" not in result.message


def test_masked_openai_key_in_the_message_is_removed():
    factory, _ = openai_client(error=openai_error(
        401, "Incorrect API key provided: sk-proj-AbCd****************************WxYz.",
        "invalid_api_key"))
    result = run("openai", factory, key="sk-proj-" + "A" * 40)
    assert "WxYz" not in result.message and "sk-proj" not in result.message


def test_unexpected_crash_is_scrubbed(monkeypatch):
    def boom(key, factory):
        raise RuntimeError(f"bad header Authorization: Bearer {key}")

    monkeypatch.setattr(key_check, "_test_claude", boom)
    result = run("claude", None)
    assert not result.ok and FAKE_KEY not in result.message


@pytest.mark.parametrize("text", [
    "sk-ant-api03-abcdefghijklmnop",
    "Bearer abc.def.ghi",
    "x-api-key: something-secret",
    "api_key=hunter2hunter2",
    "0123456789abcdef0123456789abcdef.ABCDEFGHIJ",
])
def test_scrub_removes_key_like_text(text):
    cleaned = key_check.scrub(f"before {text} after")
    assert "[key removed]" in cleaned
    assert "before" in cleaned and "after" in cleaned
    for secret in ("abcdefghijklmnop", "abc.def.ghi", "something-secret", "hunter2",
                   "0123456789abcdef"):
        assert secret not in cleaned


def test_scrub_keeps_ordinary_words_and_trims_long_text():
    assert key_check.scrub("invalid x-api-key") == "invalid x-api-key"
    assert key_check.scrub("a task-based desk-top flow") == "a task-based desk-top flow"
    assert len(key_check.scrub("word " * 200)) <= 303


@pytest.mark.parametrize("text,expected", [
    ("Authorization: Bearer abcdef", "Authorization: Bearer [key removed]"),
    ("Bearer abcdef", "[key removed]"),
    ("x-api-key: abcdef here", "x-api-key: [key removed] here"),
])
def test_scrub_leaves_one_clean_placeholder(text, expected):
    assert key_check.scrub(text) == expected


def test_scrub_after_an_exact_secret_does_not_double_up():
    assert (key_check.scrub("Authorization: Bearer s3cret-value", "s3cret-value")
            == "Authorization: Bearer [key removed]")


# --------------------------------------------------------------------------- #
# The real SDKs' error objects (built locally, no network)                     #
# --------------------------------------------------------------------------- #

def _real_response(status):
    try:
        import httpx2 as httpx
    except ImportError:
        httpx = pytest.importorskip("httpx")
    request = httpx.Request("POST", "https://api.example/v1/test")
    return request, httpx.Response(status, request=request)


def _real_error(build):
    try:
        return build()
    except TypeError as exc:      # an SDK whose constructor has changed shape
        pytest.skip(f"SDK error constructor changed: {exc}")


def test_real_anthropic_errors_map():
    anthropic = pytest.importorskip("anthropic")
    _req, resp = _real_response(401)
    auth = _real_error(lambda: anthropic.AuthenticationError(
        "invalid x-api-key", response=resp,
        body={"type": "error", "error": {"type": "authentication_error",
                                         "message": "invalid x-api-key"}}))
    factory, _ = claude_client(error=auth)
    assert "didn't accept this key" in run("claude", factory).message

    _req, resp = _real_response(400)
    credit = _real_error(lambda: anthropic.BadRequestError(
        "credit", response=resp,
        body={"type": "error", "error": {"type": "invalid_request_error",
                                         "message": "Your credit balance is too low"}}))
    factory, _ = claude_client(error=credit)
    assert "out of credit" in run("claude", factory).message

    request, _resp = _real_response(200)
    timeout = _real_error(lambda: anthropic.APITimeoutError(request=request))
    factory, _ = claude_client(error=timeout)
    assert "didn't answer in time" in run("claude", factory).message

    down = _real_error(lambda: anthropic.APIConnectionError(request=request))
    factory, _ = claude_client(error=down)
    assert "couldn't reach Claude" in run("claude", factory).message


def test_real_openai_errors_map():
    openai = pytest.importorskip("openai")
    _req, resp = _real_response(429)
    quota = _real_error(lambda: openai.RateLimitError(
        "quota", response=resp,
        body={"message": "You exceeded your current quota", "code": "insufficient_quota"}))
    factory, _ = openai_client(error=quota)
    assert "out of credit" in run("openai", factory).message

    _req, resp = _real_response(429)
    busy = _real_error(lambda: openai.RateLimitError(
        "slow down", response=resp,
        body={"message": "Rate limit reached for requests", "code": "rate_limit_exceeded"}))
    factory, _ = openai_client(error=busy)
    assert "rate limited" in run("openai", factory).message

    _req, resp = _real_response(401)
    bad = _real_error(lambda: openai.AuthenticationError(
        "bad", response=resp,
        body={"message": "Incorrect API key provided: sk-proj-****abcd.",
              "code": "invalid_api_key"}))
    factory, _ = openai_client(error=bad)
    message = run("openai", factory).message
    assert "didn't accept this key" in message and "abcd" not in message
