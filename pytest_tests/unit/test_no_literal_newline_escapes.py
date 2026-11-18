"""Messages shown to people must not contain a literal backslash-n.

Refresh AI Models showed "\\n" as text, which a screen reader reads as
"backslash n" (4.9.0 newcomer bug bash, S5). This scans the app's source for
the double-escaped form in string literals.
"""
import io
import tokenize
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.unit

_FILES = sorted((_ROOT / "imagedescriber").glob("*.py")) + sorted((_ROOT / "chatapp").glob("*.py"))


@pytest.mark.parametrize("path", _FILES, ids=lambda p: p.name)
def test_no_double_escaped_newlines_in_strings(path):
    src = path.read_text(encoding="utf-8")
    bad = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.STRING:
            continue
        text = tok.string
        prefix = text[: len(text) - len(text.lstrip("rRbBuUfF"))].lower()
        if "r" in prefix or text.lstrip("rRbBuUfF").startswith(('"""', "'''")):
            continue   # raw strings and docstrings may mean it
        if "\\\\n" in text:
            bad.append(f"line {tok.start[0]}: {text[:60]}")
    assert not bad, "\n".join(bad)
