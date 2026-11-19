"""What Configure, the Prompt Editor and Processing Options are called by a screen reader.

* #422: Configure's settings list read code names ("default_provider: ollama")
  and the dialog opened with its title and a header repeating it.
* #469: Configure's Default prompt style offered a fixed seven, missing
  accessibility, aialttext and every prompt added in the Prompt Editor.
* #417: the Prompt Editor's provider and model boxes had no name on Windows,
  its title read a file name, and it opened reading a note about --provider.
* #499: the Prompt Editor's API Key field saved a value nothing read.
* #418: Processing Options' model description box had no name on Windows.

The first group is windowless; the rest open dialogs (run them in the VM).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REQUIRE_WX = os.environ.get("IDT_REQUIRE_WX") == "1"
try:
    import wx
except ImportError as _exc:  # pragma: no cover
    if REQUIRE_WX:
        raise
    pytest.skip(f"wxPython unavailable: {_exc}", allow_module_level=True)

pytestmark = pytest.mark.unit

import configure_dialog  # noqa: E402
import prompt_editor_dialog  # noqa: E402


# --- windowless --------------------------------------------------------------

@pytest.mark.parametrize("code, shown", [
    ("default_provider", "Default provider"),
    ("default_model", "Default model"),
    ("default_prompt_style", "Default prompt style"),
    ("time_interval_seconds", "Time interval seconds"),
    ("html_report_title", "HTML report title"),
    ("metadata_enabled", "Metadata (location and date)"),
    ("extract_metadata", "Extract metadata"),
    ("Ollama top p", "Ollama top p"),          # Generation names are already plain
])
def test_settings_have_plain_names(code, shown):
    assert configure_dialog.setting_label(code) == shown


def test_no_setting_is_shown_with_an_underscore():
    meta = configure_dialog.ConfigureDialog.build_settings_metadata(
        type("Stub", (), {"_get_ollama_models": lambda self: [], "configs": {}})())
    for category, settings in meta.items():
        for code in settings:
            assert "_" not in configure_dialog.setting_label(code), (category, code)


def _metadata():
    return configure_dialog.ConfigureDialog.build_settings_metadata(
        type("Stub", (), {"_get_ollama_models": lambda self: [], "configs": {}})())


def test_no_two_settings_share_a_name():
    labels = [configure_dialog.setting_label(code)
              for settings in _metadata().values() for code in settings]
    assert len(labels) == len(set(labels)), sorted(l for l in labels if labels.count(l) > 1)


def test_choice_values_are_shown_without_underscores():
    for _category, settings in _metadata().items():
        for code, info in settings.items():
            if code == "default_model":
                continue                          # model ids are shown as they are
            for value in info.get("choices", []):
                assert "_" not in str(configure_dialog._display_value(info, value)), (code, value)


def test_default_provider_values_are_plain_names():
    meta = configure_dialog.ConfigureDialog.build_settings_metadata(
        type("Stub", (), {"_get_ollama_models": lambda self: [], "configs": {}})())
    info = meta["AI Model Settings"]["default_provider"]
    assert configure_dialog._display_value(info, "ollama") == "Ollama"
    assert configure_dialog._display_value(info, "openai") == "OpenAI"
    assert configure_dialog._display_value(info, "claude-code") == "Claude Code"
    # and what is picked is saved as the key
    assert configure_dialog._choice_value(info, "Claude Code") == "claude-code"


def test_prompt_styles_are_the_files_prompts_in_order():
    config = {"prompt_variations": {"narrative": "a", "accessibility": "b",
                                    "aialttext": "c", "museum_label": "d"}}
    assert configure_dialog.prompt_style_choices(config) == [
        "narrative", "accessibility", "aialttext", "museum_label"]


def test_the_shipped_prompts_are_all_offered():
    shipped = json.loads((_ROOT / "scripts" / "image_describer_config.json")
                         .read_text(encoding="utf-8"))
    offered = configure_dialog.prompt_style_choices(shipped)
    assert offered == list(shipped["prompt_variations"])
    assert "accessibility" in offered and "aialttext" in offered


@pytest.mark.parametrize("config", [None, {}, {"prompt_variations": {}},
                                    {"prompt_variations": "broken"}, "broken"])
def test_a_file_without_prompts_still_offers_the_shipped_names(config):
    assert configure_dialog.prompt_style_choices(config) == \
        configure_dialog._FALLBACK_PROMPT_STYLES


@pytest.mark.parametrize("provider", ["openai", "claude"])
def test_key_providers_say_where_to_add_a_key(provider):
    note = prompt_editor_dialog.api_key_note(provider)
    assert "API key" in note and "Configure" in note and "API Keys tab" in note


@pytest.mark.parametrize("provider", ["ollama", "claude-code", "windows-ai", ""])
def test_providers_without_keys_say_nothing(provider):
    assert prompt_editor_dialog.api_key_note(provider) == ""


# --- dialogs (VM) ------------------------------------------------------------

@pytest.fixture
def wx_app(monkeypatch):
    from idt_core.providers import catalog
    monkeypatch.setattr(catalog, "_api_key_for", lambda _p: "test-key")
    monkeypatch.setattr(
        catalog, "_fetch",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network in tests")))
    catalog.invalidate()

    # A message box would wait for a click that never comes: fail instead.
    def _no_message(*args, **_kwargs):
        raise AssertionError(f"a message box opened: {args}")
    for module in (prompt_editor_dialog, configure_dialog):
        for name in ("show_error", "show_warning", "show_info"):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, _no_message)
    monkeypatch.setattr(wx, "MessageBox", _no_message)
    app = wx.App.Get() or wx.App(False)
    yield app
    catalog.invalidate()


def _accessible_name(control):
    """The name a Windows screen reader gets; the plain name elsewhere."""
    try:
        acc = control.GetAccessible()
    except (NotImplementedError, AttributeError):
        acc = None
    if acc is None:
        return control.GetName()
    return acc.GetName(0)[1]


def _static_texts(win):
    out = []
    for child in win.GetChildren():
        if isinstance(child, wx.StaticText):
            out.append(child.GetLabel())
        out.extend(_static_texts(child))
    return out


def _user_config(prompts):
    """Write the user's settings file the dialogs read (the test's scratch dir)."""
    from idt_core.config_loader import get_user_config_dir
    user = get_user_config_dir()
    user.mkdir(parents=True, exist_ok=True)
    shipped = json.loads((_ROOT / "scripts" / "image_describer_config.json")
                         .read_text(encoding="utf-8"))
    shipped["prompt_variations"] = dict(shipped["prompt_variations"], **prompts)
    (user / "image_describer_config.json").write_text(json.dumps(shipped), encoding="utf-8")
    return user / "image_describer_config.json"


def test_configure_opens_with_one_short_title_and_plain_names(wx_app):
    _user_config({"museum_label": "Write a museum label."})
    dlg = configure_dialog.ConfigureDialog(None, cached_ollama_models=["moondream"])
    try:
        assert dlg.GetTitle() == "Configure"
        assert not any("Configuration Manager" in t for t in _static_texts(dlg))
        items = dlg.category_widgets["AI Model Settings"]["settings_list"].GetStrings()
        assert items[0].startswith("Default provider: ")
        assert items[1].startswith("Default model: ")
        for category, widgets in dlg.category_widgets.items():
            for item in widgets["settings_list"].GetStrings():
                assert "_" not in item.split(":", 1)[0], (category, item)
        # #469: the prompt list is the file's, custom prompt and all
        choices = dlg.settings_metadata["Prompt Styles"]["default_prompt_style"]["choices"]
        for name in ("narrative", "accessibility", "aialttext", "museum_label"):
            assert name in choices
    finally:
        dlg.Destroy()


def test_prompt_editor_names_its_boxes_and_has_no_key_field(wx_app):
    path = _user_config({})
    frame = wx.Frame(None)
    dlg = prompt_editor_dialog.PromptEditorDialog(frame)
    try:
        assert dlg.GetTitle() == "Prompt Editor"
        assert _accessible_name(dlg.provider_combo) == "AI provider"
        assert _accessible_name(dlg.default_model_combo) == "Default model"
        assert _accessible_name(dlg.default_prompt_combo) == "Default prompt style"
        assert not any("--provider" in t for t in _static_texts(dlg))
        assert not hasattr(dlg, "api_key_text")

        # A provider that needs a key says where to add one; Ollama says nothing.
        dlg.provider_combo.SetStringSelection("openai")
        dlg.on_provider_changed(None)
        assert dlg.key_note_text.IsShown()
        assert "API Keys tab" in dlg.key_note_text.GetValue()
        assert dlg.key_note_text.AcceptsFocusFromKeyboard()     # Tab reaches it
        assert _accessible_name(dlg.key_note_text) == "API key"
        dlg.provider_combo.SetStringSelection("ollama")
        dlg.on_provider_changed(None)
        assert not dlg.key_note_text.IsShown()

        # Saving writes no api_key, and the title never gains the file name.
        dlg.save_config_internal()
        assert "api_key" not in json.loads(path.read_text(encoding="utf-8"))
        assert "image_describer_config" not in dlg.GetTitle()
    finally:
        dlg.Destroy()
        frame.Destroy()


def test_saving_keeps_an_api_key_already_in_the_file(wx_app):
    path = _user_config({})
    data = json.loads(path.read_text(encoding="utf-8"))
    data["api_key"] = "typed-before"
    path.write_text(json.dumps(data), encoding="utf-8")
    frame = wx.Frame(None)
    dlg = prompt_editor_dialog.PromptEditorDialog(frame)
    try:
        dlg.save_config_internal()
        assert json.loads(path.read_text(encoding="utf-8"))["api_key"] == "typed-before"
    finally:
        dlg.Destroy()
        frame.Destroy()


def test_processing_options_names_the_model_description(wx_app):
    import dialogs_wx
    frame = wx.Frame(None)
    dlg = dialogs_wx.ProcessingOptionsDialog({"default_provider": "ollama"},
                                             cached_ollama_models=["moondream"], parent=frame)
    try:
        assert _accessible_name(dlg.model_desc_text) == "Model description"
    finally:
        dlg.Destroy()
        frame.Destroy()


@pytest.mark.parametrize("saved, shown", [("ollama", "Ollama"), ("claude-code", "Claude Code"),
                                          ("openai", "OpenAI")])
def test_change_setting_shows_the_provider_by_name_and_saves_the_key(wx_app, saved, shown):
    info = _metadata()["AI Model Settings"]["default_provider"]
    dlg = configure_dialog.SettingEditDialog(None, "default_provider", saved, info)
    try:
        assert dlg.GetTitle() == "Edit: Default provider"
        assert dlg.editor.GetStringSelection() == shown
        assert dlg.GetValue() == saved
    finally:
        dlg.Destroy()


def test_change_setting_keeps_a_provider_the_list_does_not_offer(wx_app):
    info = _metadata()["AI Model Settings"]["default_provider"]
    dlg = configure_dialog.SettingEditDialog(None, "default_provider", "someday", info)
    try:
        assert dlg.editor.GetStringSelection() == "someday (current)"
        assert dlg.GetValue() == "someday"
    finally:
        dlg.Destroy()
