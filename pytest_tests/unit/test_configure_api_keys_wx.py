"""Configure > API Keys: Add/Replace Key for the selected provider, and Test Key.

Kelly (11/2026): arrowing to Claude and choosing Add Key opened a dialog that
asked which provider again. Now the key button acts on the selected row, its
label says whether it adds or replaces, and the dialog has no provider list.
Test Key checks the selected provider's key with one tiny request.

Opens real (hidden) wx windows, so it runs in the test VM, not on Kelly's PC.
Message boxes, the credential store and the network are all stubbed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _import_wx():
    """wx, or a skip -- a failure instead when IDT_REQUIRE_WX=1 (test_gui_smoke.py's rule)."""
    if os.environ.get("IDT_REQUIRE_WX") == "1":
        import wx   # a missing wx is an ImportError, failing the test
        return wx
    return pytest.importorskip("wx", reason="wxPython is not installed")


@pytest.fixture
def env(monkeypatch):
    """A hidden Configure dialog whose key sources are a dict we control."""
    wx = _import_wx()
    monkeypatch.syspath_prepend(str(_ROOT / "imagedescriber"))
    monkeypatch.syspath_prepend(str(_ROOT))
    app = wx.App.Get() or wx.App(False)
    import configure_dialog
    import idt_core.keys as keys

    sources = {"openai": None, "claude": "credential store", "ollama.com": None}
    monkeypatch.setattr(keys, "key_source", lambda provider: sources.get(provider))
    dlg = configure_dialog.ConfigureDialog(None)
    monkeypatch.setattr(dlg, "_save_image_describer_config", lambda: None)
    monkeypatch.setattr(dlg, "_reload_provider_api_keys", lambda: None)
    dlg.load_api_keys()
    yield dlg, configure_dialog, wx, sources
    if dlg:
        dlg.Destroy()
    del app


def _select(dlg, provider):
    for i in range(dlg.api_keys_list.GetCount()):
        if dlg.api_keys_list.GetClientData(i) == provider:
            dlg.api_keys_list.SetSelection(i)
            dlg.on_api_key_selected(None)
            return
    raise AssertionError(f"no row for {provider}")


def _capture_dialog(monkeypatch, cfg, wx, result=None, key="new-key"):
    """Stub ApiKeyEditDialog.ShowModal: record the dialog, answer OK or Cancel."""
    seen = []

    def show(self):
        seen.append({"title": self.GetTitle(), "choice": self.provider_choice,
                     "first_focus": self.first_focus, "key_box": self.key_text,
                     "key_name": self.key_text.GetName()})
        self.key_text.SetValue(key)
        return result if result is not None else wx.ID_CANCEL

    monkeypatch.setattr(cfg.ApiKeyEditDialog, "ShowModal", show)
    return seen


# --------------------------------------------------------------------------- #
# Add / Replace Key                                                             #
# --------------------------------------------------------------------------- #

def test_a_row_is_selected_once_the_list_is_filled(env):
    dlg, _cfg, wx, _ = env
    assert dlg.api_keys_list.GetSelection() != wx.NOT_FOUND


def test_add_key_on_a_selected_row_has_no_provider_list(env, monkeypatch):
    dlg, cfg, wx, _ = env
    _select(dlg, "openai")
    seen = _capture_dialog(monkeypatch, cfg, wx)
    dlg.on_add_api_key(None)
    assert seen[0]["choice"] is None, "the provider must not be asked for again"
    assert seen[0]["title"] == "Add OpenAI API Key"
    assert seen[0]["first_focus"] is seen[0]["key_box"]
    assert seen[0]["key_name"] == "OpenAI API key"


def test_replace_key_when_the_provider_has_one(env, monkeypatch):
    dlg, cfg, wx, _ = env
    _select(dlg, "claude")
    assert dlg.add_key_btn.GetLabel() == "Replace Key"
    seen = _capture_dialog(monkeypatch, cfg, wx)
    dlg.on_add_api_key(None)
    assert seen[0]["title"] == "Replace Claude (Anthropic) API Key"
    assert seen[0]["choice"] is None


def test_button_label_follows_the_selection(env):
    dlg, _cfg, _wx, _ = env
    _select(dlg, "openai")
    assert dlg.add_key_btn.GetLabel() == "Add Key"
    assert not dlg.delete_key_btn.IsEnabled()
    _select(dlg, "claude")
    assert dlg.add_key_btn.GetLabel() == "Replace Key"
    assert dlg.delete_key_btn.IsEnabled()


def test_ok_saves_under_the_selected_provider(env, monkeypatch):
    dlg, cfg, wx, sources = env
    _select(dlg, "openai")
    stored = []
    monkeypatch.setattr(dlg, "_store_key", lambda p, k: stored.append((p, k)) or True)
    _capture_dialog(monkeypatch, cfg, wx, result=wx.ID_OK, key="typed")
    dlg.on_add_api_key(None)
    assert stored == [("openai", "typed")]
    assert dlg._selected_api_key_provider() == "openai", "selection stays on the row"


def test_without_a_provider_the_list_is_still_offered(env):
    dlg, cfg, _wx, _ = env
    plain = cfg.ApiKeyEditDialog(dlg)
    try:
        assert plain.provider_choice is not None
        assert plain.first_focus is plain.provider_choice
        assert plain.GetTitle() == "Add API Key"
    finally:
        plain.Destroy()


def test_unrecognised_row_is_replaced_in_the_config_file(env, monkeypatch):
    dlg, cfg, wx, _ = env
    dlg.configs.setdefault("image_describer", {})["api_keys"] = {"Gemini": "old"}
    dlg.load_api_keys()
    _select(dlg, "Gemini")
    assert dlg.add_key_btn.GetLabel() == "Replace Key"
    assert not dlg.test_key_btn.IsEnabled(), "IDT can't test an unrecognised provider"
    stored = []
    monkeypatch.setattr(dlg, "_store_key", lambda p, k: stored.append((p, k)) or True)
    seen = _capture_dialog(monkeypatch, cfg, wx, result=wx.ID_OK, key="newer")
    dlg.on_add_api_key(None)
    assert seen[0]["title"] == "Replace Gemini API Key"
    assert stored == [], "not into the credential store, where nothing reads it"
    assert dlg.configs["image_describer"]["api_keys"]["Gemini"] == "newer"


# --------------------------------------------------------------------------- #
# Test Key                                                                     #
# --------------------------------------------------------------------------- #

class _SyncThread:
    def __init__(self, target=None, name=None, daemon=None):
        self.target = target

    def start(self):
        self.target()


@pytest.fixture
def sync(monkeypatch, env):
    """Run the test's thread at once and hold its CallAfter until we release it."""
    import threading

    _dlg, cfg, _wx, _ = env
    queued = []
    monkeypatch.setattr(threading, "Thread", _SyncThread)
    monkeypatch.setattr(cfg.wx, "CallAfter", lambda fn, *a: queued.append((fn, a)))
    monkeypatch.setattr(cfg.wx, "CallLater", lambda ms, fn, *a: None)
    return queued


def test_test_key_is_off_without_a_key_and_on_with_one(env):
    dlg, _cfg, _wx, sources = env
    _select(dlg, "openai")
    assert not dlg.test_key_btn.IsEnabled()
    _select(dlg, "claude")
    assert dlg.test_key_btn.IsEnabled()
    sources["ollama.com"] = "environment"
    dlg.load_api_keys()           # sources are read once per load, not per arrow
    _select(dlg, "ollama.com")
    assert dlg.test_key_btn.IsEnabled()


def test_test_key_runs_and_shows_the_result(env, sync, monkeypatch):
    dlg, _cfg, _wx, _ = env
    from idt_core import key_check

    asked = []

    def fake(provider):
        asked.append(provider)
        return key_check.KeyTestResult(
            True, "Your Claude key works. That test cost 0.00038 cents.",
            3.8e-6, "claude-haiku-5-5", "Your Claude key works.")

    monkeypatch.setattr(key_check, "test_api_key", fake)
    _select(dlg, "claude")
    assert dlg.on_test_api_key(None) is True
    assert asked == ["claude"]
    # Running: the box says so and Test Key is off.
    assert dlg.key_test_result.GetValue() == "Testing your Claude (Anthropic) key..."
    assert not dlg.test_key_btn.IsEnabled()
    assert dlg.on_test_api_key(None) is False, "no second test while one runs"
    fn, args = sync.pop()
    fn(*args)
    # A key that works: one line, so it's read whole.
    assert dlg.key_test_result.GetValue() == (
        "Your Claude key works. That test cost 0.00038 cents.")
    assert dlg.test_key_btn.IsEnabled()


def test_failure_puts_the_verdict_on_the_first_line(env, sync, monkeypatch):
    dlg, _cfg, _wx, _ = env
    from idt_core import key_check

    monkeypatch.setattr(key_check, "test_api_key", lambda p: key_check.KeyTestResult(
        False, "Claude didn't accept this key. Copy it again.", None, "",
        "Claude didn't accept this key."))
    _select(dlg, "claude")
    dlg.on_test_api_key(None)
    fn, args = sync.pop()
    fn(*args)
    assert dlg.key_test_result.GetValue() == (
        "Claude didn't accept this key.\nCopy it again.")


def test_changing_the_key_during_a_test_drops_its_answer(env, sync, monkeypatch):
    dlg, cfg, wx, _ = env
    from idt_core import key_check

    monkeypatch.setattr(key_check, "test_api_key",
                        lambda p: key_check.KeyTestResult(True, "works"))
    monkeypatch.setattr(dlg, "_store_key", lambda p, k: True)
    _select(dlg, "claude")
    dlg.on_test_api_key(None)
    fn, args = sync.pop()
    _capture_dialog(monkeypatch, cfg, wx, result=wx.ID_OK, key="another")
    dlg.on_add_api_key(None)
    assert dlg.key_test_result.GetValue() == dlg.KEY_CHANGED_DURING_TEST
    fn(*args)                                   # the old key's answer arrives
    assert dlg.key_test_result.GetValue() == dlg.KEY_CHANGED_DURING_TEST
    assert dlg.test_key_btn.IsEnabled()


def test_deleting_the_key_during_a_test_drops_its_answer(env, sync, monkeypatch):
    dlg, cfg, _wx, sources = env
    from idt_core import key_check
    import idt_core.keys as keys
    import shared.wx_common as common

    monkeypatch.setattr(key_check, "test_api_key",
                        lambda p: key_check.KeyTestResult(True, "works"))
    monkeypatch.setattr(keys, "delete_api_key", lambda p: sources.update({p: None}) or True)
    monkeypatch.setattr(common, "ask_yes_no", lambda *a, **k: True)
    _select(dlg, "claude")
    dlg.on_test_api_key(None)
    fn, args = sync.pop()
    dlg.on_delete_api_key(None)
    fn(*args)
    assert dlg.key_test_result.GetValue() == dlg.KEY_CHANGED_DURING_TEST
    assert dlg.add_key_btn.GetLabel() == "Add Key"
    assert not dlg.test_key_btn.IsEnabled()


def test_a_stale_result_is_dropped(env, sync, monkeypatch):
    dlg, _cfg, _wx, _ = env
    from idt_core import key_check

    monkeypatch.setattr(key_check, "test_api_key",
                        lambda p: key_check.KeyTestResult(True, "works"))
    _select(dlg, "claude")
    dlg.on_test_api_key(None)
    fn, args = sync.pop()
    dlg._key_test_token = None          # as if the test had been abandoned
    dlg.key_test_result.ChangeValue("unchanged")
    fn(*args)
    assert dlg.key_test_result.GetValue() == "unchanged"


def test_a_result_after_the_dialog_is_gone_is_ignored(env, sync, monkeypatch):
    dlg, _cfg, _wx, _ = env
    from idt_core import key_check

    monkeypatch.setattr(key_check, "test_api_key",
                        lambda p: key_check.KeyTestResult(True, "works"))
    _select(dlg, "claude")
    dlg.on_test_api_key(None)
    fn, args = sync.pop()
    dlg.Destroy()
    _cfg.wx.GetApp().ProcessPendingEvents()   # let the deferred delete happen
    fn(*args)                                  # must not raise


def test_selecting_another_row_resets_the_result_unless_testing(env, sync, monkeypatch):
    dlg, _cfg, _wx, _ = env
    from idt_core import key_check

    monkeypatch.setattr(key_check, "test_api_key",
                        lambda p: key_check.KeyTestResult(True, "works"))
    _select(dlg, "claude")
    dlg.on_test_api_key(None)
    _select(dlg, "openai")
    assert dlg.key_test_result.GetValue().startswith("Testing"), "kept while running"
    fn, args = sync.pop()
    fn(*args)
    _select(dlg, "openai")
    assert dlg.key_test_result.GetValue() == dlg.KEY_TEST_INTRO


def test_tab_order_reaches_the_result_after_the_buttons(env):
    dlg, _cfg, wx, _ = env
    panel = dlg.api_keys_list.GetParent()
    order = [c for c in panel.GetChildren()
             if not isinstance(c, (wx.StaticText, wx.StaticBox))]
    names = [c for c in (dlg.api_keys_list, dlg.add_key_btn, dlg.test_key_btn,
                         dlg.delete_key_btn, dlg.key_test_result)]
    positions = [order.index(c) for c in names]
    assert positions == sorted(positions)
    assert dlg.key_test_result.GetName() == "Test result"
