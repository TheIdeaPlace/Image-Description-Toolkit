"""
Code paths that behave differently once the Windows apps are folder builds (#404).

In a one-file build sys._MEIPASS was a temp folder; in a folder build it is
<exe dir>\\<app>-lib, INSIDE the exe's folder, and it lasts until an update
replaces the folder. Anything that decided "bundled, read-only" by checking the
exe folder first now mislabels it, and anything written there is lost on update.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture
def folder_build(tmp_path, monkeypatch):
    """A frozen ImageDescriber folder build: exe dir with its -lib folder."""
    app = tmp_path / "ImageDescriber"
    lib = app / "imagedescriber-lib"
    (lib / "scripts").mkdir(parents=True)
    (lib / "scripts" / "image_describer_config.json").write_text("{}", encoding="utf-8")
    (app / "ImageDescriber.exe").write_bytes(b"")
    user = tmp_path / "user"
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()

    from idt_core import config_loader
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(app / "ImageDescriber.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(lib), raising=False)
    monkeypatch.setattr(config_loader, "get_user_config_dir", lambda: user)
    monkeypatch.delenv("IDT_CONFIG_DIR", raising=False)
    monkeypatch.delenv("IDT_IMAGE_DESCRIBER_CONFIG", raising=False)
    monkeypatch.chdir(elsewhere)
    return app, lib, user


def test_bundled_config_inside_the_exe_folder_is_still_bundled(folder_build):
    """Labelled 'exe_scripts', the prompt editor saved edits into the -lib folder."""
    from idt_core.config_loader import resolve_config
    app, lib, user = folder_build
    path, source = resolve_config("image_describer_config.json")
    assert path == lib / "scripts" / "image_describer_config.json"
    assert source == "bundled"


def test_a_scripts_folder_beside_the_exe_still_wins(folder_build):
    """The installed layout ({app}\\scripts) is unchanged."""
    from idt_core.config_loader import resolve_config
    app, lib, user = folder_build
    (app / "scripts").mkdir()
    (app / "scripts" / "image_describer_config.json").write_text("{}", encoding="utf-8")
    path, source = resolve_config("image_describer_config.json")
    assert path == app / "scripts" / "image_describer_config.json"
    assert source == "exe_scripts"


def test_the_user_config_beats_the_bundled_copy(folder_build):
    from idt_core.config_loader import resolve_config
    app, lib, user = folder_build
    user.mkdir()
    (user / "image_describer_config.json").write_text("{}", encoding="utf-8")
    assert resolve_config("image_describer_config.json") == (
        user / "image_describer_config.json", "user_config")


def test_import_configuration_never_writes_into_the_lib_folder(folder_build):
    pytest.importorskip("wx", reason="wxPython not installed")
    from shared import wx_common
    app, lib, user = folder_build
    assert wx_common.find_scripts_directory() == lib / "scripts"     # for reading
    assert wx_common.writable_scripts_directory() == user            # for writing
    assert user.is_dir()


def test_import_configuration_writes_beside_the_installed_exe(folder_build):
    pytest.importorskip("wx", reason="wxPython not installed")
    from shared import wx_common
    app, lib, user = folder_build
    (app / "scripts").mkdir()
    assert wx_common.writable_scripts_directory() == app / "scripts"


# --------------------------------------------------------------------------- #
# idt describe --showgui finds ImageDescriber in the standalone zips' layout    #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("layout", ["same-folder", "sibling-folders", "nested"])
def test_showgui_finds_imagedescriber(tmp_path, monkeypatch, layout):
    from cli import main as cli_main
    idt_dir = tmp_path / "idt"
    idt_dir.mkdir()
    gui = {
        "same-folder": idt_dir / "ImageDescriber.exe",
        "sibling-folders": tmp_path / "ImageDescriber" / "ImageDescriber.exe",
        "nested": idt_dir / "ImageDescriber" / "ImageDescriber.exe",
    }[layout]
    gui.parent.mkdir(parents=True, exist_ok=True)
    gui.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(idt_dir / "idt.exe"))
    assert cli_main._resolve_gui_launch() == [str(gui)]


def test_showgui_does_not_launch_a_folder(tmp_path, monkeypatch):
    """An ImageDescriber FOLDER beside idt.exe with no exe in it is not the GUI."""
    from cli import main as cli_main
    idt_dir = tmp_path / "idt"
    (idt_dir / "ImageDescriber").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(idt_dir / "idt.exe"))
    assert cli_main._resolve_gui_launch() is None


# --------------------------------------------------------------------------- #
# package_all_windows.bat, run for real (CI runs it after signing)             #
# --------------------------------------------------------------------------- #

_APPS = (("idt", "idt", "idt-lib"),
         ("imagedescriber", "ImageDescriber", "imagedescriber-lib"),
         ("chatapp", "IDTChat", "idtchat-lib"))


def _scaffold_package(tmp_path, skip_lib_for=None):
    root = tmp_path / "repo"
    win = root / "BuildAndRelease" / "WinBuilds"
    win.mkdir(parents=True)
    shutil.copy2(_ROOT / "BuildAndRelease" / "WinBuilds" / "package_all_windows.bat",
                 win / "package_all_windows.bat")
    for app_dir, name, lib in _APPS:
        folder = root / app_dir / "dist" / name
        folder.mkdir(parents=True)
        (folder / f"{name}.exe").write_text("signed", encoding="ascii")
        if name != skip_lib_for:
            (folder / lib / "sub").mkdir(parents=True)
            (folder / lib / "python3.dll").write_text("lib", encoding="ascii")
            (folder / lib / "sub" / "x.pyd").write_text("lib", encoding="ascii")
    return win


def _run(win):
    return subprocess.run(["cmd", "/c", str(win / "package_all_windows.bat")], cwd=str(win),
                          capture_output=True, text=True, errors="replace", timeout=120)


windows_only = pytest.mark.skipif(sys.platform != "win32", reason="cmd.exe script")


@windows_only
def test_package_all_copies_every_folder_and_clears_old_files(tmp_path):
    win = _scaffold_package(tmp_path)
    stale = win / "dist_all" / "bin" / "idtchat-lib" / "gone.pyd"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="ascii")

    proc = _run(win)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    bin_dir = win / "dist_all" / "bin"
    for _app, name, lib in _APPS:
        assert (bin_dir / f"{name}.exe").read_text(encoding="ascii") == "signed"
        assert (bin_dir / lib / "sub" / "x.pyd").exists()
    assert not stale.exists()


@windows_only
def test_package_all_refuses_an_app_without_its_lib_folder(tmp_path):
    win = _scaffold_package(tmp_path, skip_lib_for="IDTChat")
    proc = _run(win)
    assert proc.returncode == 1
    assert "idtchat-lib" in proc.stdout
