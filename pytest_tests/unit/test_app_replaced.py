"""The app notices when it has been replaced on disk while open (11/20/2026).

Installing 4.9.0 over a running 4.9.0 pre-release made Settings fail with
"Operation not permitted" for a settings file that was fine.
"""
import os
import shutil
import sys

import pytest

from idt_core import app_replaced


@pytest.fixture
def frozen_exe(tmp_path, monkeypatch):
    exe = tmp_path / "ImageDescriber"
    exe.write_bytes(b"old build")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(app_replaced, "_started", None)
    app_replaced.remember()
    return exe


@pytest.mark.unit
def test_unchanged_executable_is_not_replaced(frozen_exe):
    assert not app_replaced.replaced()


@pytest.mark.unit
def test_install_over_the_running_app_is_noticed(frozen_exe, tmp_path):
    """The way a copy from the DMG replaces it: a new file at the same path."""
    new = tmp_path / "new"
    new.write_bytes(b"new build, different size")
    os.replace(new, frozen_exe)
    assert app_replaced.replaced()


@pytest.mark.unit
def test_moved_or_deleted_app_is_noticed(frozen_exe, tmp_path):
    shutil.move(str(frozen_exe), str(tmp_path / "Trash"))
    assert app_replaced.replaced()


@pytest.mark.unit
def test_running_from_source_never_reports_replaced(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(app_replaced, "_started", None)
    app_replaced.remember()
    assert not app_replaced.replaced()


@pytest.mark.unit
def test_notice_names_the_app_and_says_what_to_do(frozen_exe, monkeypatch):
    text = app_replaced.notice()
    assert "ImageDescriber" in text and "open it again" in text
    monkeypatch.setattr(sys, "executable", "/Applications/IDT/IDTChat.app/Contents/MacOS/IDTChat")
    assert app_replaced.notice().startswith("IDT Chat was updated")


@pytest.mark.unit
def test_error_boxes_lead_with_the_notice(frozen_exe, tmp_path):
    wx_common = pytest.importorskip("shared.wx_common")
    assert wx_common._with_replaced_notice("boom") == "boom"
    new = tmp_path / "new"
    new.write_bytes(b"new build, different size")
    os.replace(new, frozen_exe)
    message = wx_common._with_replaced_notice("Error -3 while decompressing data")
    assert message.startswith("ImageDescriber was updated")
    assert message.endswith("Error -3 while decompressing data")
