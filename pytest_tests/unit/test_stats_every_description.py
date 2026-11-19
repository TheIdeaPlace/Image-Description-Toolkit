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
    return {(r["provider_name"], r["model"]): r for r in cli_main.stats_token_rows(items)}


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
    ("openai", "gpt-future-9", "no price"),  # a model IDT has no price for
    ("claude", "claude-future-9", "no price"),
])
def test_providers_without_a_per_token_price_say_why(provider, model, note):
    rows = cli_main.stats_token_rows([_item(_desc(provider, model, 500, 50))])
    assert rows[0]["cost"] is None
    assert rows[0]["cost_note"] == note
    assert rows[0]["input_tokens"] == 500          # tokens still counted


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-terra", "gpt-6.2-sol", "gpt-6.2-astra",
                                   "gpt-5.2", "gpt-5.1", "gpt-5", "gpt-5-mini", "gpt-5-nano",
                                   "o3", "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini",
                                   "o1", "o4-mini", "gpt-4.1-nano"])  # last 3: shut down, old workspaces
def test_openai_models_are_priced(model):
    rows = cli_main.stats_token_rows([_item(_desc("openai", model, 1_000_000, 0))])
    assert rows[0]["cost"] == pytest.approx(cli_main.STATS_COST_TABLE[model][0])


def test_windows_ai_is_not_reported_as_missing_tokens():
    rows = cli_main.stats_token_rows([_item(_desc("windows-ai", "accessible", None, None)),
                                      _item(_desc("ollama", "moondream", None, None))])
    by = {r["provider_name"]: r for r in rows}
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
    assert out["total_cost_is_partial"] is False
    # provider stays the canonical lowercase name scripts matched on before
    assert models["claude-haiku-5-5"]["provider"] == "claude"
    assert models["claude-haiku-5-5"]["provider_name"] == "Claude"


# --- Review findings (independent review of #450) ---------------------------

@pytest.mark.parametrize("provider, model", [
    ("ollama", "kimi-k2.5:cloud"),        # ":cloud" tags, not only "-cloud"
    ("ollama", "gpt-oss:120b-cloud"),
    ("ollama_cloud", "gpt-oss:120b-cloud"),  # ImageDescriber's old provider key
])
def test_ollama_cloud_models_are_on_the_plan_not_free(provider, model):
    row = cli_main.stats_token_rows([_item(_desc(provider, model, 100, 10))])[0]
    assert row["cost_note"] == "Ollama plan"
    assert row["cost"] is None


def test_a_priced_model_with_no_tokens_says_so_rather_than_zero():
    row = cli_main.stats_token_rows([_item(_desc("claude", "claude-haiku-4-5-20251001", None, None))])[0]
    assert row["cost"] is None
    assert row["cost_note"] == "no token data"


def test_a_priced_model_with_some_tokens_missing_is_a_floor():
    row = cli_main.stats_token_rows([
        _item(_desc("claude", "claude-sonnet-4-6", 1000, 100)),
        _item(_desc("claude", "claude-sonnet-4-6", None, 500)),   # before #446
    ])[0]
    assert row["cost_is_partial"] is True
    assert row["cost_note"] == "1 without token counts"
    assert row["cost"] == pytest.approx((1000 * 3.0 + 600 * 15.0) / 1e6)


def test_website_alt_text_is_not_counted():
    rows = cli_main.stats_token_rows([_item(
        _desc("website", "Website Alt Text", None, None),
        _desc("claude", "claude-haiku-5-5", 100, 10))])
    assert [r["model"] for r in rows] == ["claude-haiku-5-5"]
    assert rows[0]["missing_tokens"] == 0


def test_a_dated_snapshot_is_priced_as_its_model():
    row = cli_main.stats_token_rows([_item(_desc("openai", "gpt-5-mini-2025-08-07", 1_000_000, 0))])[0]
    assert row["cost"] == pytest.approx(0.25)


def test_whole_video_descriptions_are_counted(tmp_path, capsys):
    from idt_core.workspace import WorkspaceItem

    ws = Workspace.create(tmp_path / "run.idtw")
    video = WorkspaceItem(image="clip.mov", source_path=str(tmp_path / "clip.mov"),
                          item_type="video")
    video.add_description(_desc("claude", "claude-haiku-5-5", 20000, 800))
    Workspace(ws.path).save_item(video)

    cli_main.cmd_stats(SimpleNamespace(source=str(ws.path), all=False, json_out=True))
    out = json.loads(capsys.readouterr().out)
    assert [r["input_tokens"] for r in out["token_breakdown"]] == [20000]


def test_text_output_reads_cleanly_for_long_names_and_partial_costs(tmp_path, capsys):
    src = tmp_path / "photos"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"x")
    ws = Workspace.create(tmp_path / "run.idtw")
    ws.add_source_folder(src)
    bundle = Workspace(ws.path)
    item = bundle.media_items()[0]
    item.add_description(_desc("apple", "system", 300, 40))
    item.add_description(_desc("claude", "claude-sonnet-4-6", None, 500))
    item.add_description(_desc("claude", "claude-sonnet-4-6", 1000, 100))
    bundle.save_item(item)

    cli_main.cmd_stats(SimpleNamespace(source=str(ws.path), all=False, json_out=False))
    text = capsys.readouterr().out
    header = next(l for l in text.splitlines() if l.startswith("Provider"))
    lines = [l for l in text.splitlines() if l.startswith(("Apple Intelligence", "Claude", "TOTAL"))]
    assert len(lines) == 3
    # Columns line up: each row's description count ends where "Descr." ends.
    end = header.index("Descr.") + len("Descr.")
    for line in lines:
        assert line[end - 1].isdigit() and line[end] == " ", line
    assert "no charge" in lines[0]
    assert "at least $" in lines[1] and "1 without token counts" in lines[1]
    assert "at least $" in lines[2]
