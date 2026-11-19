"""4.9.0 bug bash, group GHI: error wording, the video dialog, the HTML report.

* #477 -- the no-key message says where to add a key, not "or SDK not installed".
* #476 -- Claude or OpenAI with no connection says so, not "Server error",
  and is still retried.
* #467 -- `idt describe` with no Claude or OpenAI key fails once, up front,
  with the same message `idt chat` gives, not once per picture.
* #437 -- Extract Video Frames opens at Configure's saved values, and an empty
  Max frames per video means no limit in scene-change mode.
* #465 -- the HTML report's alt is short; the description is printed once.

Windowless: no wx.App, no windows, no network, no real API keys.
"""
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "imagedescriber"))

import ai_providers  # noqa: E402
from ai_providers import (  # noqa: E402
    ErrorKind, ProviderError, RETRYABLE_KINDS, _is_retryable_error,
    classify_provider_exception, format_provider_error, provider_error_from_exception,
)

pytestmark = pytest.mark.unit

TS = "2026-11-19 10:00:00,000"


@pytest.fixture
def no_keys(monkeypatch):
    """No key anywhere: environment, credential store, config or key files."""
    from idt_core import keys
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(keys, "_from_store", lambda name: None)
    monkeypatch.setattr(keys, "_from_legacy_file", lambda name: None)
    return keys


# ------------------------------------------------------------------ #
# #476: no connection                                                  #
# ------------------------------------------------------------------ #

class APIConnectionError(Exception):
    """Shaped like anthropic/openai's: no status_code attribute."""


class APITimeoutError(APIConnectionError):
    pass


class _Status(Exception):
    def __init__(self, code):
        super().__init__(f"status {code}")
        self.status_code = code


class TestNoConnection:
    def test_a_dropped_connection_is_a_connection_error(self):
        assert classify_provider_exception(APIConnectionError("Connection error.")) == \
            (ErrorKind.CONNECTION, None)

    def test_it_is_still_retried(self):
        assert ErrorKind.CONNECTION in RETRYABLE_KINDS
        text = provider_error_from_exception(
            APIConnectionError("Connection error."), "Claude API", timestamp=TS)
        assert _is_retryable_error(text)

    def test_the_wording_says_check_the_connection(self):
        text = provider_error_from_exception(
            APIConnectionError("Connection error."), "Claude API", timestamp=TS)
        assert text.startswith("Couldn't connect to Claude. Check your internet connection. ")
        assert "Server error" not in text
        assert "Claude API" not in text

    def test_openai_reads_the_same_way(self):
        text = format_provider_error("OpenAI API", ErrorKind.CONNECTION, timestamp=TS)
        assert text.startswith("Couldn't connect to OpenAI. ")

    def test_a_timeout_is_still_a_timeout(self):
        kind, _ = classify_provider_exception(APITimeoutError("Request timed out."))
        assert kind == ErrorKind.TIMEOUT

    @pytest.mark.parametrize("code", [408, 409, 500, 503])
    def test_real_server_answers_are_still_server_errors(self, code):
        kind, status = classify_provider_exception(_Status(code))
        assert (kind, status) == (ErrorKind.SERVER_ERROR, code)

    def test_a_raised_provider_error_carries_the_kind(self):
        err = ProviderError("x", provider="Claude API", kind=ErrorKind.CONNECTION)
        assert err.is_retryable


# ------------------------------------------------------------------ #
# #477: no key, in ImageDescriber                                      #
# ------------------------------------------------------------------ #

class TestNoKeyMessage:
    @pytest.mark.parametrize("cls,name", [
        (ai_providers.ClaudeProvider, "Claude"),
        (ai_providers.OpenAIProvider, "OpenAI"),
    ])
    def test_says_where_to_add_a_key(self, cls, name, no_keys, monkeypatch):
        provider = cls()
        provider.api_key = None
        provider.client = None
        with pytest.raises(ProviderError) as info:
            provider.describe_image("missing.jpg", "Describe.", "some-model")
        message = str(info.value)
        assert message.startswith(f"Error: No {name} API key. Add one in ")
        assert "API Keys tab" in message
        assert "SDK" not in message
        # Arrows are read aloud as "right arrow"
        assert "→" not in message and "->" not in message
        assert info.value.kind == ErrorKind.UNAVAILABLE
        assert not info.value.is_retryable

    def test_windows_names_the_tools_menu(self, monkeypatch):
        monkeypatch.setattr(ai_providers.sys, "platform", "win32")
        assert ai_providers.unavailable_message("Claude", has_key=False) == \
            "No Claude API key. Add one in Tools, Configure Settings, on the API Keys tab."

    def test_mac_names_preferences(self, monkeypatch):
        monkeypatch.setattr(ai_providers.sys, "platform", "darwin")
        assert "Preferences" in ai_providers.unavailable_message("Claude", has_key=False)

    def test_a_key_without_the_sdk_says_so(self):
        assert ai_providers.unavailable_message("Claude", has_key=True, has_sdk=False) == \
            "The Claude SDK is not installed."

    def test_a_key_whose_client_failed_does_not_blame_the_sdk(self):
        message = ai_providers.unavailable_message("Claude", has_key=True, has_sdk=True)
        assert "SDK" not in message and "couldn't start" in message

    def test_cli_message_names_preferences_on_a_mac(self, monkeypatch):
        from idt_core import keys
        monkeypatch.setattr(keys.sys, "platform", "darwin")
        assert "Preferences, API Keys" in keys.missing_key_message("Claude")
        monkeypatch.setattr(keys.sys, "platform", "win32")
        assert "Tools, Configure Settings, API Keys" in keys.missing_key_message("Claude")


# ------------------------------------------------------------------ #
# #467: no key, in idt describe                                        #
# ------------------------------------------------------------------ #

class TestDescribeChecksTheKeyFirst:
    @pytest.mark.parametrize("provider,shown,var", [
        ("anthropic", "Claude", "ANTHROPIC_API_KEY"),
        ("openai", "OpenAI", "OPENAI_API_KEY"),
    ])
    def test_no_key_stops_before_any_picture(self, provider, shown, var, no_keys, capsys):
        from cli.main import _make_provider
        with pytest.raises(SystemExit) as info:
            _make_provider(provider, None, "http://localhost:11434")
        assert info.value.code == 1
        err = capsys.readouterr().err
        assert err.startswith(f"Error: No API key found for {shown}.")
        assert var in err
        assert "API Keys" in err      # Tools, Configure Settings on Windows; Preferences on a Mac
        assert "Could not resolve authentication method" not in err

    def test_the_message_matches_idt_chat(self, no_keys, capsys):
        from cli.main import _make_provider
        with pytest.raises(SystemExit):
            _make_provider("anthropic", None, "")
        assert no_keys.missing_key_message("Claude") in capsys.readouterr().err

    @pytest.mark.parametrize("provider", ["anthropic", "openai"])
    def test_a_found_key_is_used(self, provider, monkeypatch):
        """The resolved key is handed to the provider; nothing is sent."""
        from idt_core import keys
        monkeypatch.setattr(keys, "resolve_api_key", lambda name: f"test-{name}-key")
        from cli.main import _make_provider
        made = _make_provider(provider, None, "")
        expected = "test-claude-key" if provider == "anthropic" else "test-openai-key"
        assert made._client.api_key == expected

    def test_ollama_needs_no_key(self, no_keys):
        from cli.main import _make_provider
        assert _make_provider("ollama", None, "http://localhost:11434") is not None


# ------------------------------------------------------------------ #
# #437: Extract Video Frames and Configure                             #
# ------------------------------------------------------------------ #

class TestVideoDialogDefaults:
    @pytest.fixture
    def dialog_cls(self):
        pytest.importorskip("wx")
        from dialogs_wx import VideoExtractionDialog
        return VideoExtractionDialog

    def test_opens_at_saved_values(self, dialog_cls):
        got = dialog_cls.initial_settings({
            "extraction_mode": "scene_change",
            "time_interval_seconds": 2,
            "scene_change_threshold": 12.5,
        })
        assert got == {"extraction_mode": "scene_change",
                       "time_interval_seconds": 2.0,
                       "scene_change_threshold": 12.5}

    @pytest.mark.parametrize("saved", [None, {}])
    def test_nothing_saved_gives_shipped_defaults(self, dialog_cls, saved):
        assert dialog_cls.initial_settings(saved) == {
            "extraction_mode": "time_interval",
            "time_interval_seconds": 5.0,
            "scene_change_threshold": 30.0}

    @pytest.mark.parametrize("bad", ["abc", -3, 1e9, True, float("nan")])
    def test_unusable_saved_numbers_fall_back(self, dialog_cls, bad):
        got = dialog_cls.initial_settings({"extraction_mode": "nonsense",
                                           "time_interval_seconds": bad,
                                           "scene_change_threshold": bad})
        assert got == {"extraction_mode": "time_interval",
                       "time_interval_seconds": 5.0,
                       "scene_change_threshold": 30.0}

    def test_shipped_config_matches_the_fallbacks(self, dialog_cls):
        import json
        shipped = json.loads((_ROOT / "scripts" / "video_frame_extractor_config.json")
                             .read_text(encoding="utf-8"))
        assert dialog_cls.initial_settings(shipped) == dialog_cls.initial_settings(None)
        # 50, the cap scene detection always had: an empty field now means no
        # limit, and shipping that would let a long, busy video send hundreds
        # of frames to a paid provider by default.
        assert shipped["max_frames_per_video"] == 50


class TestExtractVideoUsesSavedSettings:
    """on_extract_video, run without a window: what reaches the dialog and worker."""

    def test_saved_settings_reach_dialog_and_worker(self, monkeypatch, tmp_path):
        pytest.importorskip("wx")
        import json
        from types import SimpleNamespace
        import imagedescriber_wx as gui

        user_dir = Path(__import__("os").environ["IDT_USER_CONFIG_DIR"])
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "video_frame_extractor_config.json").write_text(json.dumps({
            "extraction_mode": "time_interval", "time_interval_seconds": 2.0,
            "scene_change_threshold": 30.0, "max_frames_per_video": None,
            "start_time_seconds": 3, "end_time_seconds": 40,
            "min_scene_duration_seconds": 1.0}), encoding="utf-8")

        seen = {}

        class FakeDialog:
            def __init__(self, parent, video, defaults=None):
                seen["defaults"] = defaults

            def ShowModal(self):
                return gui.wx.ID_OK

            def get_settings(self):
                # As the real dialog returns it when accepted unchanged
                return {"extraction_mode": "time_interval",
                        "time_interval_seconds": seen["defaults"]["time_interval_seconds"],
                        "process_after_extraction": False}

            def Destroy(self):
                pass

        class FakeWorker:
            def __init__(self, parent, video, config):
                seen["config"] = config

            def start(self):
                pass

        monkeypatch.setattr(gui, "VideoExtractionDialog", FakeDialog)
        monkeypatch.setattr(gui, "VideoProcessingWorker", FakeWorker)
        monkeypatch.setattr(gui, "cv2", object())
        frame = SimpleNamespace(
            _refuse_if_batch_busy=lambda: False,
            current_image_item=SimpleNamespace(item_type="video", file_path="clip.mp4"),
            _ensure_saved_bundle=lambda why: True,
            _frames_dir_for_video=lambda v: tmp_path / "frames",
            SetStatusText=lambda *a: None,
        )
        frame._load_video_extraction_config = \
            lambda: gui.ImageDescriberFrame._load_video_extraction_config(frame)

        gui.ImageDescriberFrame.on_extract_video(frame, None)

        assert seen["defaults"]["time_interval_seconds"] == 2.0
        config = seen["config"]
        assert config["time_interval_seconds"] == 2.0
        assert config["start_time_seconds"] == 3 and config["end_time_seconds"] == 40
        assert "max_frames_per_video" in config and config["max_frames_per_video"] is None


@pytest.fixture
def wx_app():
    """Opens a dialog: CI and the test VM only, never a developer's PC."""
    import os
    if os.environ.get("IDT_REQUIRE_WX") == "1":
        import wx
    else:
        wx = pytest.importorskip("wx")
    application = wx.App.Get() or wx.App(False)
    yield wx
    del application


class TestVideoDialogWindow:
    def test_scene_mode_saved_opens_in_scene_mode(self, wx_app):
        from dialogs_wx import VideoExtractionDialog
        dlg = VideoExtractionDialog(None, "clip.mp4", defaults={
            "extraction_mode": "scene_change", "time_interval_seconds": 2.0,
            "scene_change_threshold": 12.0})
        try:
            assert dlg.scene_radio.GetValue() and not dlg.time_radio.GetValue()
            assert dlg.scene_input.IsEnabled() and not dlg.time_input.IsEnabled()
            assert float(dlg.scene_input.GetValue()) == 12.0
            assert float(dlg.time_input.GetValue()) == 2.0
            assert dlg.get_settings()["scene_change_threshold"] == 12.0
        finally:
            dlg.Destroy()

    def test_saved_interval_is_what_ok_returns(self, wx_app):
        """The exact defect: accepting the dialog as it opened gave 5 seconds."""
        from dialogs_wx import VideoExtractionDialog
        dlg = VideoExtractionDialog(None, "clip.mp4", defaults={
            "extraction_mode": "time_interval", "time_interval_seconds": 2})
        try:
            assert dlg.time_radio.GetValue()
            settings = dlg.get_settings()
            assert settings["extraction_mode"] == "time_interval"
            assert settings["time_interval_seconds"] == 2.0
        finally:
            dlg.Destroy()

    def test_no_defaults_still_opens_at_five_seconds(self, wx_app):
        from dialogs_wx import VideoExtractionDialog
        dlg = VideoExtractionDialog(None)
        try:
            assert dlg.time_radio.GetValue()
            assert dlg.get_settings()["time_interval_seconds"] == 5.0
        finally:
            dlg.Destroy()


class _FlickerCapture:
    """A fake cv2.VideoCapture: n frames, alternating black and white."""

    def __init__(self, n):
        import numpy as np
        self._frames = [np.full((8, 8, 3), 255 * (i % 2), dtype=np.uint8) for i in range(n)]

    def read(self):
        if not self._frames:
            return False, None
        return True, self._frames.pop(0)


class TestNoLimitMeansNoLimit:
    CONFIG = {"scene_change_threshold": 10.0, "min_scene_duration_seconds": 0.0}

    def _worker(self, config, tmp_path):
        pytest.importorskip("cv2")
        pytest.importorskip("wx")
        from workers_wx import VideoProcessingWorker
        worker = object.__new__(VideoProcessingWorker)
        worker.extraction_config = config
        worker.video_path = str(tmp_path / "clip.mp4")
        return worker

    def test_worker_empty_limit_extracts_every_scene(self, tmp_path):
        worker = self._worker({**self.CONFIG, "max_frames_per_video": None}, tmp_path)
        frames = worker._extract_by_scene_detection_basic(_FlickerCapture(121), 1000.0, tmp_path)
        assert len(frames) == 120          # not stopped at 50

    def test_worker_set_limit_still_stops(self, tmp_path):
        worker = self._worker({**self.CONFIG, "max_frames_per_video": 7}, tmp_path)
        frames = worker._extract_by_scene_detection_basic(_FlickerCapture(121), 1000.0, tmp_path)
        assert len(frames) == 7

    def _frame_extract(self, config, tmp_path):
        pytest.importorskip("cv2")
        pytest.importorskip("wx")
        from imagedescriber_wx import ImageDescriberFrame
        return ImageDescriberFrame._extract_by_scene_detection(
            None, _FlickerCapture(121), 1000.0, tmp_path, config, tmp_path / "clip.mp4")

    def test_process_all_empty_limit_extracts_every_scene(self, tmp_path):
        assert len(self._frame_extract({**self.CONFIG, "max_frames_per_video": None},
                                       tmp_path)) == 120

    def test_process_all_missing_limit_is_no_limit(self, tmp_path):
        assert len(self._frame_extract(dict(self.CONFIG), tmp_path)) == 120

    def test_process_all_set_limit_still_stops(self, tmp_path):
        assert len(self._frame_extract({**self.CONFIG, "max_frames_per_video": 9},
                                       tmp_path)) == 9


# ------------------------------------------------------------------ #
# #465: the HTML report's alt                                          #
# ------------------------------------------------------------------ #

DESC = "A red barn under a grey sky, with a tractor parked by the open door."


@pytest.fixture
def ws(tmp_path):
    from PIL import Image
    from idt_core.workspace import Workspace, WorkspaceDescription

    src = tmp_path / "Photos"
    src.mkdir()
    w = Workspace.create(tmp_path / "report", name="report", copy_originals=False)
    p = src / "barn.jpg"
    Image.new("RGB", (16, 16), "red").save(p, "JPEG")
    item = w.add_image(p, copy=False)
    item.add_description(WorkspaceDescription.create(DESC, provider="claude", model="m"))
    w.save_item(item)
    w.save_manifest()
    return w


class TestReportAlt:
    def test_alt_is_short_and_description_appears_once(self, ws):
        from idt_core.exporter import export_workspace_html
        html = export_workspace_html(ws).read_text(encoding="utf-8")
        assert re.findall(r'alt="([^"]*)"', html) == ["barn.jpg, described below"]
        assert html.count(DESC) == 1

    def test_heic_uses_the_converted_jpeg(self, ws):
        from idt_core.exporter import export_workspace_html
        item = ws.items()[0]
        conv = ws.path / "derived" / "converted" / "barn.jpg"
        conv.parent.mkdir(parents=True, exist_ok=True)
        conv.write_bytes(b"jpeg")
        item.converted = str(conv.relative_to(ws.path))
        ws.save_item(item)
        html = export_workspace_html(ws).read_text(encoding="utf-8")
        assert 'src="../derived/converted/barn.jpg"' in html

    def test_a_missing_converted_copy_falls_back_to_the_image(self, ws):
        from idt_core.exporter import export_workspace_html
        item = ws.items()[0]
        item.converted = "derived/converted/gone.jpg"
        ws.save_item(item)
        html = export_workspace_html(ws).read_text(encoding="utf-8")
        assert "gone.jpg" not in html
        assert "barn.jpg" in html
