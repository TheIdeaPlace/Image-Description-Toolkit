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
Viewer mode, Show All Descriptions). Everywhere the text leaves those views
(exports, embedded metadata, the clipboard, text sent back to a model) it is
removed with :func:`strip_usage_line`.

The location byline at the start ("City, State - ") is description content and
is never touched here.

wx-free so the CLI, idt_core and the GUI can all share it.
"""
from __future__ import annotations

import re

# One blank line, then "[Token Usage: …]", "[Time: …]" or
# "[Token Usage: … | Time: …]", then only whitespace to the end of the text.
# [^\]\n]* keeps the match inside a single bracketed line, so a bracket earlier
# in the description is never mistaken for the start of the usage line.
_USAGE_LINE_RE = re.compile(
    r"\n\s*\n[ \t]*\[(?:Token Usage:[^\]\n]*|Time:[^\]\n]*)\][ \t\r\n]*\Z"
)


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
    match = _USAGE_LINE_RE.search(text)
    if not match:
        return text
    return text[: match.start()].rstrip()
