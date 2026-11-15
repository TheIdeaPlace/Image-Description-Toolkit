"""
Generation options: what IDT asks a model for besides the prompt (issue #392).

The rule this module encodes: **the user picks a provider and a model; IDT
supplies sensible defaults for everything else, and anyone who wants to can
override any of it.** It is deliberately not one-size-fits-all. Every field
defaults to ``None``, meaning "automatic", and each provider decides what
automatic means for the model in hand. A field the provider or model cannot
take is dropped by that provider, with a log line, rather than sent to fail.

Where the values come from, lowest priority first:

1. The provider's built-in defaults for the model and the purpose
   (``describe`` or ``chat``). For example, Ollama descriptions default to
   thinking off, because the reasoning is thrown away and on a thinking model
   it is most of the time spent per image.
2. The user's settings, per provider, in ``image_describer_config.json``
   under ``"generation"``. Shared by the CLI and ImageDescriber, like the
   prompt library in the same file::

       "generation": {
         "ollama": {"thinking": "off", "temperature": 0.2},
         "openai": {"effort": "low"}
       }

3. Explicit overrides from the caller, e.g. ``idt describe --no-think``.

The older ``model_settings`` / ``prompt_model_settings`` keys in the same file
are **not** read. Nothing has applied them since 6/23/2026 (and ImageDescriber
never did); their values were tuned for 2025 models, and applying them now
would cut descriptions short (``num_predict: 500`` for ``narrative`` truncates
current 30B models) and change sampling under everyone at once.

Kept free of wx and of vendor SDKs, like the rest of ``idt_core``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields, replace
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

#: Thinking modes. ``auto`` = the model's own default; ``on``/``off`` = asked for.
THINKING_AUTO = "auto"
THINKING_ON = "on"
THINKING_OFF = "off"
THINKING_MODES = (THINKING_AUTO, THINKING_ON, THINKING_OFF)

#: Reasoning effort levels, in increasing order. Providers map these onto their
#: own scales and drop the field where the model has none.
EFFORT_LEVELS = ("minimal", "low", "medium", "high")

#: Purposes a provider may default differently for.
PURPOSE_DESCRIBE = "describe"
PURPOSE_CHAT = "chat"

#: Accepted spellings in settings files, mapped to field names. ``num_predict``
#: is Ollama's name and ``max_tokens`` the OpenAI/Claude one; people copy
#: whichever they know.
_ALIASES = {
    "num_predict": "max_output_tokens",
    "max_tokens": "max_output_tokens",
    "max_completion_tokens": "max_output_tokens",
    "think": "thinking",
    "reasoning_effort": "effort",
}


@dataclass(frozen=True)
class GenerationOptions:
    """Provider-neutral generation settings. ``None`` everywhere = automatic."""

    max_output_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repeat_penalty: Optional[float] = None
    #: One of THINKING_MODES, or None for the provider's default for the purpose.
    thinking: Optional[str] = None
    #: One of EFFORT_LEVELS, or None.
    effort: Optional[str] = None
    #: Raw provider-specific options passed through as-is, for experts (for
    #: Ollama, extra keys in the request's ``options``, e.g. ``num_ctx``).
    extra: Mapping[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #

    def merged(self, override: Optional["GenerationOptions"]) -> "GenerationOptions":
        """A copy with every field ``override`` sets taking precedence."""
        if override is None:
            return self
        changes: dict[str, Any] = {}
        for f in fields(self):
            if f.name == "extra":
                continue
            value = getattr(override, f.name)
            if value is not None:
                changes[f.name] = value
        if override.extra:
            changes["extra"] = {**dict(self.extra), **dict(override.extra)}
        return replace(self, **changes)

    def is_automatic(self) -> bool:
        return self == GenerationOptions()

    @classmethod
    def from_dict(cls, data: Optional[Mapping[str, Any]]) -> "GenerationOptions":
        """Build from a settings dict, tolerating aliases and bad values.

        A value that cannot be used is skipped with a warning, never raised:
        a typo in a settings file must not stop a batch of 1,800 images.
        ``None`` and ``""`` mean automatic.
        """
        if not data:
            return cls()
        known = {f.name for f in fields(cls)}
        values: dict[str, Any] = {}
        extra: dict[str, Any] = {}
        for raw_key, raw_value in data.items():
            key = _ALIASES.get(str(raw_key), str(raw_key))
            if raw_value is None or raw_value == "":
                continue
            if key == "extra":
                if isinstance(raw_value, Mapping):
                    extra.update(raw_value)
                continue
            if key not in known:
                # Unknown keys go to the provider untouched, so a new Ollama
                # option works without an IDT release.
                extra[str(raw_key)] = raw_value
                continue
            try:
                values[key] = _coerce(key, raw_value)
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring generation setting %s=%r: %s", raw_key, raw_value, exc)
        return cls(**values, extra=extra)

    def to_dict(self) -> dict[str, Any]:
        """Only the fields that are set, for saving and for logs."""
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name == "extra":
                if value:
                    out["extra"] = dict(value)
            elif value is not None:
                out[f.name] = value
        return out


def _coerce(key: str, value: Any) -> Any:
    if key in ("max_output_tokens", "top_k"):
        if isinstance(value, bool):
            raise ValueError("expected a whole number")
        number = int(value)
        if number <= 0:
            # Ollama treats -1 as "no limit"; here that is simply automatic,
            # which callers express as None. Reject rather than guess.
            raise ValueError("must be greater than 0")
        return number
    if key in ("temperature", "top_p", "repeat_penalty"):
        if isinstance(value, bool):
            raise ValueError("expected a number")
        number = float(value)
        if number < 0:
            raise ValueError("must not be negative")
        return number
    if key == "thinking":
        if isinstance(value, bool):
            return THINKING_ON if value else THINKING_OFF
        text = str(value).strip().lower()
        text = {"true": THINKING_ON, "false": THINKING_OFF, "none": THINKING_AUTO,
                "default": THINKING_AUTO, "automatic": THINKING_AUTO}.get(text, text)
        if text not in THINKING_MODES:
            raise ValueError(f"expected one of {', '.join(THINKING_MODES)}")
        return text
    if key == "effort":
        text = str(value).strip().lower()
        if text not in EFFORT_LEVELS:
            raise ValueError(f"expected one of {', '.join(EFFORT_LEVELS)}")
        return text
    return value


def think_flag(mode: Optional[str]) -> Optional[bool]:
    """THINKING_* (or None) as the tri-state bool chat requests carry."""
    if mode == THINKING_ON:
        return True
    if mode == THINKING_OFF:
        return False
    return None


def thinking_mode(flag: Optional[bool]) -> str:
    """The inverse of :func:`think_flag`."""
    if flag is True:
        return THINKING_ON
    if flag is False:
        return THINKING_OFF
    return THINKING_AUTO


# --------------------------------------------------------------------------- #
# Dropped settings and rejected parameters                                     #
# --------------------------------------------------------------------------- #

#: Notices go to a logger under idt_core.providers, which the run log captures
#: while a run is open (idt_core/logger.py).
_options_log = logging.getLogger("idt_core.providers.options")
_NOTED: set = set()


def note_dropped(provider: str, model: str, setting: str, reason: str) -> None:
    """Log, once per (provider, model, setting), that a setting was not sent.

    The promise this module makes is that a setting the provider or model
    cannot take is skipped and the log says so -- never sent to fail the
    request, never silently ignored.
    """
    key = (provider, model, setting)
    if key in _NOTED:
        return
    _NOTED.add(key)
    _options_log.info("%s %s: not sending %s (%s)", provider, model, setting, reason)


# (provider, model, parameter) the API has rejected in this process, so later
# requests leave it out instead of failing once per image.
_REJECTED: set = set()


def _is_rejection_of(exc: BaseException, needles) -> bool:
    status = getattr(exc, "status_code", None)
    if status not in (400, 422):
        return False
    text = str(exc)
    return any(needle in text for needle in needles)


def _as_needles(optional) -> dict:
    return dict(optional) if isinstance(optional, Mapping) else {p: (p,) for p in optional}


def with_extra_body(optional, params: dict) -> dict:
    """``optional`` plus ``extra_body``, identified by its own keys.

    Unknown settings from the user's file travel in ``extra_body``; if the API
    rejects one, the request goes again without them rather than failing the
    batch over a typo.
    """
    needles = _as_needles(optional)
    extra = params.get("extra_body")
    if extra:
        needles["extra_body"] = tuple(str(k) for k in extra)
    return needles


#: Words in a 400 that mean a *value* was wrong rather than the parameter
#: unsupported. Such a rejection is not remembered: once the user fixes the
#: value, it should be sent again without restarting the app.
_VALUE_PROBLEM_WORDS = ("unsupported value", "invalid value", "must be", "less than",
                        "greater than", "out of range", "between")


def send_with_fallback(call, params: dict, optional, provider: str, model: str):
    """``call(**params)``, retrying without any optional parameter the API rejects.

    Model capabilities change faster than IDT releases: OpenAI's reasoning
    models reject ``temperature``, older Claude models reject ``effort``, and a
    new model may reject something today's table says it takes. Rather than
    trust a table, an optional parameter that comes back as a 400 naming it is
    dropped (with a note) and the request sent again. Only the parameters in
    ``optional`` are ever dropped; a 400 about anything else is raised.

    ``optional`` is either parameter names, or a mapping of parameter name to
    the words that identify it in an error (``{"output_config": ("effort",
    "output_config")}``), for APIs that name a nested field.
    """
    needles = _as_needles(optional)
    params = dict(params)
    for parameter in needles:
        if (provider, model, parameter) in _REJECTED and parameter in params:
            params.pop(parameter)
    while True:
        try:
            return call(**params)
        except Exception as exc:                                 # noqa: BLE001
            culprit = next((p for p, words in needles.items()
                            if p in params and _is_rejection_of(exc, words)), None)
            if culprit is None:
                raise
            text = str(exc).lower()
            if not any(word in text for word in _VALUE_PROBLEM_WORDS):
                _REJECTED.add((provider, model, culprit))
            _options_log.info("%s %s: sending again without %s, which was rejected: %s",
                              provider, model, culprit, exc)
            params.pop(culprit)


# --------------------------------------------------------------------------- #
# User settings                                                                #
# --------------------------------------------------------------------------- #

#: The settings key in image_describer_config.json.
CONFIG_KEY = "generation"


def _load_config() -> dict:
    try:
        from idt_core.config_loader import load_json_config
    except ImportError:
        try:
            from config_loader import load_json_config          # frozen mode
        except ImportError:
            return {}
    try:
        loaded = load_json_config("image_describer_config.json")
    except Exception:                                            # noqa: BLE001
        return {}
    config = loaded[0] if isinstance(loaded, tuple) else loaded
    return config if isinstance(config, dict) else {}


def user_options(provider: str, config: Optional[Mapping[str, Any]] = None) -> GenerationOptions:
    """The user's saved settings for ``provider`` (automatic when none).

    ``config`` is the parsed image_describer_config.json; when omitted it is
    loaded through config_loader, so the CLI and the GUI read the same file.
    """
    if config is None:
        config = _load_config()
    section = (config or {}).get(CONFIG_KEY) or {}
    if not isinstance(section, Mapping):
        return GenerationOptions()
    return GenerationOptions.from_dict(section.get(provider) or {})
