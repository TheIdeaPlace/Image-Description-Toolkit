"""
shared.uia_notify: the screen reader announcement that replaced the chat window's
focus bounce (#410). Windowless: the Windows DLLs are faked.
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared import uia_notify  # noqa: E402


class _FakeOle:
    def __init__(self):
        self.allocated, self.freed = [], []

        class _Alloc:
            restype = None

            def __call__(inner, text):
                self.allocated.append(text.value)
                return 1000 + len(self.allocated)
        self.SysAllocString = _Alloc()

    def SysFreeString(self, bstr):
        self.freed.append(bstr.value)


class _FakeUia:
    def __init__(self, host_hr=0, raise_hr=0, provider=0):
        self.host_hr, self.raise_hr, self.provider = host_hr, raise_hr, provider
        self.raised = []

    def UiaHostProviderFromHwnd(self, hwnd, out):
        return self.host_hr          # leaves the provider NULL: nothing to Release

    def UiaRaiseNotificationEvent(self, provider, kind, processing, display, activity):
        self.raised.append((kind, processing, display.value, activity.value))
        return self.raise_hr


def test_no_text_or_window_does_nothing():
    assert uia_notify.notify(0, "hello", api=(_FakeUia(), _FakeOle())) is False
    assert uia_notify.notify(123, "", api=(_FakeUia(), _FakeOle())) is False


def test_without_uia_it_says_so_so_the_caller_can_fall_back(monkeypatch):
    monkeypatch.setattr(uia_notify, "_api", lambda: None)
    assert uia_notify.notify(123, "hello") is False


class _FakeNvda:
    """nvdaControllerClient.dll's two calls used here."""

    def __init__(self, running=True, speak_rc=0):
        self.running, self.speak_rc, self.spoken = running, speak_rc, []

    def nvdaController_testIfRunning(self):
        return 0 if self.running else 1717      # RPC_S_UNKNOWN_IF when NVDA isn't running

    def nvdaController_speakText(self, text):
        self.spoken.append(text.value)
        return self.speak_rc


def test_nvda_speaks_it_and_uia_is_not_used():
    """NVDA ignores UIA notifications from wx windows; its controller client
    spoke the whole reply in the test VM (NVDA 2026.2, 11/16/2026)."""
    nvda, uia = _FakeNvda(), _FakeUia()
    assert uia_notify.notify(123, "A red barn.", api=(uia, _FakeOle()), nvda=nvda) is True
    assert nvda.spoken == ["A red barn."] and uia.raised == []


def test_without_nvda_running_uia_is_used(monkeypatch):
    uia = _FakeUia()

    def host(hwnd, out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 4242
        return 0
    uia.UiaHostProviderFromHwnd = host
    monkeypatch.setattr(uia_notify, "_release", lambda p: None)
    nvda = _FakeNvda(running=False)
    assert uia_notify.notify(123, "hello", api=(uia, _FakeOle()), nvda=nvda) is True
    assert nvda.spoken == [] and len(uia.raised) == 1


def test_a_test_passing_only_api_never_reaches_nvda(monkeypatch):
    called = []
    monkeypatch.setattr(uia_notify, "speak_with_nvda", lambda *a, **k: called.append(a) or True)
    uia_notify.notify(123, "hello", api=(_FakeUia(), _FakeOle()))
    assert called == []


def test_the_controller_client_is_shipped_for_each_build_architecture():
    for arch in ("x64", "arm64"):
        dll = _ROOT / "shared" / "nvda" / arch / "nvdaControllerClient.dll"
        assert dll.is_file() and dll.stat().st_size > 100_000, arch
    assert (_ROOT / "shared" / "nvda" / "license.txt").is_file()
    spec = (_ROOT / "imagedescriber" / "imagedescriber_wx.spec").read_text(encoding="utf-8")
    assert "'shared/nvda/x64'" in spec and "'shared/nvda/arm64'" in spec
    # IDT Chat announces replies the same way (#439).
    chat_spec = (_ROOT / "chatapp" / "chatapp.spec").read_text(encoding="utf-8")
    assert "'shared/nvda/x64'" in chat_spec and "'shared/nvda/arm64'" in chat_spec
    assert "'shared.uia_notify'" in chat_spec


def test_not_on_windows_there_is_no_api(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert uia_notify._api() is None


def test_a_refused_host_provider_is_a_failure():
    uia, ole = _FakeUia(host_hr=-2147024809), _FakeOle()
    assert uia_notify.notify(123, "hello", api=(uia, ole)) is False
    assert uia.raised == []


def test_raises_the_notification_and_frees_the_strings(monkeypatch):
    uia, ole = _FakeUia(), _FakeOle()

    def host(hwnd, out):
        # A non-NULL provider, as Windows returns; Release is faked below.
        ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 4242
        return 0
    uia.UiaHostProviderFromHwnd = host
    released = []
    monkeypatch.setattr(uia_notify, "_release", lambda p: released.append(p.value))

    assert uia_notify.notify(123, "A red barn.", activity_id="idt-chat-reply",
                             api=(uia, ole)) is True
    kind, processing, display, activity = uia.raised[0]
    assert kind == uia_notify.NOTIFICATION_KIND_ACTION_COMPLETED
    assert processing == uia_notify.NOTIFICATION_PROCESSING_IMPORTANT_MOST_RECENT
    assert ole.allocated == ["A red barn.", "idt-chat-reply"]
    assert sorted(ole.freed) == sorted([display, activity])
    assert released == [4242]


def test_a_failed_raise_is_reported(monkeypatch):
    uia, ole = _FakeUia(raise_hr=-1), _FakeOle()

    def host(hwnd, out):
        ctypes.cast(out, ctypes.POINTER(ctypes.c_void_p))[0] = 4242
        return 0
    uia.UiaHostProviderFromHwnd = host
    monkeypatch.setattr(uia_notify, "_release", lambda p: None)
    assert uia_notify.notify(123, "hello", api=(uia, ole)) is False
    assert len(ole.freed) == 2
