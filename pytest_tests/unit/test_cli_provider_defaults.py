"""The command line's provider, model, prompt and default settings (4.9.0 guru bug bash).

B1: `idt describe` stopped with "Unknown provider: 'claude'" on any workspace
    ImageDescriber had described with Claude (Kelly's own iPhone490.idtw).
B2: `--provider anthropic` without `--model` sent the Ollama default model, so
    every picture got a 404.
S5: an unknown `--prompt` was accepted silently and the typo saved; Configure
    offered "Simple" (capitalised), which matched no prompt.
S6: every save of ~/.idt/config.json froze the defaults of the day, so
    Configure's choices never reached the command line.
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
from idt_core import config as cfg_mod  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / ".idt" / "config.json"
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", path)
    return path


def _ws(provider="", model="", described=True):
    return SimpleNamespace(has_any_descriptions=described,
                           defaults=SimpleNamespace(provider=provider, model=model))


def _args(provider=None, model=None, prompt=None, prompt_text=None):
    return SimpleNamespace(provider=provider, model=model, prompt=prompt, prompt_text=prompt_text)


def _cfg(provider="ollama", model="minicpm-v4.6", prompt="narrative"):
    c = cfg_mod.UserConfig()
    c.default_provider, c.default_model, c.default_prompt_name = provider, model, prompt
    return c


# --- B1: provider names ------------------------------------------------------

@pytest.mark.parametrize("name, key", [
    ("claude", "anthropic"), ("Claude", "anthropic"), ("anthropic", "anthropic"),
    ("openai", "openai"), ("Windows AI", "windows-ai"), ("windows-ai", "windows-ai"),
    ("claude-code", "claude-code"), ("ollama", "ollama"), ("apple", "apple"),
])
def test_any_name_of_a_provider_maps_to_the_cli_key(name, key):
    assert cli_main._cli_provider(name) == key


@pytest.mark.parametrize("name", ["", None, "bogus", "gemini"])
def test_unknown_provider_names_are_none(name):
    assert cli_main._cli_provider(name) is None


def test_provider_flag_accepts_claude():
    assert cli_main._provider_arg("claude") == "anthropic"


def test_a_workspace_imagedescriber_described_with_claude_continues():
    provider, model = cli_main._choose_provider_and_model(
        _args(), _ws("claude", "claude-haiku-5-5"), _cfg())
    assert (provider, model) == ("anthropic", "claude-haiku-5-5")


def test_a_workspace_with_an_unknown_provider_stops_with_a_clear_error(capsys):
    with pytest.raises(SystemExit) as exc:
        cli_main._choose_provider_and_model(_args(), _ws("gemini", "x"), _cfg())
    assert exc.value.code == 1           # a run that can't start; 2 is for usage errors
    assert "--provider" in capsys.readouterr().err


def test_an_unknown_default_provider_set_with_idt_config_stops(capsys):
    cfg = _cfg(provider="gemini")
    cfg.user_set.add("default_provider")
    with pytest.raises(SystemExit) as exc:
        cli_main._choose_provider_and_model(_args(), _ws(described=False), cfg)
    assert exc.value.code == 1
    assert "idt config" in capsys.readouterr().err


def test_configures_mlx_default_falls_back_to_ollama_with_a_note(capsys):
    """MLX runs only in ImageDescriber; the CLI carries on rather than refuse
    every run (#455 review)."""
    provider, model = cli_main._choose_provider_and_model(
        _args(), _ws(described=False), _cfg(provider="mlx"))
    assert provider == "ollama"
    assert model == "minicpm-v4.6"        # Configure's Ollama model
    assert "only in ImageDescriber" in capsys.readouterr().err


# --- B2: models stay with their provider ---------------------------------------

def test_a_named_provider_without_a_model_gets_its_own_default():
    provider, model = cli_main._choose_provider_and_model(
        _args(provider="anthropic"), _ws("ollama", "moondream"), _cfg())
    assert provider == "anthropic"
    assert model == "claude-haiku-5-5"      # Claude's own default


def test_a_configured_claude_model_is_used_for_claude_whatever_the_saved_provider():
    provider, model = cli_main._choose_provider_and_model(
        _args(provider="anthropic"), _ws(described=False), _cfg(model="claude-opus-5-5"))
    assert model == "claude-opus-5-5"


def test_the_workspaces_model_is_kept_for_its_own_provider():
    provider, model = cli_main._choose_provider_and_model(
        _args(), _ws("ollama", "moondream"), _cfg(provider="anthropic"))
    assert (provider, model) == ("ollama", "moondream")


def test_an_explicit_model_always_wins():
    _, model = cli_main._choose_provider_and_model(
        _args(provider="anthropic", model="claude-sonnet-5-5"), _ws("ollama", "moondream"), _cfg())
    assert model == "claude-sonnet-5-5"


def test_configures_claude_default_never_gets_configures_ollama_model():
    """Configure's default_model is its Ollama model. Paired with Configure's
    Claude default it sent "minicpm-v4.6" to Anthropic (#455 review, blocker)."""
    provider, model = cli_main._choose_provider_and_model(
        _args(), _ws(described=False), _cfg(provider="claude", model="minicpm-v4.6"))
    assert (provider, model) == ("anthropic", "claude-haiku-5-5")


@pytest.mark.parametrize("provider_key, expected", [
    ("openai", "gpt-5.2"), ("claude-code", "haiku")])
def test_configures_other_defaults_get_their_own_model(provider_key, expected):
    from importlib import import_module
    mod = {"openai": "openai_provider", "claude-code": "claude_code"}[provider_key]
    expected = import_module(f"idt_core.providers.{mod}").DEFAULT_MODEL
    _, model = cli_main._choose_provider_and_model(
        _args(), _ws(described=False), _cfg(provider=provider_key, model="minicpm-v4.6"))
    assert model == expected


def test_a_model_set_alone_with_idt_config_goes_with_its_own_provider():
    cfg = _cfg(provider="claude", model="llava:13b")      # provider from Configure
    cfg.user_set.add("default_model")
    _, model = cli_main._choose_provider_and_model(_args(), _ws(described=False), cfg)
    assert model == "claude-haiku-5-5"                     # llava is an Ollama model
    _, model = cli_main._choose_provider_and_model(_args(provider="ollama"), _ws(described=False), cfg)
    assert model == "llava:13b"


def test_a_model_set_with_idt_config_stays_with_its_provider_after_a_switch(config_file):
    """Set ollama + llava:13b, then switch the default to Claude: llava must
    not follow to Claude (#455 re-review)."""
    for setting in ("default_provider=ollama", "default_model=llava:13b",
                    "default_provider=anthropic"):
        cli_main.cmd_config(SimpleNamespace(set_value=setting))
    cfg = cfg_mod.UserConfig.load()
    assert cfg.default_model_provider == "ollama"
    assert cli_main._choose_provider_and_model(_args(), _ws(described=False), cfg) == \
        ("anthropic", "claude-haiku-5-5")
    assert cli_main._choose_provider_and_model(
        _args(provider="ollama"), _ws(described=False), cfg) == ("ollama", "llava:13b")


def test_a_provider_and_model_set_together_stay_together():
    cfg = _cfg(provider="anthropic", model="claude-opus-5-5")
    cfg.user_set.update({"default_provider", "default_model"})
    assert cli_main._choose_provider_and_model(_args(), _ws(described=False), cfg) == \
        ("anthropic", "claude-opus-5-5")


# --- S5: prompt names ----------------------------------------------------------

def test_prompt_names_match_regardless_of_case(config_file):
    name, text = cli_main._resolve_prompt(_args(prompt="Simple"), None, "anthropic")
    assert name == "simple" and text


def test_an_unknown_prompt_asked_for_is_an_error(config_file, capsys):
    with pytest.raises(SystemExit) as exc:
        cli_main._resolve_prompt(_args(prompt="nonexistent_style"), None, "anthropic")
    assert exc.value.code == 2
    assert "idt prompts" in capsys.readouterr().err


def test_an_unknown_inherited_prompt_falls_back_and_says_so(config_file, capsys):
    ws_defaults = SimpleNamespace(prompt_name="nonexistent_style")
    name, text = cli_main._resolve_prompt(_args(), ws_defaults, "anthropic")
    assert name == cfg_mod.DEFAULT_PROMPT_NAME and text
    assert "doesn't exist" in capsys.readouterr().err


def test_configure_offers_real_prompt_names():
    # Configure lists the settings file's prompts (#469); the fallback, used
    # only for a file with none, must still be real prompt names.
    src = (_ROOT / "imagedescriber" / "configure_dialog.py").read_text(encoding="utf-8")
    shared = json.loads((_ROOT / "scripts" / "image_describer_config.json").read_text(encoding="utf-8"))
    start = src.index("_FALLBACK_PROMPT_STYLES = [")
    literal = src[start:src.index("]", start) + 1].split("=", 1)[1]
    for choice in json.loads(" ".join(literal.split())):
        assert choice in shared["prompt_variations"], choice


# --- S6: what ~/.idt/config.json holds ----------------------------------------

def test_saving_writes_only_what_the_user_set(config_file):
    c = cfg_mod.UserConfig.load()
    c.last_update_check = "2026-11-18T00:00:00"     # what ImageDescriber's update check saves
    c.save()
    data = json.loads(config_file.read_text(encoding="utf-8"))
    for key in ("default_provider", "default_model", "default_prompt_name"):
        assert key not in data
    assert data["user_set"] == []


def test_a_default_set_with_idt_config_is_kept(config_file):
    c = cfg_mod.UserConfig.load()
    c.set_default("default_model", "claude-opus-5-5")
    c.save()
    again = cfg_mod.UserConfig.load()
    assert again.default_model == "claude-opus-5-5"
    assert again.user_set == {"default_model"}


def test_an_old_file_with_frozen_defaults_no_longer_overrides_configure(config_file):
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps({          # Kelly's actual file, 11/18/2026
        "default_provider": "ollama", "default_model": "minicpm-v4.6",
        "default_prompt_name": "narrative", "custom_prompts": {},
        "copy_originals": False, "preserve_alt_text": True,
        "auto_check_updates": True, "last_update_check": "2026-11-17T19:20:14"}),
        encoding="utf-8")
    c = cfg_mod.UserConfig.load()
    assert c.user_set == set()
    assert c.default_provider == cfg_mod.DEFAULT_PROVIDER
    assert c.default_model == cfg_mod.DEFAULT_OLLAMA_MODEL


def test_an_old_file_with_a_real_choice_keeps_it(config_file):
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps({"default_provider": "anthropic",
                                       "default_model": "claude-opus-5-5"}), encoding="utf-8")
    c = cfg_mod.UserConfig.load()
    assert (c.default_provider, c.default_model) == ("anthropic", "claude-opus-5-5")
    assert c.user_set == {"default_provider", "default_model"}


def test_configures_default_provider_is_read(tmp_path, monkeypatch):
    user_dir = tmp_path / "user_config"
    user_dir.mkdir()
    (user_dir / "image_describer_config.json").write_text(
        json.dumps({"default_provider": "claude"}), encoding="utf-8")
    monkeypatch.setenv("IDT_USER_CONFIG_DIR", str(user_dir))
    assert cfg_mod._shared_default_provider() == ("claude", True)


def test_an_old_file_is_judged_as_a_whole(config_file):
    """Only a file whose three defaults are ALL the old shipped ones is
    leftovers; one real choice keeps the provider and model together
    (#455 review: keeping llava:13b but dropping "ollama" sent llava to Claude)."""
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps({"default_provider": "ollama", "default_model": "llava:13b",
                                       "default_prompt_name": "narrative"}), encoding="utf-8")
    c = cfg_mod.UserConfig.load()
    assert (c.default_provider, c.default_model) == ("ollama", "llava:13b")
    assert c.user_set == {"default_provider", "default_model", "default_prompt_name"}


def test_a_new_workspace_uses_the_default_prompt_not_detailed(config_file, monkeypatch):
    """A workspace's prompt is used only once it has descriptions; a new one
    used to say "detailed" whatever Configure said (#431, #455 review)."""
    c = cfg_mod.UserConfig.load()
    c.set_default("default_prompt_name", "simple")
    c.save()
    ws = SimpleNamespace(has_any_descriptions=False,
                         defaults=SimpleNamespace(prompt_name="detailed"))
    name, _ = cli_main._resolve_prompt(
        _args(), ws.defaults if ws.has_any_descriptions else None, "anthropic")
    assert name == "simple"


def test_a_mistyped_prompt_is_refused_before_a_workspace_is_made(tmp_path, monkeypatch, config_file):
    pics = tmp_path / "pics"
    pics.mkdir()
    monkeypatch.setattr(sys, "argv", ["idt", "describe", str(pics), "--prompt", "Simpel",
                                      "--workspace", str(tmp_path / "w.idtw")])
    with pytest.raises(SystemExit) as exc:
        cli_main.main()
    assert exc.value.code == 2
    assert not (tmp_path / "w.idtw").exists()


# --- idt config --set ------------------------------------------------------------

def test_config_set_stores_a_provider_as_its_cli_key(config_file, capsys):
    cli_main.cmd_config(SimpleNamespace(set_value="default_provider=claude"))
    assert cfg_mod.UserConfig.load().default_provider == "anthropic"


def test_config_set_refuses_an_unknown_provider(config_file):
    with pytest.raises(SystemExit):
        cli_main.cmd_config(SimpleNamespace(set_value="default_provider=gemini"))
    assert not config_file.exists()


def test_config_set_refuses_an_unknown_prompt_and_fixes_case(config_file):
    with pytest.raises(SystemExit):
        cli_main.cmd_config(SimpleNamespace(set_value="default_prompt_name=nope"))
    cli_main.cmd_config(SimpleNamespace(set_value="default_prompt_name=Simple"))
    assert cfg_mod.UserConfig.load().default_prompt_name == "simple"


@pytest.mark.parametrize("from_configure, label", [(True, "(from Configure)"), (False, "(default)")])
def test_config_says_where_each_default_comes_from(config_file, capsys, monkeypatch,
                                                   from_configure, label):
    monkeypatch.setattr(cfg_mod, "DEFAULTS_FROM_CONFIGURE", from_configure)
    cli_main.cmd_config(SimpleNamespace(set_value="default_model=claude-opus-5-5"))
    capsys.readouterr()
    cli_main.cmd_config(SimpleNamespace(set_value=None))
    out = capsys.readouterr().out
    assert "default_model:    claude-opus-5-5  (set with idt config)" in out
    assert f"default_prompt:   {cfg_mod.DEFAULT_PROMPT_NAME}  {label}" in out


def test_config_says_configures_model_is_the_ollama_model(config_file, capsys):
    cli_main.cmd_config(SimpleNamespace(set_value=None))
    assert ", used with Ollama)" in capsys.readouterr().out


# --- idt guideme's key check ---------------------------------------------------

def test_guideme_finds_a_key_saved_in_configure(monkeypatch, capsys):
    """It checked only environment variables, so a key saved in Configure was
    reported missing (newcomer bug bash, S3)."""
    from cli import guide
    import idt_core.keys as keys

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(keys, "resolve_api_key", lambda p: "sk-ant-test-0000000000000000")
    monkeypatch.setattr(keys, "key_source", lambda p: "credential store")
    assert guide._step_api_key("anthropic") is True
    out = capsys.readouterr().out
    assert "credential store" in out
    assert "sk-ant" not in out and "0000" not in out   # no part of the key


def test_guideme_with_no_key_points_to_configure(monkeypatch, capsys):
    from cli import guide
    import idt_core.keys as keys

    monkeypatch.setattr(keys, "resolve_api_key", lambda p: None)
    monkeypatch.setattr(guide, "get_yes_no", lambda *a, **k: False)
    assert guide._step_api_key("openai") is False
    assert "Configure" in capsys.readouterr().out
