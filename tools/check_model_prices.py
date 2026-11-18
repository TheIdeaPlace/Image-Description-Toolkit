"""Compare IDT's model prices with Anthropic's and OpenAI's pricing pages.

Providers don't report prices through their APIs, so idt_core/pricing.py is a
hand-copied table, and it goes stale. This reads both pricing pages (their
Markdown versions), and reports:

* a price that differs from the page;
* a model IDT offers with no price in the table;
* a priced model the page no longer lists (often retired);
* a model on the page IDT has no price for (usually a new model, which IDT's
  model list probably lacks too).

Run weekly by .github/workflows/model-prices.yml, which files or updates an
issue when there's anything to report. The report says
whether anything differs (first line "OK" or "DIFFERS"); a page that can't be read gives "ERROR" and exit code 1.

    python tools/check_model_prices.py [--report out.md] [--anthropic file] [--openai file]
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from idt_core import pricing  # noqa: E402

ANTHROPIC_URL = "https://platform.claude.com/docs/en/about-claude/pricing.md"
OPENAI_URL = "https://developers.openai.com/api/docs/pricing.md"

#: Models on the pages that IDT deliberately doesn't price or offer. Edit
#: this, with a reason, to stop a model being reported as missing.
IGNORE = {
    "claude": [
        (re.compile(r"Mythos", re.I), "verified organizations only"),
    ],
    "openai": [
        (re.compile(r"-pro$"), "pro models: far too expensive for describing images"),
    ],
}

_PRICE = re.compile(r"\$\s*([\d,]*\.?\d+)")


def _cells(line: str) -> list:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _dollars(cell: str):
    m = _PRICE.search(cell or "")
    return float(m.group(1).replace(",", "")) if m else None


def _section(text: str, heading: str, level: str) -> str:
    """Text from ``heading`` to the next heading of the same level."""
    start = text.find(heading)
    if start < 0:
        return ""
    rest = text[start + len(heading):]
    nxt = re.search(rf"^{re.escape(level)} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def parse_anthropic(text: str) -> dict:
    """{page name: (input, output, retired)} from the "Model pricing" table.

    The first row for a name wins, so Haiku 5.5's "up to 100,000 tokens" row
    is used rather than its long-prompt row."""
    out: dict = {}
    for line in _section(text, "## Model pricing", "##").splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) < 3 or cells[0].lower() == "model" or set(cells[0]) <= set("-: "):
            continue
        raw = cells[0]
        name = re.sub(r"\s*\(.*$", "", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", raw)).strip()
        inp, outp = _dollars(cells[1]), _dollars(cells[-1])
        if name and inp is not None and outp is not None and name not in out:
            out[name] = (inp, outp, "retired" in raw.lower())
    return out


def parse_openai(text: str) -> dict:
    """{model id: (input, output, False)} from the "Standard pricing" tables.

    Columns 2 and 3 are input and output in both table layouts on the page
    ("Input | Output" and "Short context input | Short context output")."""
    out: dict = {}
    for line in _section(text, "### Standard pricing data", "###").splitlines():
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) < 3 or cells[0].lower() == "model" or set(cells[0]) <= set("-: "):
            continue
        model = re.sub(r"\s*\(.*$", "", cells[0]).strip()
        inp, outp = _dollars(cells[1]), _dollars(cells[2])
        if model and inp is not None and outp is not None and model not in out:
            out[model] = (inp, outp, False)
    return out


def _ignored(provider: str, name: str) -> str:
    for pattern, reason in IGNORE.get(provider, []):
        if pattern.search(name):
            return reason
    return ""


def offered_models() -> dict:
    """Model ids IDT offers, per provider (its built-in lists)."""
    from idt_core.providers.claude import CLAUDE_MODELS
    from idt_core.providers.openai_provider import OPENAI_MODELS
    return {"claude": list(CLAUDE_MODELS), "openai": list(OPENAI_MODELS)}


def compare(provider: str, page: dict, offered: list) -> list:
    """Findings for one provider, as (kind, text) pairs."""
    findings = []
    table = pricing.PRICES.get(provider, {})
    by_page_name = {p.page_name: (model, p) for model, p in table.items()}
    for model, p in table.items():
        row = page.get(p.page_name)
        if row is None and model in pricing.KEPT_FOR_OLD_WORKSPACES:
            continue
        if row is None:
            findings.append(("gone", f"`{model}` ({p.page_name}) isn't on the pricing page any more."))
            continue
        if abs(row[0] - p.input) > 1e-9 or abs(row[1] - p.output) > 1e-9:
            findings.append(("price", f"`{model}`: IDT has ${p.input:g} in / ${p.output:g} out, "
                                      f"the page says ${row[0]:g} / ${row[1]:g}."))
    for name, (inp, outp, retired) in sorted(page.items()):
        if name in by_page_name or retired or _ignored(provider, name):
            continue
        findings.append(("new", f"{name}: ${inp:g} in / ${outp:g} out on the page, no price in IDT."))
    for model in offered:
        if model not in table:
            findings.append(("unpriced", f"`{model}` is in IDT's model list but has no price."))
    return findings


def report(results: dict, errors: list) -> str:
    any_finding = errors or any(results.values())
    # A page that couldn't be read is ERROR, not DIFFERS: the workflow fails
    # the run (GitHub sends its own notice) and leaves any open issue alone,
    # so a download hiccup never replaces the real findings.
    status = "ERROR" if errors else ("DIFFERS" if any_finding else "OK")
    lines = [status, ""]
    if not any_finding:
        lines.append("Every price in `idt_core/pricing.py` matches the providers' pricing pages.")
        return "\n".join(lines) + "\n"
    lines += ["IDT's price table (`idt_core/pricing.py`) and the providers' pricing pages "
              "don't agree. `idt stats` and ImageDescriber's cost meter use that table.", ""]
    for err in errors:
        lines.append(f"- **Couldn't check:** {err}")
    titles = {"price": "Price changed", "new": "On the pricing page, not priced in IDT",
              "unpriced": "Offered by IDT, no price", "gone": "No longer on the pricing page"}
    for provider, findings in results.items():
        if not findings:
            continue
        lines += ["", f"## {'Claude' if provider == 'claude' else 'OpenAI'}"]
        for kind in ("price", "unpriced", "new", "gone"):
            items = [t for k, t in findings if k == kind]
            if items:
                lines += ["", f"**{titles[kind]}**", ""] + [f"- {t}" for t in items]
    lines += ["", "Pages checked:", f"- {ANTHROPIC_URL}", f"- {OPENAI_URL}", "",
              "To fix: update `idt_core/pricing.py` (and the model lists in "
              "`idt_core/providers/` for new models). To stop a model being reported, add it "
              "to `IGNORE` in `tools/check_model_prices.py` with a reason."]
    return "\n".join(lines) + "\n"


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "idt-price-check"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", help="write the report here as well as printing it")
    ap.add_argument("--anthropic", help="read Anthropic's page from this file (testing)")
    ap.add_argument("--openai", help="read OpenAI's page from this file (testing)")
    args = ap.parse_args(argv)

    offered = offered_models()
    results, errors = {}, []
    for provider, url, path, parse in (("claude", ANTHROPIC_URL, args.anthropic, parse_anthropic),
                                       ("openai", OPENAI_URL, args.openai, parse_openai)):
        try:
            text = Path(path).read_text(encoding="utf-8") if path else _fetch(url)
            page = parse(text)
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            continue
        if len(page) < 3:
            errors.append(f"{url}: found only {len(page)} priced models; the page's layout "
                          "may have changed, so this check needs updating.")
            continue
        results[provider] = compare(provider, page, offered.get(provider, []))
    text = report(results, errors)
    print(text)
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
