"""
Three ImageDescriber problems Kelly hit on a Surface Laptop 7, 11/15/2026.

* Saving a 12,911-item photo library after adding two descriptions rewrote every
  item's sidecar. A save now writes only items that changed since the workspace
  was opened or last written.
* The Process dialog took 8-21 s to open. Every request to Ollama went to
  "localhost", which on Windows tries IPv6 first; Ollama listens on IPv4 only,
  so each request waited 2 s (2.06 s against 0.024 s for 127.0.0.1).
* Configure offered Apple Intelligence on Windows (and Windows AI on a Mac).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --------------------------------------------------------------------------- #
# localhost -> 127.0.0.1                                                       #
# --------------------------------------------------------------------------- #

from idt_core.providers import ollama as ollama_mod  # noqa: E402


@pytest.mark.parametrize("given, expected", [
    ("http://localhost:11434", "http://127.0.0.1:11434"),
    ("localhost:11434", "127.0.0.1:11434"),
    ("http://LOCALHOST:11434/", "http://127.0.0.1:11434/"),
    ("http://localhost", "http://127.0.0.1"),
    ("http://192.168.1.5:11434", "http://192.168.1.5:11434"),
    ("https://ollama.example.com", "https://ollama.example.com"),
    ("http://mylocalhost.example:11434", "http://mylocalhost.example:11434"),
])
def test_localhost_becomes_ipv4(given, expected):
    assert ollama_mod.normalize_host(given) == expected


def test_no_host_stays_the_sdk_default_unless_ollama_host_says_localhost(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert ollama_mod.normalize_host(None) is None
    monkeypatch.setenv("OLLAMA_HOST", "localhost:11434")
    assert ollama_mod.normalize_host(None) == "127.0.0.1:11434"
    monkeypatch.setenv("OLLAMA_HOST", "http://10.0.0.2:11434")
    assert ollama_mod.normalize_host(None) is None


def test_defaults_are_ipv4_everywhere(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert "localhost" not in ollama_mod.DEFAULT_HOST
    assert ollama_mod.OllamaProvider(model="m", host="http://localhost:11434")._host \
        == "http://127.0.0.1:11434"
    from idt_core.chat.providers import OllamaChatProvider
    assert OllamaChatProvider("m", host="http://localhost:11434")._host == "http://127.0.0.1:11434"
    import ai_providers
    assert ai_providers.OllamaProvider().base_url == "http://127.0.0.1:11434"
    assert ai_providers.OllamaProvider("http://localhost:11434").base_url == "http://127.0.0.1:11434"
    assert ai_providers.OllamaCloudProvider().base_url == "http://127.0.0.1:11434"


def test_no_source_file_points_at_localhost_any_more():
    for rel in ("cli/main.py", "cli/guide.py", "imagedescriber/ai_providers.py",
                "idt_core/providers/ollama.py"):
        text = (_ROOT / rel).read_text(encoding="utf-8")
        assert '"http://localhost:11434"' not in text, rel


# --------------------------------------------------------------------------- #
# Provider choices by platform                                                 #
# --------------------------------------------------------------------------- #

def _configure():
    pytest.importorskip("wx", reason="wxPython not installed in this environment")
    import configure_dialog
    return configure_dialog


@pytest.mark.parametrize("system, present, absent", [
    ("Windows", "windows-ai", "apple"),
    ("Darwin", "apple", "windows-ai"),
    ("Linux", None, "apple"),
])
def test_default_provider_choices_follow_the_platform(system, present, absent):
    choices, description = _configure().default_provider_choices(system)
    assert absent not in choices
    assert {"ollama", "openai", "claude", "claude-code"} <= set(choices)
    if present:
        assert present in choices
    if system == "Windows":
        assert "Apple" not in description and "Windows-AI" in description
    if system == "Darwin":
        assert "Windows-AI" not in description and "Apple Intelligence" in description


# --------------------------------------------------------------------------- #
# Saving only what changed                                                     #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def _frame():
    wx = pytest.importorskip("wx", reason="wxPython not installed in this environment")
    import imagedescriber_wx
    app = wx.App.Get() or wx.App(False)
    f = imagedescriber_wx.ImageDescriberFrame()
    yield f
    f.Destroy()
    wx.SafeYield()
    del app


@pytest.fixture
def frame(_frame, tmp_path, monkeypatch):
    """The frame with a saved 3-item workspace open, as after File > Open."""
    import imagedescriber_wx
    from data_models import ImageItem, ImageWorkspace
    from idt_core.gui_bridge import BundleCheckpointWriter
    from idt_core.workspace import Workspace

    src = tmp_path / "photos"
    src.mkdir()
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        (src / n).write_bytes(b"x")
    bundle = Workspace.create(tmp_path / "lib.idtw").path
    ws = ImageWorkspace(new_workspace=True)
    ws.directory_paths = [str(src)]
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        ws.add_item(ImageItem(str(src / n)))
    f = _frame
    monkeypatch.setattr(f, "workspace", ws)
    monkeypatch.setattr(f, "workspace_file", bundle)
    monkeypatch.setattr(f, "_checkpointer", BundleCheckpointWriter())
    monkeypatch.setattr(f, "_changed_seq", {})
    for name in ("show_error", "show_warning", "show_info"):
        monkeypatch.setattr(imagedescriber_wx, name, lambda *a, **k: None)
    f._save_bundle()                                   # everything on disk
    f._remember_saved(ws.to_dict()["items"], replace=True)
    return f, src


@pytest.fixture
def written(monkeypatch):
    from idt_core.workspace import Workspace
    names = []
    real = Workspace.save_item

    def spy(self, item):
        names.append(Path(str(item.source_path)).name if getattr(item, "source_path", None)
                     else str(item))
        return real(self, item)

    monkeypatch.setattr(Workspace, "save_item", spy)
    return names


def _describe(ws, path, text):
    from data_models import ImageDescription
    ws.items[str(path)].add_description(ImageDescription(text=text, model="m",
                                                         prompt_style="narrative"))


def test_a_save_writes_only_the_items_that_changed(frame, written):
    f, src = frame
    _describe(f.workspace, src / "b.jpg", "a blue boat")
    f._save_bundle()
    assert len(written) == 1 and "b.jpg" in written[0]


def test_an_unchanged_workspace_writes_no_items(frame, written):
    f, src = frame
    f._save_bundle()
    assert written == []


def test_the_change_is_on_disk(frame):
    from idt_core.workspace import Workspace
    f, src = frame
    _describe(f.workspace, src / "a.jpg", "a red barn")
    f._save_bundle()
    item = Workspace(f.workspace_file).get_item("a.jpg", None)
    assert [d.text for d in item.descriptions] == ["a red barn"]


def test_after_a_save_the_next_save_writes_nothing(frame, written):
    import wx
    f, src = frame
    _describe(f.workspace, src / "c.jpg", "a cat")
    f._save_bundle()
    wx.SafeYield()
    written.clear()
    f._save_bundle()
    assert written == []


def test_a_different_workspace_is_saved_in_full(frame, written):
    """The record belongs to one workspace and bundle; another one writes everything."""
    from data_models import ImageItem, ImageWorkspace
    f, src = frame
    other = ImageWorkspace(new_workspace=True)
    for n in ("a.jpg", "b.jpg", "c.jpg"):
        other.add_item(ImageItem(str(src / n)))
    f.workspace = other
    f._save_bundle()
    assert len(written) == 3
