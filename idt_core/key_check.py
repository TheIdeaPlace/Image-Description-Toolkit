"""Test Key: check that a saved API key works by sending one tiny request.

Configure > API Keys calls :func:`test_api_key` on a background thread. It
never raises and never returns key material: every message is put through
:func:`scrub` before it leaves this module, because a provider's error text
can quote part of the key ("Incorrect API key provided: sk-proj-...abcd").

What each test sends:

* **Claude** -- one Messages request on the cheapest priced Claude model,
  "Reply with the single word OK.", capped at a handful of output tokens.
* **OpenAI** -- the same on the cheapest priced OpenAI model, with the least
  reasoning the model takes, so the request is cheap and cannot come back
  empty for want of tokens (an empty answer still proves the key works).
* **Ollama web search** (the ollama.com key) -- one web search for one result,
  which is how IDT uses that key. ollama.com doesn't price a search on its
  own; it counts toward the account's usage limits.

The models are chosen from :mod:`idt_core.pricing` rather than named here, so
the test follows the price table when a cheaper model is added. wx-free.

(Named key_check, not key_test: pytest collects any ``*_test.py``.)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Optional

__all__ = ["KeyTestResult", "test_api_key", "can_test", "scrub",
           "cheapest_model", "TESTABLE", "PROVIDER_LABELS"]

#: Canonical provider names (idt_core.keys) that Test Key can check.
TESTABLE = ("claude", "openai", "ollama.com")

#: How each provider is named in what the user hears.
PROVIDER_LABELS = {
    "claude": "Claude",
    "openai": "OpenAI",
    "ollama.com": "ollama.com",
}

PROMPT = "Reply with the single word OK."

#: Output cap for the chat tests. Claude answers "OK" in 2 tokens; OpenAI's
#: reasoning models count reasoning against the cap, and at their lowest
#: effort this is plenty. A longer answer is cut off, which still proves the key.
CLAUDE_MAX_TOKENS = 16
OPENAI_MAX_TOKENS = 64

#: Seconds before the test gives up. One retry is allowed by the SDKs, so the
#: longest wait is about twice this.
TIMEOUT_SECONDS = 30

# Text that may be a key, or part of one.
_REMOVED = "[key removed]"
_KEYLIKE = re.compile(
    "|".join((
        # OpenAI and Anthropic keys, including the masked form OpenAI quotes
        # back. \b, so "task-based" and "desk-top" are left alone.
        r"\bsk-[A-Za-z0-9_\-*.]{3,}",
        # A credential after its label: "Bearer x", "x-api-key: x", "api_key=x".
        # (Not the placeholder an exact-secret replacement already left.)
        r"(?i:\bbearer\s+(?!\[key removed\])\S+)",
        r"(?i:\b(?P<label>x-api-key|api[_-]?key|authorization)"
        r"(?P<sep>\s*[:=]\s*(?:bearer\s+)?)(?!\[key removed\])(?!bearer\b)\S+)",
        # Any long unbroken token (ollama.com keys are long hex-and-dot strings).
        r"[A-Za-z0-9_\-.]{32,}",
    )))


def _replace_keylike(match: "re.Match") -> str:
    if match.group("label"):
        return f"{match.group('label')}{match.group('sep')}{_REMOVED}"
    return _REMOVED

#: Longest provider message shown; past this it's noise, not explanation.
_MESSAGE_LIMIT = 300


@dataclass
class KeyTestResult:
    """What a key test found. ``message`` is a whole sentence to show as is."""
    ok: bool
    message: str
    cost: Optional[float] = None     # US dollars, when known
    model: str = ""                  # the model tested with, if any
    #: The first, short sentence of ``message``: the answer in a few words,
    #: for a UI that shows it on a line of its own.
    verdict: str = ""

    @property
    def detail(self) -> str:
        """``message`` after the verdict; "" when there's no separate verdict."""
        if self.verdict and self.message.startswith(self.verdict):
            return self.message[len(self.verdict):].strip()
        return ""


def scrub(text: str, *secrets: Optional[str]) -> str:
    """``text`` with anything key-like replaced by "[key removed]"."""
    text = str(text or "")
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, _REMOVED)
    # One pass, so a pattern never chews on another's placeholder.
    text = _KEYLIKE.sub(_replace_keylike, text)
    text = " ".join(text.split())
    if len(text) > _MESSAGE_LIMIT:
        text = text[:_MESSAGE_LIMIT].rstrip() + "..."
    return text


def can_test(provider: str) -> bool:
    """True if Test Key knows how to check this provider's key."""
    return (provider or "").strip().lower() in TESTABLE


def cheapest_model(provider: str) -> str:
    """The priced model with the lowest input+output rate, skipping models
    kept only so old workspaces can be costed."""
    from .pricing import KEPT_FOR_OLD_WORKSPACES, PRICES

    table = {m: p for m, p in PRICES.get(provider, {}).items()
             if m not in KEPT_FOR_OLD_WORKSPACES}
    if not table:
        return ""
    return min(table, key=lambda m: (table[m].input + table[m].output, m))


# --------------------------------------------------------------------------- #
# Reading an exception                                                         #
# --------------------------------------------------------------------------- #

def _status(exc: BaseException) -> Optional[int]:
    for attr in ("status_code", "status", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and not isinstance(value, bool) and 100 <= value < 600:
            return value
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def _body_error(exc: BaseException) -> dict:
    """The provider's error object: Anthropic's body is {"error": {...}},
    OpenAI's is the error object itself, ollama.com's {"error": "text"}."""
    body = getattr(exc, "body", None)
    if not isinstance(body, dict):
        return {}
    inner = body.get("error")
    if isinstance(inner, dict):
        return inner
    if isinstance(inner, str):
        return {"message": inner}
    return body


def _provider_words(exc: BaseException) -> str:
    """The provider's own explanation, as plain as it comes."""
    err = _body_error(exc)
    message = err.get("message") if isinstance(err.get("message"), str) else ""
    if not message:
        message = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
    return str(message)


def _error_codes(exc: BaseException) -> set:
    """Every machine-readable code the error carries: OpenAI's ``code``
    ("insufficient_quota"), Anthropic's ``type`` ("billing_error") and
    ``error_code`` ("enforced_spend_limit_reached")."""
    err = _body_error(exc)
    values = (err.get("code"), err.get("type"), err.get("error_code"),
              getattr(exc, "code", None))
    return {v.lower() for v in values if isinstance(v, str) and v}


def _is_connection_error(exc: BaseException) -> bool:
    """No answer at all: the SDKs' connection errors, urllib's URLError, and
    any socket-level OSError (DNS failure, connection refused)."""
    names = {cls.__name__ for cls in type(exc).__mro__}
    return (bool(names & {"APIConnectionError", "ConnectError", "URLError"})
            or isinstance(exc, OSError))


def _is_timeout(exc: BaseException) -> bool:
    names = {cls.__name__ for cls in type(exc).__mro__}
    return bool(names & {"APITimeoutError", "TimeoutError", "ReadTimeout",
                         "ConnectTimeout", "timeout"})


# --------------------------------------------------------------------------- #
# Turning a failure into words                                                  #
# --------------------------------------------------------------------------- #

_CONSOLE = {
    "claude": "the Claude Console (console.anthropic.com)",
    "openai": "the OpenAI dashboard (platform.openai.com)",
    "ollama.com": "your ollama.com account settings (ollama.com/settings/keys)",
}

_BILLING = {
    "claude": "Billing in the Claude Console",
    "openai": "Billing at platform.openai.com",
    "ollama.com": "your plan at ollama.com",
}


def _failure(provider: str, exc: BaseException, model: str, key: Optional[str]) -> KeyTestResult:
    """Plain words for why the test failed, with the provider's own message
    (scrubbed) after them."""
    name = PROVIDER_LABELS.get(provider, provider)
    said = scrub(_provider_words(exc), key)
    lowered = said.lower()
    codes = _error_codes(exc)
    status = _status(exc)

    # Each answer is a short verdict, then what to do. The verdict is kept
    # short because a screen reader landing in the result box reads one line.
    def result(verdict: str, detail: str = "", quote: bool = True) -> KeyTestResult:
        text = f"{verdict} {detail}".strip()
        if quote and said:
            text = f"{text} {name} said: {said}"
        return KeyTestResult(False, text, None, model, verdict)

    if _is_timeout(exc):
        return result(f"{name} didn't answer in time.", "Test again in a moment.", quote=False)
    if status is None and _is_connection_error(exc):
        return result(f"IDT couldn't reach {name}.", "Check your internet connection, "
                      "and any proxy or firewall, then test again.", quote=False)

    no_credit = (
        status == 402
        or codes & {"insufficient_quota", "billing_error", "enforced_spend_limit_reached"}
        or any(w in lowered for w in ("credit balance", "insufficient_quota",
                                      "exceeded your current quota", "billing",
                                      "payment required", "no credit"))
    )
    if no_credit:
        return result(f"{name} accepted the key, but the account is out of credit.",
                      "Or it has reached its spending limit. Check "
                      f"{_BILLING[provider]}, then test again.")
    if "organization_on_hold" in codes:
        return result(f"{name} accepted the key, but its organization is on hold.",
                      f"Check {_CONSOLE[provider]}.")
    if status == 401 or (status == 403 and provider == "ollama.com"):
        return result(f"{name} didn't accept this key.",
                      "It may have been copied only in part, or deleted or disabled. "
                      f"Copy it again, or make a new one, in {_CONSOLE[provider]}, "
                      "and replace it here.")
    if status == 403:
        if provider == "claude" and "workspace" in lowered:
            return result("Claude accepted the key, but it isn't in a workspace.",
                          "Assign it to one in the Claude Console (new keys are, "
                          "by default), then test again.")
        return result(f"{name} accepted the key but refused the request.",
                      "The key may not be allowed to use this model, or the account "
                      "may be restricted. Check the key's permissions in "
                      f"{_CONSOLE[provider]}.")
    if status == 404:
        return result(f"{name} accepted the key, but it can't use {model or 'the test'}.",
                      "That is the model IDT tests with. Check which models the key's "
                      f"project may use in {_CONSOLE[provider]}.")
    if status == 429:
        if provider == "ollama.com":
            return result("ollama.com accepted the key, but its search limit is used up.",
                          "Test again later.")
        return result(f"{name} accepted the key, but it is rate limited.",
                      "Too many requests just now. Wait a minute and test again.")
    if status == 529 or "overloaded" in lowered:
        return result(f"{name} is overloaded right now.", "Test again in a few minutes.")
    if status is not None and status >= 500:
        return result(f"{name} had a problem on its side (HTTP {status}).",
                      "Test again in a few minutes.")
    if status is not None:
        return result(f"{name} refused the test request (HTTP {status}).")
    return result("The test didn't work.")


def _works(provider: str, model: str, input_tokens: int, output_tokens: int) -> KeyTestResult:
    from .pricing import estimate, format_dollars

    name = PROVIDER_LABELS.get(provider, provider)
    verdict = f"Your {name} key works."
    cost, _note = estimate(provider, model, input_tokens or 0, output_tokens or 0)
    if cost is None:
        return KeyTestResult(True, f"{verdict} IDT doesn't know the price of "
                                   f"{model}, so what that test cost isn't known.",
                             None, model, verdict)
    return KeyTestResult(True, f"{verdict} That test cost {format_dollars(cost)}.",
                         cost, model, verdict)


# --------------------------------------------------------------------------- #
# The tests                                                                    #
# --------------------------------------------------------------------------- #

def _test_claude(key: str, client_factory: Optional[Callable]) -> KeyTestResult:
    model = cheapest_model("claude")
    try:
        if client_factory is None:
            import anthropic

            client = anthropic.Anthropic(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=1)
        else:
            client = client_factory(key)
    except ImportError:
        return KeyTestResult(False, "The anthropic package isn't installed, so IDT "
                                    "can't test a Claude key.", None, model)
    try:
        response = client.messages.create(
            model=model, max_tokens=CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": PROMPT}])
    except Exception as exc:                                    # noqa: BLE001
        return _failure("claude", exc, model, key)
    usage = getattr(response, "usage", None)
    return _works("claude", model, getattr(usage, "input_tokens", 0),
                  getattr(usage, "output_tokens", 0))


def _test_openai(key: str, client_factory: Optional[Callable]) -> KeyTestResult:
    from .generation import send_with_fallback
    from .providers.openai_provider import (EFFORT_FALLBACK, is_reasoning_model,
                                            lowest_effort)

    model = cheapest_model("openai")
    try:
        if client_factory is None:
            import openai

            client = openai.OpenAI(api_key=key, timeout=TIMEOUT_SECONDS, max_retries=1)
        else:
            client = client_factory(key)
    except ImportError:
        return KeyTestResult(False, "The openai package isn't installed, so IDT "
                                    "can't test an OpenAI key.", None, model)
    params = {"model": model,
              "messages": [{"role": "user", "content": PROMPT}],
              # Never max_tokens: reasoning models reject it.
              "max_completion_tokens": OPENAI_MAX_TOKENS}
    if is_reasoning_model(model):
        params["reasoning_effort"] = lowest_effort(model)
    try:
        response = send_with_fallback(client.chat.completions.create, params,
                                      ("reasoning_effort",), "openai", model,
                                      EFFORT_FALLBACK)
    except Exception as exc:                                    # noqa: BLE001
        return _failure("openai", exc, model, key)
    usage = getattr(response, "usage", None)
    return _works("openai", model, getattr(usage, "prompt_tokens", 0),
                  getattr(usage, "completion_tokens", 0))


class _HttpFailure(Exception):
    """An ollama.com HTTP error, in the shape _failure reads."""

    def __init__(self, status: int, body: dict):
        super().__init__(f"HTTP {status}")
        self.status_code = status
        self.body = body


def _test_ollama_web(key: str, call: Optional[Callable]) -> KeyTestResult:
    import urllib.error

    if call is None:
        from .chat.tools import _call_api as call
    try:
        call("web_search", {"query": "test", "max_results": 1}, key)
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", "replace") or "{}")
        except Exception:                                       # noqa: BLE001
            body = {}
        return _failure("ollama.com", _HttpFailure(exc.code, body if isinstance(body, dict) else {}),
                        "", key)
    except Exception as exc:                                    # noqa: BLE001
        # urlopen wraps a timeout in URLError(reason=TimeoutError).
        reason = getattr(exc, "reason", None)
        return _failure("ollama.com", reason if isinstance(reason, TimeoutError) else exc,
                        "", key)
    verdict = "Your ollama.com key works."
    return KeyTestResult(True, f"{verdict} That test was one web search, which "
                               "ollama.com doesn't charge for on its own; it counts "
                               "toward your account's usage limits.", None, "", verdict)


def test_api_key(provider: str, *, api_key: Optional[str] = None,
                 client_factory: Optional[Callable] = None) -> KeyTestResult:
    """Send one tiny request with ``provider``'s key and say whether it works.

    ``api_key`` defaults to the key IDT would use (``idt_core.keys``).
    ``client_factory`` is for tests: it takes the key and returns an object
    shaped like the SDK client (for ollama.com, the ``_call_api`` function).
    Never raises; never puts key material in the result.
    """
    name = (provider or "").strip().lower()
    label = PROVIDER_LABELS.get(name, provider)
    if name not in TESTABLE:
        return KeyTestResult(False, f"IDT can't test a key for {scrub(label)}.")
    key = api_key
    if key is None:
        from .keys import resolve_api_key

        key = resolve_api_key(name)
    if not key:
        return KeyTestResult(False, f"There's no {label} key to test. Add one first.")
    try:
        if name == "claude":
            return _test_claude(key, client_factory)
        if name == "openai":
            return _test_openai(key, client_factory)
        return _test_ollama_web(key, client_factory)
    except Exception as exc:                                    # noqa: BLE001
        # A bug here must not take the dialog's worker thread down silently.
        return KeyTestResult(False, f"The test didn't work: {scrub(str(exc), key)}")


# Not a pytest test, whatever its name says: a test module that imports it
# by name would otherwise have pytest try to run it.
test_api_key.__test__ = False
