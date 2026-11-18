"""
The usage line ImageDescriber appends to a description, and removing it.

ImageDescriber's worker (``imagedescriber/workers_wx.py``,
``_add_token_usage_info``) appends one bracketed line to every AI
description it stores::

    <description>

    [Token Usage: 4,196 total (3,000 prompt + 1,196 completion) | Time: 8.12s]

Either part may be absent, so ``[Token Usage: …]`` and ``[Time: 8.12s]`` on
their own are both possible. The line is deliberate: it stays in the stored
text and in ImageDescriber's own reading views (description list, editor,
Viewer mode). Everywhere the text leaves those views (exports, embedded
metadata, the clipboard) it is removed with :func:`strip_usage_line`.

The location byline at the start ("City, State - ") is description content and
is never touched here.

wx-free so the CLI, idt_core and the GUI can all share it.
"""
from __future__ import annotations

import re

# The last line alone: "[Token Usage: …]", "[Time: …]" or
# "[Token Usage: … | Time: …]". Only the last line is ever examined, so a
# description that ends in thousands of blank lines (a small model looping
# until its token limit) costs one pass, not a regex search that rescans the
# blank lines from every newline, which took seconds (#489 review).
_USAGE_LINE_RE = re.compile(r"\[(?:Token Usage:|Time:)[^\]\n]*\]")


def strip_usage_line(text: str | None) -> str:
    """Return *text* without ImageDescriber's trailing usage line.

    Removes ``[Token Usage: …]``, ``[Time: …]`` or both joined by ``|``,
    only when it is the last thing in the text and set off by a blank line,
    together with the whitespace around it. Any other text, including a
    bracketed phrase elsewhere in the description, is returned unchanged
    (trailing whitespace is left alone when there is no usage line).

    ``None`` is returned as ``""``.
    """
    if not text:
        return text or ""
    body = text.rstrip()
    cut = body.rfind("\n")
    if cut < 0 or not _USAGE_LINE_RE.fullmatch(body[cut + 1:].strip(" \t\r")):
        return text
    before = body[:cut].rstrip(" \t\r")
    # Set off by a blank line: what comes before must end in a newline once
    # the line's own spaces are gone.
    if not before.endswith("\n"):
        return text
    return before.rstrip()
