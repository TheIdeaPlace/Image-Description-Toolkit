"""Markdown in a description, shown as HTML in IDT's HTML exports (#465).

Models write Markdown: "**Foreground:**", "## Setting", "- a red chair". The
HTML report, ImageDescriber's Export HTML and the gallery escaped it and showed
it as typed, so a screen reader read "number sign number sign Setting" and
"star star". This turns a small subset into tags:

* headings, as a bold paragraph rather than <h1>-<h6>, so they don't break the
  page's own heading outline (each picture is an <h2>, its descriptions <h3>
  and <h4>);
* **bold** and __bold__, *italic*, `code`;
* bulleted (-, *, +) and numbered (1. or 1)) lists;
* paragraphs, split on blank lines, with single line breaks kept as <br>.

Everything is HTML-escaped first and only these tags are added afterwards, so
a description can never inject markup: "<script>" stays text. No Markdown
library, as Python-Markdown passes raw HTML straight through.

The output has no raw newlines between tags: the lightbox gallery shows its
description with ``white-space: pre-wrap``, which would turn them into extra
blank lines.
"""
from __future__ import annotations

import html
import re

_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_BULLET = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^\s*\d{1,3}[.)]\s+(.*)$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")

_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*|__(?=\S)(.+?)(?<=\S)__")
# Single-star italic only: underscores sit inside file names (IMG_0001_edit).
_ITALIC = re.compile(r"(?<![*\w])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![*\w])")


def _inline(escaped: str) -> str:
    """Bold, italic and code on text that is already HTML-escaped."""
    codes = []

    def keep_code(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = _CODE.sub(keep_code, escaped)          # nothing inside code is styled
    text = _BOLD.sub(lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", text)
    text = _ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", text)


def markdown_to_safe_html(text: str) -> str:
    """A description's Markdown as escaped HTML block elements (see module doc)."""
    if not text or not text.strip():
        return ""
    out = []
    paragraph: list = []
    list_tag = None
    items: list = []

    def flush_paragraph():
        if paragraph:
            out.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def flush_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"<{list_tag}>" + "".join(f"<li>{_inline(i)}</li>" for i in items)
                       + f"</{list_tag}>")
            items.clear()
            list_tag = None

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = html.escape(raw.rstrip(), quote=True)
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        if _RULE.match(line):
            flush_paragraph()
            flush_list()
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_paragraph()
            flush_list()
            if heading.group(1):
                out.append(f"<p><strong>{_inline(heading.group(1))}</strong></p>")
            continue
        bullet, numbered = _BULLET.match(line), _NUMBERED.match(line)
        if bullet or numbered:
            tag = "ul" if bullet else "ol"
            flush_paragraph()
            if list_tag and list_tag != tag:
                flush_list()
            list_tag = tag
            items.append((bullet or numbered).group(1))
            continue
        if list_tag and raw[:1].isspace():
            items[-1] += " " + line.strip()          # a wrapped list item
            continue
        flush_list()
        paragraph.append(line)
    flush_paragraph()
    flush_list()
    return "".join(out)
