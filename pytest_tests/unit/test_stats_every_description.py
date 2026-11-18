"""`idt stats` counts every description's tokens and cost, for every provider.

It used to count only each picture's current description. Describing the same
376 pictures with Haiku 5.5 and then Haiku 4.5 left the Haiku 5.5 run's $0.36
out entirely: `idt stats` showed $1.19 where $1.55 had been spent (11/17/2026).
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli import main as cli_main  # noqa: E402
from idt_core.workspace import Workspace, WorkspaceDescription  # noqa: E402

pytestmark = pytest.mark.unit


def _desc(provider, model, inp, out):
    return WorkspaceDescription.create("A picture.", provider=provider, model=model,
                                       prompt_name="narrative", input_tokens=inp,
                                       output_tokens=out)


def _item(*descs):
    return SimpleNamespace(descriptions=list(descs), active_description=descs[-1])


def _rows(items):
    return {(r["provider"], r["model"]): r for r in cli_main.stats_token_rows(items)}


def test_a_picture_described_twice_is_paid_for_twice():
    items = [_item(_desc("claude", "claude-haiku-5-5", 3925, 932),
                   _desc("claude", "claude-haiku-4-5-20251001", 1529, 294))]
    rows = _rows(items)
    assert rows[("Claude", "claude-haiku-5-5")]["descriptions"] == 1
    assert rows[("Claude", "claude-haiku-4-5-20251001")]["descriptions"] == 1
    total = sum(r["cost"] for r in rows.values())
    expected = (3925 * 0.10 + 932 * 0.50 + 1529 * 1.0 + 294 * 5.0) / 1e6
    assert total == pytest.approx(expected)


def test_the_command_line_and_imagedescriber_names_for_claude_are_one_row():
    items = [_item(_desc("anthropic", "claude-haiku-5-5", 100, 10)),
             _item(_desc("claude", "claude-haiku-5-5", 100, 10))]
    rows = _rows(items)
    assert list(rows) == [("Claude", "claude-haiku-5-5")]
    assert rows[("Claude", "claude-haiku-5-5")]["descriptions"] == 2
    assert rows[("Claude", "claude-haiku-5-5")]["pictures"] == 2


def test_a_picture_described_twice_by_one_model_counts_one_picture_two_descriptions():
    rows = _rows([_item(_desc("openai", "gpt-5-mini", 1000, 100),
                        _desc("openai", "gpt-5-mini", 1000, 120))])
    r = rows[("OpenAI", "gpt-5-mini")]
    assert (r["pictures"], r["descriptions"]) == (1, 2)
    assert r["cost"] == pytest.approx((2000 * 0.25 + 220 * 2.0) / 1e6)


@pytest.mark.parametrize("provider, model, note", [
    ("ollama", "moondream", "no charge"),
    ("ollama", "qwen3-vl:235b-cloud", "Ollama plan"),
    ("windows-ai", "accessible", "no charge"),
    ("apple", "system", "no charge"),
    ("mlx", "some-mlx-model", "no charge"),
    ("claude-code", "haiku", "your plan"),
    ("openai", "o1", "no price"),            # OpenAI lists no price for it
    ("claude", "claude-future-9", "no price"),
])
def test_providers_without_a_per_token_price_say_why(provider, model, note):
    rows = cli_main.stats_token_rows([_item(_desc(provider, model, 500, 50))])
    assert rows[0]["cost"] is None
    assert rows[0]["cost_note"] == note
    assert rows[0]["input_tokens"] == 500          # tokens still counted


@pytest.mark.parametrize("model", ["gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-5-nano",
                                   "o3", "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"])
def test_openai_models_are_priced(model):
    rows = cli_main.stats_token_rows([_item(_desc("openai", model, 1_000_000, 0))])
    assert rows[0]["cost"] == pytest.approx(cli_main.STATS_COST_TABLE[model][0])


def test_windows_ai_is_not_reported_as_missing_tokens():
    rows = cli_main.stats_token_rows([_item(_desc("windows-ai", "accessible", None, None)),
                                      _item(_desc("ollama", "moondream", None, None))])
    by = {r["provider"]: r for r in rows}
    assert by["Windows AI"]["missing_tokens"] == 0
    assert by["Ollama"]["missing_tokens"] == 1


def test_idt_stats_json_reports_every_description_and_a_total(tmp_path, capsys):
    src = tmp_path / "photos"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"x")
    ws = Workspace.create(tmp_path / "run.idtw")
    ws.add_source_folder(src)
    bundle = Workspace(ws.path)
    item = bundle.media_items()[0]
    item.add_description(_desc("claude", "claude-haiku-5-5", 3925, 932))
    item.add_description(_desc("claude", "claude-haiku-4-5-20251001", 1529, 294))
    bundle.save_item(item)

    cli_main.cmd_stats(SimpleNamespace(source=str(ws.path), all=False, json_out=True))
    out = json.loads(capsys.readouterr().out)
    models = {r["model"]: r for r in out["token_breakdown"]}
    assert set(models) == {"claude-haiku-5-5", "claude-haiku-4-5-20251001"}
    assert out["grand_described"] == 1
    expected = (3925 * 0.10 + 932 * 0.50 + 1529 * 1.0 + 294 * 5.0) / 1e6
    assert out["total_estimated_cost_usd"] == pytest.approx(expected, abs=0.0001)
