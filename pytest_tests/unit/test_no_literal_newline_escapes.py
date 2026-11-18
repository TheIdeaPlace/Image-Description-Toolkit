"""Messages shown to people must not contain a literal backslash-n.

Refresh AI Models showed "\\n" as text, which a screen reader reads as
"backslash n" (4.9.0 newcomer bug bash, S5). This scans the app's source for
the double-escaped form in string literals, f-strings included: on Python
3.12+ tokenize splits an f-string into FSTRING_START/MIDDLE/END tokens, and
two of the three original bugs were in f-strings (#457 review).

Known gaps, accepted: triple-quoted strings are skipped (docstrings, and
sometimes help text, legitimately show a backslash-n), and a Windows path
such as "C:\\new" in a non-raw string would be flagged.
"""
import io
import tokenize
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.unit

_FILES = (sorted((_ROOT / "imagedescriber").glob("*.py")) + sorted((_ROOT / "chatapp").glob("*.py"))
          + sorted((_ROOT / "shared").glob("*.py")) + [_ROOT / "cli" / "main.py"])

_FSTRING_START = getattr(tokenize, "FSTRING_START", None)
_FSTRING_MIDDLE = getattr(tokenize, "FSTRING_MIDDLE", None)


def double_escaped_newlines(src: str) -> list:
    """Line numbers of string literals containing a double-escaped newline."""
    found = []
    skip_fstring = False          # inside a raw or triple-quoted f-string
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.STRING or (_FSTRING_START is not None and tok.type == _FSTRING_START):
            text = tok.string
            prefix = text[: len(text) - len(text.lstrip("rRbBuUfF"))].lower()
            raw_or_triple = "r" in prefix or text.lstrip("rRbBuUfF").startswith(('"""', "'''"))
            if tok.type == tokenize.STRING:
                if not raw_or_triple and "\\\\n" in text:
                    found.append(tok.start[0])
            else:
                skip_fstring = raw_or_triple
        elif _FSTRING_MIDDLE is not None and tok.type == _FSTRING_MIDDLE:
            if not skip_fstring and "\\\\n" in tok.string:
                found.append(tok.start[0])
    return found


def test_the_scanner_sees_plain_strings_and_f_strings():
    assert double_escaped_newlines('x = "a\\\\nb"\n') == [1]
    assert double_escaped_newlines('x = f"a\\\\n{y}"\n') == [1]
    assert double_escaped_newlines('x = "a\\nb"\n') == []
    assert double_escaped_newlines('x = r"a\\\\nb"\n') == []
    assert double_escaped_newlines('x = rf"a\\\\n{y}"\n') == []


@pytest.mark.parametrize("path", _FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_double_escaped_newlines_in_strings(path):
    lines = double_escaped_newlines(path.read_text(encoding="utf-8"))
    assert not lines, f"double-escaped newline on line(s) {lines}"
