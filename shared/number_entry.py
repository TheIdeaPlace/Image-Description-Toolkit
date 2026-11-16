"""Checking a number typed into a settings field. No wx imports, so it's testable alone.

Used by Configure (#405), and by the video extraction and Download dialogs
(#406). Each refuses a bad entry with a message naming the range, instead of
saving something else without a word: a plain number field saved "abc" as
0.0, "max frames" saved it as unlimited, and a spin box clamped a typed 150
to its maximum as soon as focus left it.
"""
from __future__ import annotations

import math
from typing import Any, Dict

#: One range per setting wherever it's typed: Configure and the video extraction
#: dialog disagreed (0.5-30 against 0.1-60 seconds; 10-50 against 1-100).
VIDEO_INTERVAL_RANGE = (0.5, 60.0)
SCENE_THRESHOLD_RANGE = (1.0, 100.0)

#: Setting types typed as numbers. Every one is checked on OK (validate_number).
NUMBER_TYPES = ("float", "int", "int_or_null", "float_or_auto", "int_or_auto")
WHOLE_NUMBER_TYPES = ("int", "int_or_null", "int_or_auto")
#: What an empty entry means, for the types where empty is allowed.
EMPTY_MEANS = {"float_or_auto": "Automatic", "int_or_auto": "Automatic",
               "int_or_null": "no limit"}
#: Words that mean the same as empty. A setting whose old way to say "no
#: limit" was -1 (Download's Maximum images) says so with "minus_one_empty".
EMPTY_WORDS = {"float_or_auto": ("auto", "automatic"),
               "int_or_auto": ("auto", "automatic"),
               "int_or_null": ("null", "none", "unlimited")}


def _n(value) -> str:
    """A number as a person says it: 30.0 is "30", 0.5 stays "0.5"."""
    return f"{value:g}" if isinstance(value, float) else str(value)


def validate_number(setting_info: Dict[str, Any], text: str):
    """``(value, error)`` for a number typed into a setting.

    ``setting_info`` has a "type" from NUMBER_TYPES and usually a "range"
    (low, high). ``error`` is the message to show, or None; ``value`` is None
    for an empty entry where empty is allowed. Text that isn't a number, a
    fraction where a whole number is needed, NaN or infinity, and anything
    outside the range are refused.
    """
    kind = setting_info.get("type")
    text = (text or "").strip()
    empty_means = EMPTY_MEANS.get(kind)
    if empty_means and (text == "" or text.lower() in EMPTY_WORDS[kind]
                        or (text == "-1" and setting_info.get("minus_one_empty"))):
        return None, None

    low, high = setting_info.get("range", (None, None))
    span = f" from {_n(low)} to {_n(high)}" if low is not None else ""
    tail = f", or leave it empty for {empty_means}." if empty_means else "."
    whole = kind in WHOLE_NUMBER_TYPES
    word = "a whole number" if whole else "a number"
    try:
        value = int(text) if whole else float(text)
    except ValueError:
        return None, f"Enter {word}{span}{tail}"
    if not whole and not math.isfinite(value):
        return None, f"Enter {word}{span}{tail}"
    if low is not None and not (low <= value <= high):
        return None, f"Enter {word}{span}{tail}"
    return value, None


def spoken_range(setting_info: Dict[str, Any]) -> str:
    """", 0.5 to 60.0" (plus what empty means), for a number field's name.

    The range goes in the name because a "Range:" line or a hint beside the
    field is static text JAWS and NVDA don't read when the field gets focus.
    """
    kind = setting_info.get("type")
    if kind not in NUMBER_TYPES or "range" not in setting_info:
        return ""
    low, high = setting_info["range"]
    text = f", {_n(low)} to {_n(high)}"
    if kind in EMPTY_MEANS:
        text += f", or empty for {EMPTY_MEANS[kind]}"
    return text
