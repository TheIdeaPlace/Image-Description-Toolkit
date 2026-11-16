"""Layered configuration loader for Image Description Toolkit.

Non-breaking helper used to allow external overrides of bundled JSON config
files without requiring a rebuild. If a higher-precedence source is not
present, existing bundled behavior is preserved.

Two layers: the user's settings over the shipped defaults.

Resolution order (first existing file wins):
 1. Explicit path (passed by caller)
 2. File env var (e.g. IDT_IMAGE_DESCRIBER_CONFIG)
 3. User config dir (platform-specific, writable) -- what Configure, the
    Prompt Editor and Import Configuration save:
      macOS  : ~/Library/Application Support/IDT/<filename>
      Windows: %APPDATA%\\IDT\\<filename>
      Linux  : ~/.config/IDT/<filename>
 4. The shipped defaults, first that exists:
      a. Directory env var IDT_CONFIG_DIR/<filename>
      b. Frozen exe dir /scripts/<filename>, then /<filename>
      c. Bundled data dir (sys._MEIPASS/scripts/)
      d. Current working directory ./scripts/<filename>, ./<filename>
      e. Bundled script directory (where this module lives)

The user file used to come after the exe's scripts folder, and the Windows
installer pointed IDT_CONFIG_DIR at that folder too. So on an installed copy
nothing changed in Configure ever reached processing or the CLI (found by the
NVDA bug bash, 11/15/2026), and writing to {app}\\scripts instead would be
undone by the installer, which replaces those files on every upgrade.

load_json_config() fills any top-level section the user file lacks from the
defaults (see merge_defaults), so a section added in a later release still
appears for someone whose saved copy predates it.

Each resolver returns (path, source_label) so callers can optionally log
which layer provided the config. Save to writable_config_path().
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

__all__ = [
    'get_user_config_dir',
    'resolve_config',
    'resolve_defaults',
    'load_json_config',
    'merge_defaults',
    'writable_config_path',
]


def get_user_config_dir() -> Path:
    """Return the platform-appropriate writable user config directory for IDT.

    macOS  : ~/Library/Application Support/IDT/
    Windows: %APPDATA%/IDT/   (C:/Users/<user>/AppData/Roaming/IDT/)
    Linux  : ~/.config/IDT/

    The directory is NOT created by this function — call .mkdir() at the
    write site so read paths never create the directory unnecessarily.

    IDT_USER_CONFIG_DIR replaces it: the test suite points it at a scratch
    folder, since this folder is now read before the shipped defaults and a
    developer's own saved settings must not change what a test sees.
    """
    override = os.environ.get('IDT_USER_CONFIG_DIR')
    if override:
        return Path(override)
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'IDT'
    elif sys.platform == 'win32':
        appdata = os.environ.get('APPDATA') or str(Path.home() / 'AppData' / 'Roaming')
        return Path(appdata) / 'IDT'
    else:
        # Linux / other POSIX
        xdg = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
        return Path(xdg) / 'IDT'

def _exists_file(p: Optional[Path]) -> bool:
    return bool(p and p.exists() and p.is_file())


def resolve_config(
    filename: str,
    explicit: Optional[str] = None,
    env_var_file: Optional[str] = None,
) -> Tuple[Path, str]:
    # 1 explicit
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = Path.cwd() / p
        if _exists_file(p):
            return p, 'explicit'

    # 2 file env var
    if env_var_file:
        env_val = os.getenv(env_var_file)
        if env_val:
            p = Path(env_val)
            if _exists_file(p):
                return p, env_var_file.lower()

    # 3 the user's own settings
    p = get_user_config_dir() / filename
    if _exists_file(p):
        return p, 'user_config'

    # 4 the shipped defaults
    return resolve_defaults(filename)


def resolve_defaults(filename: str) -> Tuple[Path, str]:
    """The shipped defaults for ``filename``, ignoring the user's saved copy."""
    cfg_dir = os.getenv('IDT_CONFIG_DIR')
    if cfg_dir:
        p = Path(cfg_dir) / filename
        if _exists_file(p):
            return p, 'idt_config_dir'

    exe_dir: Optional[Path] = None
    meipass_dir: Optional[Path] = None
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
        # In onefile mode, bundled data files land in sys._MEIPASS (temp extract dir)
        _meipass = getattr(sys, '_MEIPASS', None)
        if _meipass:
            meipass_dir = Path(_meipass)

    script_dir = Path(__file__).parent

    candidates = []
    if exe_dir:
        candidates.append(exe_dir / 'scripts' / filename)
        candidates.append(exe_dir / filename)
    # onefile bundle: data files extracted to _MEIPASS/scripts/ (per spec datas dest)
    if meipass_dir:
        candidates.append(meipass_dir / 'scripts' / filename)
        candidates.append(meipass_dir / filename)
    candidates.append(Path.cwd() / 'scripts' / filename)
    candidates.append(Path.cwd() / filename)
    candidates.append(script_dir / filename)

    for c in candidates:
        if _exists_file(c):
            # _MEIPASS first: in a Windows folder build it is <exe dir>\<app>-lib,
            # INSIDE the exe dir, and its read-only defaults must still be
            # labelled 'bundled' so edits are written to the user config dir.
            if meipass_dir and c.is_relative_to(meipass_dir):
                return c, 'bundled'
            if exe_dir and c.is_relative_to(exe_dir):
                if 'scripts' in c.parts:
                    return c, 'exe_scripts'
                return c, 'exe_dir'
            if c.parent == Path.cwd():
                return c, 'cwd'
            if c.parent == script_dir:
                return c, 'bundled'
            return c, 'found'

    # fallback path (likely non-existent) for logging
    return script_dir / filename, 'missing_fallback'


def merge_defaults(user: dict, defaults: dict) -> dict:
    """``user`` with any top-level section it lacks taken from ``defaults``.

    Top level only, on purpose: a section the user has is theirs as saved.
    Filling in nested keys would bring back a built-in prompt style the user
    deleted in the Prompt Editor, and an API key entry or a Generation setting
    removed to mean "Automatic". A section added in a later release (as
    "generation" was in 4.9) still appears.
    """
    merged = dict(user)
    for key, default in defaults.items():
        merged.setdefault(key, default)
    return merged


def _read_json(path: Path):
    import json
    try:
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_json_config(
    filename: str,
    explicit: Optional[str] = None,
    env_var_file: Optional[str] = None,
):
    """``(config, path, source)``: the settings to use and the file they came from.

    The user's saved copy (or an explicit path naming it) has the shipped
    defaults filled in under it; an explicit path or file env var to some other
    file is read as it is.
    """
    path, source = resolve_config(filename, explicit=explicit, env_var_file=env_var_file)
    config = _read_json(path)
    if _is_user_file(path, filename):
        defaults_path, _ = resolve_defaults(filename)
        if _exists_file(defaults_path):
            config = merge_defaults(config, _read_json(defaults_path))
    return config, path, source


def _is_user_file(path: Path, filename: str) -> bool:
    try:
        return path.resolve() == (get_user_config_dir() / filename).resolve()
    except OSError:
        return False


def writable_config_path(filename: str, explicit: Optional[str] = None,
                         env_var_file: Optional[str] = None) -> Path:
    """Where a change to ``filename`` should be saved.

    An explicit file, or one named by its env var, is the caller's own choice;
    everything else goes to the user config dir, which is read before the
    shipped defaults and which no upgrade replaces. (The directory is not
    created here.)
    """
    path, source = resolve_config(filename, explicit=explicit, env_var_file=env_var_file)
    if source == 'explicit' or (env_var_file and source == env_var_file.lower()):
        return path
    return get_user_config_dir() / filename
