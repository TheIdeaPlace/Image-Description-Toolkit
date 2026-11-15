"""
The Windows apps are PyInstaller folder builds, not one-file exes (4.9.0).

A one-file exe unpacks itself into %TEMP%\\_MEIxxxxxx on every start and deletes
the folder on exit. ImageDescriber and IDT Chat still held a file there when they
closed, so the bootloader showed "Failed to remove temporary directory" after the
window had gone, and left the folder behind each time. A folder build unpacks
nothing. These checks keep each piece of the chain in step: spec, packaging,
installer, CI and release.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

APPS = [
    # (spec, exe/folder name, contents folder)
    ("idt/idt.spec", "idt", "idt-lib"),
    ("imagedescriber/imagedescriber_wx.spec", "ImageDescriber", "imagedescriber-lib"),
    ("chatapp/chatapp.spec", "IDTChat", "idtchat-lib"),
]


def _text(rel):
    return (_ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.parametrize("spec, name, lib", APPS, ids=[a[1] for a in APPS])
def test_spec_builds_a_folder_on_windows(spec, name, lib):
    text = _text(spec)
    assert re.search(r"platform == 'win32'", text), spec
    assert "exclude_binaries=True" in text, spec
    assert f"contents_directory='{lib}'" in text, spec
    assert re.search(rf"COLLECT\(exe, a\.binaries, a\.datas,.*?name='{name}'\)", text, re.S), spec


def test_every_app_has_its_own_contents_folder():
    """All three exes go into one install folder; a shared name would overwrite."""
    libs = [lib for _s, _n, lib in APPS]
    assert len(set(libs)) == len(libs)


@pytest.mark.parametrize("spec, name, lib", APPS, ids=[a[1] for a in APPS])
def test_spec_still_builds_one_file_on_macos(spec, name, lib):
    """The Mac tarball, DMG and signing scripts expect a single binary."""
    text = _text(spec)
    assert re.search(r"else:\s*\n(\s*#.*\n)*\s*exe = EXE\(pyz, a\.scripts, a\.binaries, a\.datas, \[\]", text), spec


@pytest.mark.parametrize("script", ["BuildAndRelease/WinBuilds/builditall_wx.bat",
                                    "BuildAndRelease/WinBuilds/package_all_windows.bat"])
def test_packaging_copies_each_whole_folder(script):
    text = _text(script)
    for _spec, name, lib in APPS:
        assert re.search(rf'xcopy /E /I /Q /Y "[^"]*dist\\{name}" "[^"]*dist_all\\bin"', text), (script, name)
        assert f"{lib}\"" in text, (script, lib)    # checked before packaging
    assert "rmdir /S /Q" in text and "dist_all\\bin" in text


def test_installer_ships_and_refreshes_every_contents_folder():
    iss = _text("BuildAndRelease/WinBuilds/installer.iss")
    for _spec, name, lib in APPS:
        assert f'Source: "dist_all\\bin\\{name}.exe"; DestDir: "{{app}}"' in iss
        assert re.search(
            rf'Source: "dist_all\\bin\\{lib}\\\*"; DestDir: "\{{app\}}\\{lib}"; '
            rf'Flags: [^\n]*recursesubdirs createallsubdirs', iss), lib
        assert f'Type: filesandordirs; Name: "{{app}}\\{lib}"' in iss, lib


def test_ci_signs_the_exe_inside_each_folder():
    yml = _text(".github/workflows/build-windows.yml")
    for app_dir, name in (("idt", "idt"), ("imagedescriber", "ImageDescriber"), ("chatapp", "IDTChat")):
        assert f"files-folder: ${{{{ github.workspace }}}}\\{app_dir}\\dist\\{name}\n" in yml.replace("\r\n", "\n")
        assert f'"{app_dir}\\dist\\{name}\\{name}.exe"' in yml


def test_release_publishes_standalone_zips_not_bare_exes():
    yml = _text(".github/workflows/release.yml")
    for name in ("idt", "ImageDescriber", "IDTChat"):
        assert f"release/{name}-*-windows-x64.zip" in yml
        assert f"release/{name}-*-windows-x64.exe" not in yml
