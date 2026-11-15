"""
Ollama provider — local models (llava, qwen2-vl, llama3.2-vision, etc.)
Connects to a running Ollama instance; default host is localhost:11434.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Optional

from ..generation import THINKING_AUTO, THINKING_OFF, THINKING_ON, GenerationOptions
from .base import BaseProvider, DescriptionResult

logger = logging.getLogger(__name__)

try:
    from idt_core.config import DEFAULT_OLLAMA_MODEL as DEFAULT_MODEL  # dev
except ImportError:
    try:
        from config import DEFAULT_OLLAMA_MODEL as DEFAULT_MODEL        # frozen
    except ImportError:
        DEFAULT_MODEL = "llama3.2-vision"                               # fallback
DEFAULT_HOST = "http://localhost:11434"

# (host, model) -> the /api/show payload, or None when the probe failed.
#
# ONE cache for one endpoint. Capabilities, context length and vision all come
# from the same /api/show response, so probing them separately meant a single
# chat turn issued two or three round trips for the same model before the first
# token. Keyed by host as well as name: the same model name on a local and a
# remote server is not the same model, and a cached answer from one must never
# be served for the other.
_SHOW_CACHE: dict[tuple[str, str], Optional[dict]] = {}

# Failures are cached too, but only briefly. Not caching them at all meant an
# unreachable daemon was re-probed on every single turn, each attempt waiting
# out its own timeout; caching them forever would mean Ollama starting up later
# in the session was never noticed. A short TTL gets both.
_NEGATIVE_TTL_SECONDS = 30.0
_NEGATIVE_AT: dict[tuple[str, str], float] = {}


def _resolve_host(host: Optional[str]) -> str:
    """The Ollama base URL to talk to.

    ``None`` means "whatever the SDK would use", i.e. ``OLLAMA_HOST`` when it is
    set. Passing an explicit host and letting the raw-REST fallback default to
    localhost is what made remote-Ollama users silently fall back to a 32k
    context window while their chat turns went to the real server.
    """
    resolved = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).strip()
    if not resolved.startswith(("http://", "https://")):
        resolved = f"http://{resolved}"
    return resolved.rstrip("/")


def _show(name: str, host: Optional[str] = None, client=None) -> Optional[dict]:
    """The /api/show payload for ``name``, as a plain dict, or None.

    Tries the SDK first, then raw REST, because the ``ollama`` package drops
    ``model_info`` entirely in some released versions. Results are cached per
    (host, model); failures are cached for ``_NEGATIVE_TTL_SECONDS``.
    """
    resolved = _resolve_host(host)
    key = (resolved, name)
    if key in _SHOW_CACHE:
        payload = _SHOW_CACHE[key]
        if payload is not None:
            return payload
        if time.monotonic() - _NEGATIVE_AT.get(key, 0.0) < _NEGATIVE_TTL_SECONDS:
            return None
        # TTL expired — fall through and probe again.

    own_client = client is None
    info = None
    try:
        if client is None:
            import ollama
            client = ollama.Client(host=resolved)
        info = client.show(name)
    except Exception:
        info = None

    def _field(key_name):
        if info is None:
            return None
        value = getattr(info, key_name, None)
        if value is None and isinstance(info, dict):
            value = info.get(key_name)
        return value

    payload = {
        "model_info": _field("model_info"),
        "parameters": _field("parameters"),
        "capabilities": _field("capabilities"),
    }

    # The SDK drops `model_info` entirely in some released versions while still
    # returning `capabilities`, so the trigger is that specific field being
    # absent — not the whole response being empty. Getting this wrong means
    # context discovery silently returns None on exactly the servers the REST
    # fallback was written for. An injected client is a test double or a shared
    # listing client, so only a client we made talks to the real server.
    if own_client and payload["model_info"] is None:
        try:
            raw = _show_via_rest(name, resolved)
            for field in ("model_info", "parameters", "capabilities"):
                if payload[field] is None:
                    payload[field] = raw.get(field)
        except Exception:
            pass

    if not any(v is not None for v in payload.values()):
        _SHOW_CACHE[key] = None
        _NEGATIVE_AT[key] = time.monotonic()
        return None

    _SHOW_CACHE[key] = payload
    _NEGATIVE_AT.pop(key, None)
    return payload


def model_capabilities(name: str, host: Optional[str] = None, client=None) -> Optional[list]:
    """Lowercased capability list from /api/show, or None when unavailable.

    Current servers report from {completion, vision, tools, thinking, insert,
    embedding}; older ones report nothing, in which case callers must decide
    their own fail-open/fail-closed policy — that is why this returns None
    instead of [].
    """
    payload = _show(name, host=host, client=client)
    if payload is None:
        return None
    caps = payload.get("capabilities")
    if caps is None:
        return None
    return [str(c).lower() for c in caps]


def model_is_chat_capable(name: str, host: Optional[str] = None, client=None) -> bool:
    """True when the model can hold a conversation (`completion` capability).

    Fails OPEN like :func:`model_has_vision`, and for the same reason: a
    transient probe failure must never hide a working model from a picker.
    Excludes embedding-only models, which /api/tags lists but /api/chat
    rejects.
    """
    caps = model_capabilities(name, host=host, client=client)
    if caps is None:
        return True
    return "completion" in caps


def _parse_context_length(model_info, parameters) -> int:
    """Context length out of a /api/show response's fields, or 0."""
    for key, val in (model_info or {}).items():
        lowered = str(key).lower()
        if "context_length" in lowered or "context_window" in lowered:
            try:
                return int(val)
            except (TypeError, ValueError):
                continue
    for line in (parameters or "").splitlines():
        parts = line.strip().lower().split()
        if len(parts) >= 2 and parts[0] == "num_ctx":
            try:
                return int(parts[1])
            except ValueError:
                return 0
    return 0


def _show_via_rest(name: str, host: str) -> dict:
    """Raw POST /api/show. The ``ollama`` Python package's ``show()`` drops
    ``model_info`` entirely in some released versions, so when the SDK comes
    back empty this asks the server directly."""
    import json
    import urllib.request

    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/show",
        data=json.dumps({"model": name}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def model_context_length(name: str, host: Optional[str] = None, client=None) -> Optional[int]:
    """Context length Ollama reports for a model, or None when unavailable.

    Reads /api/show. Newer servers expose ``model_info`` with an
    architecture-prefixed key (``llama.context_length``); older ones only
    mention ``num_ctx`` in the ``parameters`` string. Both are tried, in that
    order. Shared by the chat token budgeter and ImageDescriber's token gauge
    so there is one implementation of this parsing.
    """
    payload = _show(name, host=host, client=client)
    if payload is None:
        return None
    size = _parse_context_length(payload.get("model_info"), payload.get("parameters"))
    return size if size > 0 else None


def model_has_vision(name: str, host: Optional[str] = None, client=None) -> bool:
    """True when Ollama reports `vision` among the model's capabilities.

    Fails OPEN: if the capability query itself errors we return True and keep the
    model. Only a *successful* query that omits `vision` excludes it — a transient
    API problem must never silently hide a working model from the picker.
    """
    caps = model_capabilities(name, host=host, client=client)
    if caps is None:
        return True                          # unreachable/silent — do not exclude
    return "vision" in caps


def model_can_think(name: str, host: Optional[str] = None, client=None) -> bool:
    """True when /api/show lists `thinking`. Fails CLOSED (see resolve_think)."""
    try:
        caps = model_capabilities(name, host=host, client=client)
    except Exception:                                            # noqa: BLE001
        return False
    return bool(caps) and "thinking" in caps


def resolve_think(mode: Optional[str], name: str, host: Optional[str] = None,
                  client=None) -> Optional[bool]:
    """The ``think`` value to send for a THINKING_* mode, or None to omit it.

    The one thinking policy for every Ollama request IDT makes, description
    and chat alike (issue #392):

    * ``on`` is passed through unprobed. The user asked for thinking; if the
      model cannot do it, the API's 400 saying so is the honest answer.
    * ``off`` is sent only to models that report the capability. Against any
      other model it is already satisfied, and omitting it keeps the request
      valid on servers too old to know the field.
    * ``auto`` (or None) turns separation ON for thinking models, so their
      scratch work arrives in its own field instead of inside the answer as
      ``<think>`` tags, and omits the field otherwise.

    The capability probe fails CLOSED: a wrong True breaks the request, while a
    wrong None merely leaves tags in the text.

    Note that ``off`` is a request, not a guarantee. Every qwen3-vl thinking
    tag tested (2B, 8B, 32B) keeps reasoning with ``think: false``; for those
    the fix is the ``-instruct`` tag. :meth:`OllamaProvider.describe` logs it.
    """
    if mode == THINKING_ON:
        return True
    has_thinking = model_can_think(name, host=host, client=client)
    if mode == THINKING_OFF:
        return False if has_thinking else None
    return True if has_thinking else None


def is_cloud_model(name: str) -> bool:
    """Models Ollama proxies to its cloud (``kimi-k2.5:cloud``, ``gpt-oss:20b-cloud``)."""
    return ":cloud" in name or name.endswith("-cloud")


#: GenerationOptions fields that map one-to-one onto Ollama ``options`` keys.
_DIRECT_OPTIONS = ("temperature", "top_p", "top_k", "repeat_penalty")


def request_options(opts: GenerationOptions, name: str,
                    think: Optional[bool] = None) -> dict:
    """GenerationOptions as the ``options`` dict of an Ollama request.

    Only what is set goes on the wire; everything else stays at the model's own
    defaults (its Modelfile), which is what "automatic" means for Ollama.
    ``num_predict`` is withheld in two cases, both of which cut answers off:

    * cloud models, whose servers enforce their own output limits; forwarding
      a cap was the main cause of empty and truncated cloud responses;
    * when thinking is on, because Ollama counts the reasoning against the
      same cap, so a thinking model can spend it all before the answer starts.
    """
    options: dict = {}
    for key in _DIRECT_OPTIONS:
        value = getattr(opts, key)
        if value is not None:
            options[key] = value
    if opts.max_output_tokens:
        if is_cloud_model(name):
            logger.info("Not sending num_predict to cloud model %s: cloud servers "
                        "apply their own output limit", name)
        elif think is True:
            logger.info("Not sending num_predict to %s while thinking is on: the "
                        "reasoning would count against it", name)
        else:
            options["num_predict"] = opts.max_output_tokens
    options.update(opts.extra or {})
    return options


#: What descriptions use when the user has set nothing (issue #392). Thinking
#: off: the reasoning is discarded, and on a thinking model it was 60-75% of
#: the output and most of the time per image. Everything else automatic.
DESCRIBE_DEFAULTS = GenerationOptions(thinking=THINKING_OFF)

# (host, model) pairs already warned about ignoring think=false, so a batch
# logs it once rather than once per image.
_WARNED_IGNORED_THINK: set = set()


def _answer_parts(response) -> tuple[str, str]:
    """(answer, thinking) from a chat response, SDK object or plain dict.

    Servers or models that do not separate reasoning put it in the answer as
    ``<think>...</think>``; that is moved out here so it never lands in a
    saved description.
    """
    message = getattr(response, "message", None)
    if message is None and isinstance(response, dict):
        message = response.get("message")
    if message is None:
        return "", ""
    if isinstance(message, dict):
        text = message.get("content") or ""
        thinking = message.get("thinking") or ""
    else:
        text = getattr(message, "content", None) or ""
        thinking = getattr(message, "thinking", None) or ""
    stripped = text.lstrip()
    if stripped.startswith("<think>") and "</think>" in stripped:
        inline, _, rest = stripped[len("<think>"):].partition("</think>")
        thinking = (thinking + inline) if thinking else inline
        text = rest.lstrip()
    return text, thinking


class EmptyDescriptionError(RuntimeError):
    """The model produced reasoning but no description, even after a retry."""


class OllamaProvider(BaseProvider):
    #: Ceiling on one description request. Generous on purpose: a thinking
    #: model on a CPU-only machine took 229 s for one photo (Surface Laptop 7,
    #: qwen3-vl:8b), and ImageDescriber's old 300 s limit would have failed a
    #: 32B model there. Long enough for slow hardware, short of hanging forever.
    DESCRIBE_TIMEOUT_SECONDS = 1800

    def __init__(self, model: str = DEFAULT_MODEL, host: Optional[str] = None,
                 options: Optional[GenerationOptions] = None):
        try:
            import ollama  # noqa: F401
        except ImportError:
            raise ImportError(
                "ollama package is required: pip install ollama"
            )
        self._model = model
        # None means "let the SDK decide", which is how OLLAMA_HOST reaches us.
        # Hardcoding localhost here sent every capability/context probe to the
        # local daemon while the chat turns themselves went to the real server.
        self._host = host.rstrip("/") if host else None
        #: User and caller settings, layered over DESCRIBE_DEFAULTS per request.
        self._options = options or GenerationOptions()

    @property
    def options(self) -> GenerationOptions:
        """The effective description settings: defaults, then the caller's."""
        return DESCRIBE_DEFAULTS.merged(self._options)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def describe(self, image_bytes: bytes, mime_type: str, prompt: str) -> DescriptionResult:
        import ollama

        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        client = ollama.Client(host=self._host, timeout=self.DESCRIBE_TIMEOUT_SECONDS)
        opts = self.options
        think = resolve_think(opts.thinking, self._model, host=self._host)
        options = request_options(opts, self._model, think=think)

        def ask(request_opts: dict):
            kwargs = {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt, "images": [b64]}],
            }
            if request_opts:
                kwargs["options"] = request_opts
            if think is not None:
                kwargs["think"] = think
            return client.chat(**kwargs)

        response = ask(options)
        text, thinking = _answer_parts(response)
        input_tokens = getattr(response, "prompt_eval_count", None) or 0
        output_tokens = getattr(response, "eval_count", None) or 0

        if not text.strip() and thinking:
            # All reasoning, no description: the model spent its output on
            # thinking (seen with qwen3-vl:2b after 13,000 characters of it).
            # Saving the blank would look like success. Retry once, without
            # the cap if there was one, since that is the likeliest cause.
            logger.warning(
                "%s returned reasoning (%d characters) but no description; retrying%s",
                self._model, len(thinking),
                " without num_predict" if "num_predict" in options else "")
            retry_opts = {k: v for k, v in options.items() if k != "num_predict"}
            response = ask(retry_opts)
            text, thinking = _answer_parts(response)
            input_tokens += getattr(response, "prompt_eval_count", None) or 0
            output_tokens += getattr(response, "eval_count", None) or 0
            if not text.strip():
                raise EmptyDescriptionError(
                    f"{self._model} spent its whole reply on hidden reasoning and wrote "
                    f"no description, twice. Thinking models are slow and unreliable "
                    f"for descriptions; try a non-thinking model, such as an "
                    f"'-instruct' tag of the same model.")

        if thinking and think is False:
            key = (self._host, self._model)
            if key not in _WARNED_IGNORED_THINK:
                _WARNED_IGNORED_THINK.add(key)
                logger.warning(
                    "%s kept thinking although thinking was turned off (%d characters "
                    "of hidden reasoning for this image). This model ignores the "
                    "setting; descriptions will be slow. A non-thinking edition, "
                    "usually the '-instruct' tag, avoids it.", self._model, len(thinking))

        if thinking:
            # Recorded per image so a slow run can be explained from the log.
            logger.info("%s: %d characters of hidden reasoning (discarded), "
                        "%d-character description, %s output tokens",
                        self._model, len(thinking), len(text), output_tokens or "?")

        truncated = getattr(response, "done_reason", None) == "length"
        if truncated:
            logger.warning("%s stopped at its output limit; the description is cut off",
                           self._model)

        return DescriptionResult(
            text=text,
            model=self._model,
            provider="ollama",
            input_tokens=input_tokens or None,
            output_tokens=output_tokens or None,
            thinking_chars=len(thinking),
            truncated=truncated,
        )

    def list_models(self) -> list[str]:
        """Return names of vision-capable models available in this Ollama instance.

        Models without vision must not be offered for description. Ollama accepts
        an attached image for them and silently discards it, so the model writes a
        confident description from the prompt alone — a photo of boats at a dock
        came back as "a woman standing next to a white Porsche 911" (issue #227).
        Fluent, wrong, and nothing signals it.
        """
        import ollama
        client = ollama.Client(host=self._host)
        try:
            models = client.list()
        except Exception:
            return []

        out: list[str] = []
        for m in models.models:
            if model_has_vision(m.model, host=self._host, client=client):
                out.append(m.model)
        return out

    def list_chat_models(self) -> list[str]:
        """Names of chat-capable models — the picker filter for *chat*, where
        text-only models are often the strongest ones installed.

        The vision filter in :meth:`list_models` exists so describe never
        hands an image to a model that would silently discard it (issue #227);
        applying it to the chat picker hid every text-only model for no
        reason. Chat needs `completion`, nothing more.
        """
        import ollama
        client = ollama.Client(host=self._host)
        try:
            models = client.list()
        except Exception:
            return []

        return [
            m.model
            for m in models.models
            if model_is_chat_capable(m.model, host=self._host, client=client)
        ]
