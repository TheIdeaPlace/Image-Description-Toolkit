"""
#415: About said "Version: 1.0.0" in every built copy.
#416: Check for Updates while offline read out a Python exception.

No windows are opened here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from idt_core import updater  # noqa: E402


# --------------------------------------------------------------------------- #
# #416                                                                         #
# --------------------------------------------------------------------------- #

def test_offline_says_to_check_the_connection():
    exc = requests.ConnectionError(
        "HTTPSConnectionPool(host='api.github.com', port=443): Max retries exceeded "
        "(Caused by NameResolutionError(... [Errno 11001] getaddrinfo failed))")
    message = updater.describe_check_error(exc)
    assert message == ("Couldn't reach GitHub to check for updates. "
                       "Check your internet connection, then try again.")
    for jargon in ("HTTPSConnectionPool", "Errno", "getaddrinfo", "api.github.com"):
        assert jargon not in message


def test_a_timeout_is_treated_as_offline():
    assert "internet connection" in updater.describe_check_error(requests.Timeout("read timed out"))


@pytest.mark.parametrize("status", [403, 429])
def test_rate_limit_says_to_wait(status):
    response = requests.Response()
    response.status_code = status
    message = updater.describe_check_error(requests.HTTPError(response=response))
    assert "asked too often" in message


def test_another_http_error_names_its_status():
    response = requests.Response()
    response.status_code = 502
    assert updater.describe_check_error(requests.HTTPError(response=response)) == (
        "GitHub couldn't answer the update check (error 502). Try again later.")


def test_anything_else_is_still_plain():
    assert updater.describe_check_error(ValueError("bad json at line 1 column 2")) == (
        "Couldn't check for updates. Try again later.")


def test_idt_update_prints_plain_words_and_puts_the_detail_on_stderr(monkeypatch, capsys):
    from cli import main as cli_main

    def offline(*a, **k):
        raise requests.ConnectionError("HTTPSConnectionPool(host='api.github.com')")

    monkeypatch.setattr(updater, "check_for_update", offline)
    monkeypatch.setattr(updater, "current_version", lambda: "4.9.0")
    cli_main.cmd_update(type("Args", (), {})())
    out, err = capsys.readouterr()
    assert "Couldn't reach GitHub" in out
    assert "HTTPSConnectionPool" not in out
    assert "HTTPSConnectionPool" in err


# --------------------------------------------------------------------------- #
# #415                                                                         #
# --------------------------------------------------------------------------- #

def _wx_common():
    pytest.importorskip("wx", reason="wxPython not installed")
    from shared import wx_common
    return wx_common


def test_a_built_copy_finds_version_in_its_bundled_data(tmp_path, monkeypatch):
    """The specs put VERSION in _MEIPASS, which wasn't searched."""
    wx_common = _wx_common()
    app = tmp_path / "ImageDescriber"
    lib = app / "imagedescriber-lib"
    lib.mkdir(parents=True)
    (lib / "VERSION").write_text("4.9.0\n", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "ImageDescriber.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(lib), raising=False)
    monkeypatch.chdir(tmp_path)
    assert wx_common.get_app_version() == "4.9.0"


def test_without_a_version_file_the_code_version_is_used(tmp_path, monkeypatch):
    """Never a made-up "1.0.0"."""
    wx_common = _wx_common()
    from idt_core import __version__
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "ImageDescriber.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "lib"), raising=False)
    monkeypatch.chdir(tmp_path)
    assert wx_common.get_app_version() == __version__


def test_from_source_the_repo_version_is_read(monkeypatch):
    wx_common = _wx_common()
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    expected = (_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert wx_common.get_app_version() == expected
