"""#421: ImageDescriber's chat window, as NVDA heard it in the bug bash.

- Chat Settings opened with focus on OK, so Tab went OK, Cancel, Provider,
  Model. It opens on Provider now.
- The title read "Chat: Chat - Ollama moondream:1.8b - 11/15/2026 9:49P":
  default chat names already start with "Chat".

The ChatDialog test opens a real wx window: CI and the test VM run it, not a
developer's PC.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if os.environ.get("IDT_REQUIRE_WX") == "1":
    import wx  # noqa: F401
else:
    wx = pytest.importorskip("wx", reason="wxPython not installed")

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("name, title", [
    ("Chat - Ollama moondream:1.8b - 11/15/2026 9:49P",
     "Chat - Ollama moondream:1.8b - 11/15/2026 9:49P"),
    ("chat about the beach", "chat about the beach"),
    ("Chat: beach.jpg", "Chat: beach.jpg"),
    ("Beach questions", "Chat: Beach questions"),
    # Starts with the letters but isn't the word.
    ("Chateau photos", "Chat: Chateau photos"),
])
def test_the_title_says_chat_once(name, title):
    from chat_window_wx import chat_window_title
    assert chat_window_title(name) == title


def test_chat_settings_opens_on_provider(monkeypatch):
    """Checked by spying on SetFocus rather than with FindFocus, which on
    macOS needs the test process to be the active app (as in
    test_mode_switch_focus.py)."""
    import wx
    import chat_window_wx

    focused = []
    monkeypatch.setattr(wx.Choice, "SetFocus", lambda self: focused.append(self))
    app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None)
    dlg = chat_window_wx.ChatDialog(frame, {}, cached_ollama_models=["llava"])
    try:
        assert focused and focused[-1] is dlg.provider_choice
        focused.clear()
        dlg.Show()
        wx.SafeYield()          # runs the CallAfter that refocuses once shown
        assert focused and focused[-1] is dlg.provider_choice
    finally:
        dlg.Destroy()
        frame.Destroy()
        del app
