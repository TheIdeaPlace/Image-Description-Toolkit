"""
What Configure saves is what processing, the Prompt Editor and the CLI read (#407).

On an installed Windows copy, Configure saved to %APPDATA%\\IDT while every
reader took C:\\idt\\scripts first: the exe's scripts folder came before the user
folder in config_loader, and the installer pointed IDT_CONFIG_DIR at it too.
So no setting changed in Configure ever took effect there -- including all of
4.9's Generation tab. Found by the NVDA bug bash of 11/15/2026: Configure said
"artistic", the Process dialog still said "narrative".

These tests build that installed layout (a frozen exe beside a scripts folder of
shipped defaults, IDT_CONFIG_DIR pointing at it) and check the round trip.
None of them opens a window.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from idt_core import config_loader  # noqa: E402

NAME = "image_describer_config.json"
SHIPPED = {"default_prompt_style": "narrative", "default_model": "minicpm-v4.6",
           "prompt_variations": {"narrative": "Describe.", "artistic": "Paint it."},
           "processing_options": {"default_batch_delay": 1.0}}


@pytest.fixture
def installed(tmp_path, monkeypatch):
    """C:\\idt with idt.exe, scripts\\ of shipped defaults, and IDT_CONFIG_DIR set."""
    app = tmp_path / "idt"
    (app / "scripts").mkdir(parents=True)
    (app / "scripts" / NAME).write_text(json.dumps(SHIPPED), encoding="utf-8")
    (app / "ImageDescriber.exe").write_bytes(b"")
    user = tmp_path / "AppData" / "IDT"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "ImageDescriber.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(app / "imagedescriber-lib"), raising=False)
    monkeypatch.setenv("IDT_CONFIG_DIR", str(app / "scripts"))   # what old installers set
    monkeypatch.setenv("IDT_USER_CONFIG_DIR", str(user))
    monkeypatch.chdir(tmp_path)
    return app, user


def _save_user(user, data):
    user.mkdir(parents=True, exist_ok=True)
    (user / NAME).write_text(json.dumps(data), encoding="utf-8")


def test_without_user_settings_the_shipped_defaults_are_used(installed):
    app, user = installed
    config, path, source = config_loader.load_json_config(NAME)
    assert config["default_prompt_style"] == "narrative"
    assert path == app / "scripts" / NAME and source == "idt_config_dir"


def test_the_users_settings_win_over_the_installed_defaults(installed):
    """The bug: this read C:\\idt\\scripts and said "narrative"."""
    app, user = installed
    _save_user(user, dict(SHIPPED, default_prompt_style="artistic"))
    config, path, source = config_loader.load_json_config(NAME)
    assert config["default_prompt_style"] == "artistic"
    assert path == user / NAME and source == "user_config"


def test_generation_settings_saved_by_configure_reach_processing(installed):
    from idt_core import generation
    app, user = installed
    _save_user(user, dict(SHIPPED, generation={"ollama": {"temperature": 0.2}}))
    assert generation.user_options("ollama").temperature == 0.2


def test_a_section_added_in_a_later_release_still_appears(installed):
    """A copy saved before 4.9 has no "generation"; one shipped later is filled in."""
    app, user = installed
    shipped = dict(SHIPPED, generation={"ollama": {"thinking": "off"}})
    (app / "scripts" / NAME).write_text(json.dumps(shipped), encoding="utf-8")
    _save_user(user, dict(SHIPPED, default_prompt_style="artistic"))
    config, _p, _s = config_loader.load_json_config(NAME)
    assert config["generation"] == {"ollama": {"thinking": "off"}}
    assert config["default_prompt_style"] == "artistic"


def test_what_the_user_removed_stays_removed(installed):
    """Top level only: a deleted built-in prompt style, or a setting removed to
    mean Automatic, must not come back from the defaults."""
    app, user = installed
    saved = json.loads(json.dumps(SHIPPED))
    del saved["prompt_variations"]["artistic"]
    del saved["processing_options"]["default_batch_delay"]
    _save_user(user, saved)
    config, _p, _s = config_loader.load_json_config(NAME)
    assert "artistic" not in config["prompt_variations"]
    assert config["processing_options"] == {}


def test_reading_the_user_file_by_path_fills_in_too(installed):
    """Workers are handed the path (self.config_file) and read it explicitly."""
    app, user = installed
    _save_user(user, {"default_prompt_style": "artistic"})
    config, _p, source = config_loader.load_json_config(NAME, explicit=str(user / NAME))
    assert source == "explicit"
    assert config["default_prompt_style"] == "artistic"
    assert config["prompt_variations"] == SHIPPED["prompt_variations"]


def test_a_file_with_a_byte_order_mark_is_read(installed):
    """PowerShell 5's -Encoding UTF8 writes one; plain utf-8 dropped every setting."""
    app, user = installed
    user.mkdir(parents=True, exist_ok=True)
    (user / NAME).write_bytes(b"\xef\xbb\xbf" + json.dumps(
        dict(SHIPPED, default_prompt_style="artistic")).encode("utf-8"))
    assert config_loader.load_json_config(NAME)[0]["default_prompt_style"] == "artistic"


def test_an_unreadable_file_is_used_as_defaults_and_left_untouched(installed, caplog):
    """A file caught mid-save (or, before utf-8-sig, any file with a BOM) used to
    be overwritten by the one-time check with just its marker, deleting every
    setting and API key in it (#441 review)."""
    import logging
    app, user = installed
    user.mkdir(parents=True, exist_ok=True)
    cut_off = b'{"default_prompt_style": "artistic", "api_keys": {"claude": "sk-ant-'
    (user / NAME).write_bytes(cut_off)
    with caplog.at_level(logging.WARNING):
        config = config_loader.load_json_config(NAME)[0]
    assert config["default_prompt_style"] == "narrative"        # the defaults, this time
    assert "Couldn't read the settings" in caplog.text
    assert (user / NAME).read_bytes() == cut_off                 # byte for byte


def test_another_explicit_file_is_read_as_it_is(installed, tmp_path):
    other = tmp_path / "mine.json"
    other.write_text(json.dumps({"default_prompt_style": "concise"}), encoding="utf-8")
    config, _p, _s = config_loader.load_json_config(NAME, explicit=str(other))
    assert config == {"default_prompt_style": "concise"}


def test_saves_go_to_the_user_dir(installed):
    app, user = installed
    assert config_loader.writable_config_path(NAME) == user / NAME
    _save_user(user, SHIPPED)
    assert config_loader.writable_config_path(NAME) == user / NAME


def test_an_explicit_file_is_saved_where_it_is(installed, tmp_path):
    other = tmp_path / "mine.json"
    other.write_text("{}", encoding="utf-8")
    assert config_loader.writable_config_path(NAME, explicit=str(other)) == other


def test_configure_saves_where_processing_reads(installed):
    """The round trip, through Configure's own folder choice (no window opened)."""
    pytest.importorskip("wx", reason="wxPython not installed")
    import configure_dialog
    app, user = installed
    folder = configure_dialog.ConfigureDialog.find_scripts_directory(None)
    assert folder == user
    saved = json.loads((user / NAME).read_text(encoding="utf-8"))
    assert saved == SHIPPED, "seeded from the installed defaults"
    saved["default_prompt_style"] = "artistic"                   # what Change Setting does
    (user / NAME).write_text(json.dumps(saved), encoding="utf-8")
    assert config_loader.load_json_config(NAME)[0]["default_prompt_style"] == "artistic"


def test_configure_never_overwrites_saved_settings(installed):
    pytest.importorskip("wx", reason="wxPython not installed")
    import configure_dialog
    app, user = installed
    _save_user(user, {"default_prompt_style": "artistic"})
    configure_dialog.ConfigureDialog.find_scripts_directory(None)
    assert json.loads((user / NAME).read_text(encoding="utf-8")) == {"default_prompt_style": "artistic"}


def test_installer_no_longer_sets_idt_config_dir():
    iss = (_ROOT / "BuildAndRelease" / "WinBuilds" / "installer.iss").read_text(encoding="utf-8")
    assert "RegWriteStringValue(HKEY_CURRENT_USER, EnvironmentKey, 'IDT_CONFIG_DIR'" not in iss
    assert "RegDeleteValue(HKEY_CURRENT_USER, EnvironmentKey, 'IDT_CONFIG_DIR')" in iss


# --------------------------------------------------------------------------- #
# The one-time fix-up of copies Configure seeded before 4.9 read them           #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("old", ["moondream:latest", "moondream", "gemma3:latest"])
def test_an_old_shipped_default_model_gives_way_to_the_current_one(installed, old):
    """Seeded Feb-Jun 2026 with moondream:latest, which the installer no longer
    pulls: once that copy is read, every description would 404."""
    app, user = installed
    _save_user(user, dict(SHIPPED, default_model=old))
    config, _p, _s = config_loader.load_json_config(NAME)
    assert config["default_model"] == "minicpm-v4.6"
    on_disk = json.loads((user / NAME).read_text(encoding="utf-8"))
    assert "default_model" not in on_disk and on_disk[config_loader.MIGRATED_KEY] == "4.9"


def test_the_fix_up_runs_once_so_a_later_choice_sticks(installed):
    app, user = installed
    _save_user(user, dict(SHIPPED, default_model="moondream:latest"))
    config_loader.load_json_config(NAME)                     # the one-time fix-up
    saved = json.loads((user / NAME).read_text(encoding="utf-8"))
    saved["default_model"] = "moondream:latest"              # chosen again in Configure
    (user / NAME).write_text(json.dumps(saved), encoding="utf-8")
    assert config_loader.load_json_config(NAME)[0]["default_model"] == "moondream:latest"


def test_any_other_saved_model_is_kept(installed):
    app, user = installed
    _save_user(user, dict(SHIPPED, default_model="qwen3-vl:8b-instruct"))
    assert config_loader.load_json_config(NAME)[0]["default_model"] == "qwen3-vl:8b-instruct"


def test_from_source_the_repo_defaults_are_found_from_any_folder(tmp_path, monkeypatch):
    """CLAUDE.md's dev command runs from imagedescriber/, where cwd has no scripts/."""
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    path, source = config_loader.resolve_defaults(NAME)
    assert path == _ROOT / "scripts" / NAME


# --------------------------------------------------------------------------- #
# #411: the CLI kept the default model's tag                                    #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("saved, expected", [
    ("moondream:1.8b", "moondream:1.8b"),          # was "moondream": a 404
    ("qwen3-vl:8b-instruct", "qwen3-vl:8b-instruct"),  # was the thinking "qwen3-vl"
    ("minicpm-v4.6:latest", "minicpm-v4.6"),
    ("minicpm-v4.6", "minicpm-v4.6"),
])
def test_cli_default_model_keeps_its_tag(installed, saved, expected):
    from idt_core import config as idt_config
    app, user = installed
    _save_user(user, dict(SHIPPED, default_model=saved))
    _prompts, _prompt, model = idt_config._load_shared_config()
    assert model == expected
