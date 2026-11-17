"""
OpenAI provider (GPT-4o, GPT-4o-mini, o1).
Reads OPENAI_API_KEY from the environment.
"""
from __future__ import annotations

import base64
import re
from typing import Iterable, List, Optional, Sequence

from .base import BaseProvider, DescriptionResult

# The list below is no longer the source of truth for *which* models exist --
# `catalog.py` asks the API that, and this list is the offline fallback plus the
# metadata layer (issue #267). It is still the source of truth for
# context_window / max_output / cost / recommended, and for display order.
#
# Updated July 2026.
DEFAULT_MODEL = "gpt-5.2"

OPENAI_MODELS = [
    # Current generation — GPT-5.x
    "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-5-nano",
    # Reasoning models
    "o4-mini", "o3",
    # Legacy (still functional, users may have old descriptions referencing them)
    "gpt-4o", "gpt-4o-mini",
    "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
    "o1",
]

# context_window / max_output are the platform-documented figures. They feed
# the chat token budgeter and the context gauge; before they were recorded,
# registry.model_limits() returned (None, None) for every OpenAI model and
# budgeting fell back to a flat 128k guess regardless of model.
OPENAI_MODEL_METADATA: dict = {
    # --- GPT-5.x --- (400k context, 128k max output across the family)
    "gpt-5.2": {"name": "GPT-5.2", "description": "Best available model — highest quality vision and reasoning.", "cost": "$$$$", "supports_vision": True, "recommended": True,
                "context_window": 400_000, "max_output": 128_000},
    "gpt-5.1": {"name": "GPT-5.1", "description": "High-quality GPT-5 with strong reasoning.", "cost": "$$$", "supports_vision": True, "recommended": False,
                "context_window": 400_000, "max_output": 128_000},
    "gpt-5": {"name": "GPT-5", "description": "Flagship GPT-5 reasoning model.", "cost": "$$$", "supports_vision": True, "recommended": False,
              "context_window": 400_000, "max_output": 128_000},
    "gpt-5-mini": {"name": "GPT-5 Mini", "description": "Faster, efficient GPT-5.", "cost": "$$", "supports_vision": True, "recommended": False,
                   "context_window": 400_000, "max_output": 128_000},
    "gpt-5-nano": {"name": "GPT-5 Nano", "description": "Fastest and most affordable GPT-5.", "cost": "$", "supports_vision": True, "recommended": False,
                   "context_window": 400_000, "max_output": 128_000},
    # --- Reasoning models ---
    "o4-mini": {"name": "O4 Mini", "description": "Fast cost-efficient reasoning.", "cost": "$$", "supports_vision": True, "recommended": False,
                "context_window": 200_000, "max_output": 100_000},
    "o3": {"name": "O3", "description": "Powerful reasoning for complex tasks.", "cost": "$$$", "supports_vision": True, "recommended": False,
           "context_window": 200_000, "max_output": 100_000},
    # --- Legacy (still functional) ---
    "gpt-4o": {"name": "GPT-4o", "description": "Legacy — still works well for vision tasks.", "cost": "$$", "supports_vision": True, "recommended": False,
               "context_window": 128_000, "max_output": 16_384},
    "gpt-4o-mini": {"name": "GPT-4o Mini", "description": "Legacy — affordable and fast.", "cost": "$", "supports_vision": True, "recommended": False,
                    "context_window": 128_000, "max_output": 16_384},
    "gpt-4.1": {"name": "GPT-4.1", "description": "Legacy — last non-reasoning GPT-4 generation.", "cost": "$$", "supports_vision": True, "recommended": False,
                "context_window": 1_047_576, "max_output": 32_768},
    "gpt-4.1-mini": {"name": "GPT-4.1 Mini", "description": "Legacy — compact GPT-4.1.", "cost": "$", "supports_vision": True, "recommended": False,
                     "context_window": 1_047_576, "max_output": 32_768},
    "gpt-4.1-nano": {"name": "GPT-4.1 Nano", "description": "Legacy — ultra-budget GPT-4.1.", "cost": "$", "supports_vision": True, "recommended": False,
                     "context_window": 1_047_576, "max_output": 32_768},
    "o1": {"name": "O1", "description": "Legacy — original full reasoning model.", "cost": "$$$", "supports_vision": True, "recommended": False,
           "context_window": 200_000, "max_output": 100_000},
}


def get_openai_model_info(model_id: str) -> dict:
    return OPENAI_MODEL_METADATA.get(model_id, {"name": model_id, "supports_vision": True})


# ---------------------------------------------------------------------------
# Generation settings (issue #392)
# ---------------------------------------------------------------------------

def is_reasoning_model(model_id: str) -> bool:
    """True for OpenAI's reasoning families: the o-series and GPT-5 onward.

    They reason before answering, count that against the output cap, accept
    ``reasoning_effort``, and reject a non-default ``temperature``/``top_p``.
    A rule rather than a list, so gpt-6 and later models are covered on the
    day they appear in the live catalog; send_with_fallback catches the cases
    a rule gets wrong.
    """
    import re

    name = (model_id or "").lower()
    if re.match(r"o\d", name):
        return True
    match = re.match(r"gpt-(\d+)", name)
    return bool(match) and int(match.group(1)) >= 5


#: Description cap when the user sets none. Reasoning counts against it, so it
#: has to leave room: ImageDescriber's old 300 cut descriptions off, and its
#: 1500 was measured against a 192-token reasoning budget at default effort.
DESCRIBE_MAX_OUTPUT_TOKENS = 4096

#: Parameters dropped and retried without when the API rejects them.
OPTIONAL_PARAMS = ("temperature", "top_p", "reasoning_effort")


def describe_request_params(model: str, opts) -> dict:
    """Chat-completions keyword arguments (all but ``messages``) for a description.

    Shared by idt_core's provider and ImageDescriber's, so the two cannot drift
    apart again: the CLI sent ``max_tokens`` -- which reasoning models reject --
    while ImageDescriber capped other models at 300 tokens.
    """
    from ..generation import THINKING_OFF, GenerationOptions, note_dropped

    opts = opts or GenerationOptions()
    reasoning = is_reasoning_model(model)
    # max_completion_tokens, never max_tokens: every current chat model takes
    # it, and reasoning models reject max_tokens outright.
    params = {"model": model,
              "max_completion_tokens": opts.max_output_tokens or DESCRIBE_MAX_OUTPUT_TOKENS}
    for setting in ("temperature", "top_p"):
        value = getattr(opts, setting)
        if value is None:
            continue
        if reasoning:
            note_dropped("openai", model, setting,
                         "reasoning models accept only their default")
        else:
            params[setting] = value
    for setting in ("top_k", "repeat_penalty"):
        if getattr(opts, setting) is not None:
            note_dropped("openai", model, setting, "OpenAI has no such setting")

    effort = opts.effort
    if reasoning and (effort == "minimal" or
                      (effort is None and opts.thinking == THINKING_OFF)):
        # "As little reasoning as possible", in each family's own word. Sending
        # "low" to GPT-5.1+, whose default is "none", would make it reason
        # *more*; "minimal" exists only on the original GPT-5 models.
        effort = lowest_effort(model)
    if effort is not None:
        if reasoning:
            params["reasoning_effort"] = effort
        else:
            note_dropped("openai", model, "effort", "the model does not reason")
    elif opts.thinking is not None and not reasoning:
        note_dropped("openai", model, "thinking", "the model does not reason")
    if "temperature" in params and params["temperature"] > 2:
        note_dropped("openai", model, "temperature", "OpenAI accepts 0 to 2")
        params.pop("temperature")
    extra = dict(opts.extra or {})
    if extra:
        # Request body, not SDK keyword arguments: an unknown keyword is a
        # TypeError that fails every image (see claude._extra_body).
        params["extra_body"] = extra
    return params


def lowest_effort(model_id: str) -> str:
    """The least reasoning a model takes: "minimal" on the original GPT-5
    models, "none" on GPT-5.1 and later, "low" on the o-series. A model that
    rejects it is retried at "low" (see EFFORT_FALLBACK)."""
    import re

    name = (model_id or "").lower()
    if re.match(r"gpt-5(-mini|-nano)?(-\d{4}-\d{2}-\d{2})?$", name):
        return "minimal"
    if re.match(r"o\d", name):
        return "low"
    return "none"


#: A rejected reasoning_effort value is retried at these before the parameter
#: is dropped -- dropping it means the model's default, usually more reasoning.
EFFORT_FALLBACK = {"reasoning_effort": ("low",)}


def empty_answer_error(model: str, choice, cap: int, hidden: Optional[int]) -> Exception:
    """The error for a choice with no description text, by why it stopped.

    Every empty answer is an error: saving the blank would mark the picture
    described. A refusal or content filter is about the picture, so it is a
    DeclinedError, which the pipeline remembers and does not stop the run on.
    """
    from .base import DeclinedError, EmptyAnswerError

    finish_reason = getattr(choice, "finish_reason", None)
    refusal = getattr(getattr(choice, "message", None), "refusal", None)
    if refusal or finish_reason == "content_filter":
        return DeclinedError(f"OpenAI ({model}) declined to describe this picture"
                             + (f": {refusal}" if refusal else "."))
    if finish_reason == "length":
        return EmptyAnswerError(
            f"OpenAI ({model}) used its whole output allowance ({cap} tokens"
            + (f", {hidden} of them reasoning" if hidden else "")
            + ") before writing a description. Raise the output limit or lower the "
              "reasoning effort in the generation settings.")
    return EmptyAnswerError(
        f"OpenAI ({model}) returned no description (finish reason: {finish_reason or 'none'}).")


def reasoning_tokens(usage) -> Optional[int]:
    """Hidden reasoning tokens from a chat-completions usage object, or None."""
    details = getattr(usage, "completion_tokens_details", None)
    value = getattr(details, "reasoning_tokens", None) if details is not None else None
    return value if isinstance(value, int) else None


# ---------------------------------------------------------------------------
# Live listing
# ---------------------------------------------------------------------------
#
# `GET /v1/models` returns everything the account can reach -- around eighty
# entries, most of which are not chat models at all, plus a dated snapshot
# alongside nearly every base id. Dropping a picker of that size in front of
# someone arrowing through it with a screen reader would be worse than the stale
# list this replaces, so the response is filtered before it is offered.

#: Whole tokens that mean "not a chat model". Matched against the id split on
#: `-` and `.`, never as substrings: a substring test for "audio" or "image"
#: would drop a future `gpt-6-audio-native` flagship, which is precisely the
#: kind of silent omission issue #267 exists to fix. `idt models --all` shows
#: everything when this filter is wrong.
#
# "vision" is deliberately absent from this set: `gpt-4-vision-preview` is a
# chat model, and for an image-description app it is one of the last ones we
# would want to hide.
_NON_CHAT_TOKENS = frozenset({
    "embedding", "embeddings", "similarity",
    "tts", "whisper", "transcribe", "audio", "realtime", "voice",
    "dall", "image", "sora", "moderation",
    "davinci", "babbage", "curie", "ada", "instruct",
})
# "search", "codex", "pro", "chat" and "deep" are all deliberately absent:
# `gpt-4o-search-preview`, `gpt-5.3-codex`, `gpt-5-pro`, `gpt-5-chat-latest` and
# `o4-mini-deep-research` all answer chat completions perfectly well. Verified
# against a real account listing (126 ids in, 47 out) rather than guessed --
# every one of those would have been a model the user could call and IDT would
# not have offered.

#: A trailing release date: `-2024-08-06` or `-20240806`.
_DATED = re.compile(r"^(?P<base>.+?)-(?P<date>\d{4}-\d{2}-\d{2}|\d{8})$")

#: A trailing four-digit MMDD snapshot: `gpt-4-0613`, `gpt-3.5-turbo-0125`.
#: Handled more cautiously than a full date -- four digits are ambiguous enough
#: that a future `gpt-5-1000` could match -- so this form only ever *collapses*
#: into an existing base id and never drives the "keep the newest" branch.
_SHORT_DATED = re.compile(r"^(?P<base>.+?)-(?P<date>\d{4})$")


def _normalise_date(value: str) -> str:
    """`20240806` -> `2024-08-06`, so both spellings sort and group together.

    Without this, one family spelled both ways becomes two groups and the
    collapse silently does nothing for it.
    """
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


def _is_non_chat(model_id: str) -> bool:
    tokens = {t for t in re.split(r"[-.]", model_id.lower()) if t}
    return bool(tokens & _NON_CHAT_TOKENS)


def filter_chat_model_ids(
    ids: Iterable[str],
    *,
    curated: Sequence[str] = (),
    keep: Iterable[str] = (),
) -> List[str]:
    """Reduce a raw `/v1/models` listing to what belongs in a picker.

    Order of operations matters, and the first rule is the safety net for the
    other two:

    1. **Curated ids and ``keep`` ids always survive.** Whatever the patterns
       below decide, a model we ship metadata for -- or one the user has already
       selected -- is never removed. A filter that can drop the user's saved
       model would change their selection with no message anywhere.
    2. **Non-chat ids go**, by whole-token match (see ``_NON_CHAT_TOKENS``).
    3. **Dated snapshots collapse.** When `gpt-4o` is present, every
       `gpt-4o-YYYY-MM-DD` is hidden behind it. When the base is *absent*, the
       newest snapshot is kept rather than the family vanishing entirely --
       otherwise a model offered only as a pinned snapshot would disappear from
       the picker, which is the failure mode most likely to bite in practice.

    ``ft:`` fine-tunes are kept: a fine-tune of a vision model is a perfectly
    good chat model. They sort last, after everything else.

    Returns ``[]`` for an empty input; the caller treats that as a failed fetch
    rather than as "this account has no models".
    """
    ordered = [str(i) for i in ids if i]
    protected = set(curated) | {k for k in keep if k}
    present = set(ordered)

    survivors = [
        model_id for model_id in ordered
        if model_id in protected or not _is_non_chat(model_id)
    ]

    # Group the dated variants so we can tell "collapse behind the base" from
    # "this family only exists as snapshots".
    newest_of: dict = {}
    for model_id in survivors:
        match = _DATED.match(model_id)
        if not match:
            continue
        base = match.group("base")
        date = _normalise_date(match.group("date"))
        if base not in present:
            current = newest_of.get(base)
            if current is None or date > current[0]:
                newest_of[base] = (date, model_id)

    out: List[str] = []
    fine_tunes: List[str] = []
    for model_id in survivors:
        if model_id.startswith("ft:"):
            fine_tunes.append(model_id)
            continue
        if model_id in protected:
            out.append(model_id)
            continue

        match = _DATED.match(model_id)
        if match:
            base = match.group("base")
            if base in present:
                continue                          # collapsed behind the base id
            if newest_of.get(base, (None, None))[1] != model_id:
                continue                          # an older snapshot of a base-less family
            out.append(model_id)
            continue

        short = _SHORT_DATED.match(model_id)
        if short and short.group("base") in present:
            continue                              # legacy MMDD snapshot, base present

        out.append(model_id)

    return out + fine_tunes


# Alias kept for import compatibility
DEV_OPENAI_MODELS = OPENAI_MODELS


def list_models_live(client=None, api_key: Optional[str] = None,
                     timeout: float = 8.0, *, keep: Iterable[str] = (),
                     include_all: bool = False) -> List[dict]:
    """Ask the API which OpenAI models this account can use.

    Returns ``{"id", "name", "created"}`` records for ``catalog`` to merge. The
    endpoint reports no display name, so ``name`` is empty and the catalog falls
    back to the id -- which is what every OpenAI picker in this app has always
    shown anyway.

    ``include_all`` bypasses :func:`filter_chat_model_ids`, backing
    ``idt models --all`` for when the filter is hiding something it should not.

    Raises rather than swallowing, for the same reason as the Claude fetcher:
    the caller cannot tell a failure from an empty account otherwise.
    """
    if client is None:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=timeout)

    response = client.models.list()
    records = {}
    for model in getattr(response, "data", None) or []:
        model_id = str(getattr(model, "id", "") or "")
        if not model_id:
            continue
        created = getattr(model, "created", None)
        try:
            created = float(created) if created is not None else 0.0
        except (TypeError, ValueError):
            created = 0.0
        records[model_id] = {"id": model_id, "name": "", "created": created}

    if include_all:
        wanted = list(records)
    else:
        wanted = filter_chat_model_ids(
            records, curated=OPENAI_MODELS, keep=keep
        )
    return [records[model_id] for model_id in wanted]


class OpenAIProvider(BaseProvider):
    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None,
                 options=None):
        try:
            from openai import OpenAI  # noqa: F401
        except ImportError:
            raise ImportError(
                "openai package is required: pip install openai"
            )
        from openai import OpenAI
        self._model = model
        #: GenerationOptions; None means automatic.
        self._options = options
        # No key given: the shared lookup (environment, then the credential store
        # Configure saves to, then the config file). Leaving it to the SDK read
        # only OPENAI_API_KEY, so `idt describe` failed with "Missing
        # credentials" for a key saved in Configure (real-service check, 11/16/2026).
        if not api_key:
            from ..keys import resolve_api_key
            api_key = resolve_api_key("openai")
        self._client = OpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def describe(self, image_bytes: bytes, mime_type: str, prompt: str) -> DescriptionResult:
        from ..generation import send_with_fallback, with_extra_body

        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        params = describe_request_params(self._model, self._options)
        params["messages"] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        response = send_with_fallback(self._client.chat.completions.create, params,
                                      with_extra_body(OPTIONAL_PARAMS, params),
                                      "openai", self._model, EFFORT_FALLBACK)
        usage = response.usage
        choice = response.choices[0]
        text = choice.message.content or ""
        finish_reason = getattr(choice, "finish_reason", None)
        truncated = finish_reason == "length"
        hidden = reasoning_tokens(usage)
        if not text.strip():
            raise empty_answer_error(self._model, choice, params["max_completion_tokens"],
                                     hidden)
        return DescriptionResult(
            text=text,
            model=self._model,
            provider="openai",
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            thinking_tokens=hidden,
            truncated=truncated,
        )
