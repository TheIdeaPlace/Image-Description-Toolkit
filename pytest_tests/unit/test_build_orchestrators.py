"""Run the release orchestrators for real and check what they exit with.

Issue #228, P2. builditall_wx.bat exited 0 after BOTH application builds had
failed, and the packaging step shipped a three-week-old idt.exe into the
installer. builditall_macos.sh had the same silent success plus an
((x++))-under-set -e abort that killed the run before the summary.

test_batch_script_syntax.py and test_shell_script_safety.py already scan the
sources for the two specific traps, and they parametrize over every script
including ones added later. What neither can do is answer the question that
actually matters: given a sub-build that fails, what does the orchestrator
exit with? That was verified by hand during the fix and never written down.

These tests scaffold a throwaway project tree -- the real orchestrator, stub
sub-builds that do exactly what we tell them -- and run it. Four scenarios per
platform:

    both build            -> 0, fresh artifacts packaged
    a sub-build fails     -> 1
    a sub-build exits 0
      but emits nothing   -> 1        <- the silent-success bug
    ... with last run's
      artifact still there-> 1, and the stale binary is NOT packaged
                                       <- the shipped-a-three-week-old-exe bug
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

FRESH = "FRESH-BUILD-FROM-THIS-RUN"
STALE = "STALE-BINARY-FROM-A-PREVIOUS-RUN"

# What a stubbed sub-build should do.
OK = "ok"              # exit 0 and emit an artifact
FAILS = "fails"        # exit 1, emit nothing
SILENT = "silent"      # exit 0, emit nothing -- looks like success


# ===========================================================================
# Windows
# ===========================================================================

_WIN_ORCHESTRATOR = _ROOT / "BuildAndRelease" / "WinBuilds" / "builditall_wx.bat"

# Each app is a PyInstaller folder build: dist\<App>\<App>.exe plus its own
# contents folder dist\<App>\<lib>\ (4.9.0; one-file exes left %TEMP%\_MEI
# folders behind and showed a warning on close).
_WIN_APPS = (
    # (app dir, build script, folder/exe name, contents folder)
    ("idt", "build_idt.bat", "idt", "idt-lib"),
    ("imagedescriber", "build_imagedescriber_wx.bat", "ImageDescriber",
     "imagedescriber-lib"),
    ("chatapp", "build_chatapp.bat", "IDTChat", "idtchat-lib"),
)

LIB_ONLY = "lib-only"  # exit 0, emit the -lib folder but no exe
EXE_ONLY = "exe-only"  # exit 0, emit the exe but no -lib folder

_BAT_STUB = {
    OK: '@echo off\r\nmkdir dist\\{name}\\{lib} 2>nul\r\n'
        '>dist\\{name}\\{name}.exe echo {content}\r\n'
        '>dist\\{name}\\{lib}\\python312.dll echo {content}\r\nexit /b 0\r\n',
    FAILS: '@echo off\r\necho simulated compiler failure\r\nexit /b 1\r\n',
    SILENT: '@echo off\r\necho done.\r\nexit /b 0\r\n',
    LIB_ONLY: '@echo off\r\nmkdir dist\\{name}\\{lib} 2>nul\r\n'
              '>dist\\{name}\\{lib}\\python312.dll echo {content}\r\nexit /b 0\r\n',
    EXE_ONLY: '@echo off\r\nmkdir dist\\{name} 2>nul\r\n'
              '>dist\\{name}\\{name}.exe echo {content}\r\nexit /b 0\r\n',
}


def _scaffold_windows(tmp_path, idt=OK, describer=OK, chat=OK, stale=False):
    root = tmp_path / "repo"
    (root / "BuildAndRelease" / "WinBuilds").mkdir(parents=True)
    shutil.copy2(_WIN_ORCHESTRATOR,
                 root / "BuildAndRelease" / "WinBuilds" / "builditall_wx.bat")

    for (app, script, name, lib), behaviour in zip(_WIN_APPS, (idt, describer, chat)):
        (root / app).mkdir(exist_ok=True)
        (root / app / script).write_text(
            _BAT_STUB[behaviour].format(name=name, lib=lib, content=FRESH),
            encoding="ascii", newline="")
        if stale:
            folder = root / app / "dist" / name
            (folder / lib).mkdir(parents=True, exist_ok=True)
            (folder / f"{name}.exe").write_text(STALE, encoding="ascii")
            (folder / lib / "python312.dll").write_text(STALE, encoding="ascii")
            # and a one-file exe from before 4.9.0
            (root / app / "dist" / f"{name}.exe").write_text(STALE, encoding="ascii")

    (root / "README.md").write_text("readme", encoding="utf-8")
    (root / "LICENSE").write_text("license", encoding="utf-8")
    return root


def _run_windows(root):
    script = root / "BuildAndRelease" / "WinBuilds" / "builditall_wx.bat"
    proc = subprocess.run(
        ["cmd", "/c", str(script)],
        cwd=str(root / "BuildAndRelease" / "WinBuilds"),
        capture_output=True, text=True, errors="replace", timeout=120,
    )
    return proc


def _packaged(root):
    return root / "BuildAndRelease" / "WinBuilds" / "dist_all" / "bin"


windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="cmd.exe orchestrator")


@windows_only
def test_windows_success_exits_zero_and_packages_fresh_binaries(tmp_path):
    root = _scaffold_windows(tmp_path, idt=OK, describer=OK)

    proc = _run_windows(root)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    for _app, _script, name, lib in _WIN_APPS:
        packaged = _packaged(root) / f"{name}.exe"
        assert packaged.exists(), f"{name}.exe was not packaged\n{proc.stdout}"
        assert FRESH in packaged.read_text(encoding="ascii")
        # The exe can't start without its contents folder beside it.
        library = _packaged(root) / lib / "python312.dll"
        assert library.exists(), f"{lib} was not packaged\n{proc.stdout}"
        assert FRESH in library.read_text(encoding="ascii")


@windows_only
def test_windows_package_drops_libraries_from_the_last_package(tmp_path):
    """bin\\ is rebuilt from nothing: a library the new build no longer has must not ship."""
    root = _scaffold_windows(tmp_path)
    leftover = _packaged(root) / "imagedescriber-lib" / "removed_in_this_build.pyd"
    leftover.parent.mkdir(parents=True)
    leftover.write_text(STALE, encoding="ascii")

    proc = _run_windows(root)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not leftover.exists()


@windows_only
@pytest.mark.parametrize("behaviour", [LIB_ONLY, EXE_ONLY])
def test_windows_a_half_built_app_is_not_packaged(tmp_path, behaviour):
    """An exe without its -lib folder (or the reverse) is not a build."""
    root = _scaffold_windows(tmp_path, describer=behaviour)

    proc = _run_windows(root)

    assert proc.returncode != 0, proc.stdout


@windows_only
@pytest.mark.parametrize("idt,describer", [
    (FAILS, OK), (OK, FAILS), (FAILS, FAILS),
])
def test_windows_build_failure_exits_nonzero(tmp_path, idt, describer):
    """The original defect: this returned 0 with both builds broken."""
    root = _scaffold_windows(tmp_path, idt=idt, describer=describer)

    proc = _run_windows(root)

    assert proc.returncode != 0, (
        "orchestrator reported success after a build failure:\n" + proc.stdout
    )
    assert "Ready for distribution" not in proc.stdout


@windows_only
@pytest.mark.parametrize("idt,describer", [(SILENT, OK), (OK, SILENT)])
def test_windows_exit_zero_without_an_artifact_still_fails(tmp_path, idt,
                                                           describer):
    """A build step can exit 0 and emit nothing. That is not a build."""
    root = _scaffold_windows(tmp_path, idt=idt, describer=describer)

    proc = _run_windows(root)

    assert proc.returncode != 0, (
        "a sub-build exited 0 without producing an executable and the "
        "orchestrator called it a success:\n" + proc.stdout
    )


@windows_only
@pytest.mark.parametrize("idt,describer", [(SILENT, OK), (OK, SILENT)])
def test_windows_never_packages_the_previous_runs_binary(tmp_path, idt,
                                                         describer):
    """The exact shipped defect: a three-week-old idt.exe in the installer.

    dist/ still holds the last good build. This run emits nothing. Without the
    up-front delete, 'the artifact exists' proves nothing about THIS build and
    the stale binary gets packaged under a success banner.
    """
    root = _scaffold_windows(tmp_path, idt=idt, describer=describer, stale=True)

    proc = _run_windows(root)

    assert proc.returncode != 0, proc.stdout

    bin_dir = _packaged(root)
    if bin_dir.exists():
        for exe in (f for f in bin_dir.rglob("*") if f.is_file()):
            assert STALE not in exe.read_text(encoding="ascii"), (
                f"{exe.name} from a previous run was packaged as if it were "
                "built by this one"
            )


# ===========================================================================
# macOS
# ===========================================================================

_MAC_ORCHESTRATOR = _ROOT / "BuildAndRelease" / "MacBuilds" / "builditall_macos.sh"

_SH_STUB = {
    OK: '#!/bin/bash\nmkdir -p dist\n{emit}\nexit 0\n',
    FAILS: '#!/bin/bash\necho "simulated compiler failure"\nexit 1\n',
    SILENT: '#!/bin/bash\necho "done."\nexit 0\n',
}


def _scaffold_macos(tmp_path, idt=OK, describer=OK, chat=OK, stale=False):
    root = tmp_path / "repo"
    (root / "BuildAndRelease" / "MacBuilds").mkdir(parents=True)
    shutil.copy2(_MAC_ORCHESTRATOR,
                 root / "BuildAndRelease" / "MacBuilds" / "builditall_macos.sh")

    # The orchestrator shells out to these; stub both so the test exercises
    # the build/packaging logic rather than the validators.
    (root / "tools").mkdir()
    (root / "tools" / "pre_build_validation.py").write_text(
        "raise SystemExit(0)\n", encoding="utf-8")
    (root / "BuildAndRelease" / "validate_build.py").write_text(
        "raise SystemExit(0)\n", encoding="utf-8")

    # Git Bash on Windows has no python3; the validators are stubs anyway.
    binder = root / "stub_bin"
    binder.mkdir()
    (binder / "python3").write_text("#!/bin/sh\nexit 0\n",
                                    encoding="utf-8", newline="\n")
    os.chmod(binder / "python3", 0o700)

    emitters = {
        "idt": 'echo "{content}" > dist/idt',
        "imagedescriber": ('mkdir -p dist/ImageDescriber.app/Contents\n'
                           'echo "{content}" > '
                           'dist/ImageDescriber.app/Contents/marker'),
        "chatapp": ('mkdir -p dist/IDTChat.app/Contents\n'
                    'echo "{content}" > dist/IDTChat.app/Contents/marker'),
    }
    for app, behaviour, script in (
        ("idt", idt, "build_idt.sh"),
        ("imagedescriber", describer, "build_imagedescriber_wx.sh"),
        ("chatapp", chat, "build_chatapp.sh"),
    ):
        (root / app).mkdir(exist_ok=True)
        body = _SH_STUB[behaviour].format(
            emit=emitters[app].format(content=FRESH))
        (root / app / script).write_text(body, encoding="utf-8", newline="\n")
        os.chmod(root / app / script, 0o700)

    if stale:
        (root / "idt" / "dist").mkdir(parents=True, exist_ok=True)
        (root / "idt" / "dist" / "idt").write_text(STALE, encoding="utf-8")
        for app, bundle in (("imagedescriber", "ImageDescriber.app"),
                            ("chatapp", "IDTChat.app")):
            app_dir = root / app / "dist" / bundle / "Contents"
            app_dir.mkdir(parents=True, exist_ok=True)
            (app_dir / "marker").write_text(STALE, encoding="utf-8")

    (root / "README.md").write_text("readme", encoding="utf-8")
    (root / "LICENSE").write_text("license", encoding="utf-8")
    return root, binder


def _run_macos(root, binder):
    bash = shutil.which("bash")
    env = dict(os.environ)
    env["PATH"] = str(binder) + os.pathsep + env["PATH"]
    return subprocess.run(
        [bash, str(root / "BuildAndRelease" / "MacBuilds" / "builditall_macos.sh")],
        cwd=str(root), capture_output=True, text=True,
        errors="replace", timeout=120, env=env,
    )


needs_bash = pytest.mark.skipif(
    shutil.which("bash") is None, reason="bash not available")


@needs_bash
def test_macos_success_exits_zero_and_packages_fresh_artifacts(tmp_path):
    root, binder = _scaffold_macos(tmp_path, idt=OK, describer=OK)

    proc = _run_macos(root, binder)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    dist_all = root / "BuildAndRelease" / "MacBuilds" / "dist_all"
    assert (dist_all / "idt").exists(), proc.stdout
    assert (dist_all / "Applications" / "ImageDescriber.app").is_dir()
    assert (dist_all / "Applications" / "IDTChat.app").is_dir(), proc.stdout
    assert FRESH in (dist_all / "idt").read_text(encoding="utf-8")
    # Freshness, not just presence: a stale bundle left from a previous run
    # would satisfy is_dir() while shipping the wrong build.
    for bundle in ("ImageDescriber.app", "IDTChat.app"):
        marker = dist_all / "Applications" / bundle / "Contents" / "marker"
        assert FRESH in marker.read_text(encoding="utf-8"), bundle


@needs_bash
@pytest.mark.parametrize("idt,describer", [
    (FAILS, OK), (OK, FAILS), (FAILS, FAILS),
])
def test_macos_build_failure_exits_nonzero(tmp_path, idt, describer):
    """Under the old ((BUILD_ERRORS++)), set -e aborted here mid-run."""
    root, binder = _scaffold_macos(tmp_path, idt=idt, describer=describer)

    proc = _run_macos(root, binder)

    assert proc.returncode != 0, (
        "orchestrator reported success after a build failure:\n" + proc.stdout
    )


@needs_bash
@pytest.mark.parametrize("idt,describer", [(FAILS, OK), (OK, FAILS)])
def test_macos_still_prints_a_summary_after_a_failure(tmp_path, idt, describer):
    """The summary branch was dead code while set -e killed the run early."""
    root, binder = _scaffold_macos(tmp_path, idt=idt, describer=describer)

    proc = _run_macos(root, binder)

    assert "BUILD SUMMARY" in proc.stdout, (
        "the run died before reaching the summary:\n" + proc.stdout
    )
    assert "build failures encountered" in proc.stdout


@needs_bash
@pytest.mark.parametrize("idt,describer", [(SILENT, OK), (OK, SILENT)])
def test_macos_exit_zero_without_an_artifact_still_fails(tmp_path, idt,
                                                        describer):
    root, binder = _scaffold_macos(tmp_path, idt=idt, describer=describer)

    proc = _run_macos(root, binder)

    assert proc.returncode != 0, (
        "a sub-build exited 0 without producing an artifact and the "
        "orchestrator called it a success:\n" + proc.stdout
    )
    assert "Ready for DMG creation" not in proc.stdout


@needs_bash
@pytest.mark.parametrize("idt,describer", [(SILENT, OK), (OK, SILENT)])
def test_macos_never_packages_the_previous_runs_artifact(tmp_path, idt,
                                                         describer):
    """Never clean dist/ and the DMG ships whatever was left lying around."""
    root, binder = _scaffold_macos(tmp_path, idt=idt, describer=describer,
                                   stale=True)

    proc = _run_macos(root, binder)

    assert proc.returncode != 0, proc.stdout

    dist_all = root / "BuildAndRelease" / "MacBuilds" / "dist_all"
    if dist_all.exists():
        for path in dist_all.rglob("*"):
            if path.is_file():
                assert STALE not in path.read_text(
                    encoding="utf-8", errors="replace"), (
                    f"{path.name} from a previous run was packaged as if it "
                    "were built by this one"
                )
