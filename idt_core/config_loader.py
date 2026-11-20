"""Layered configuration loader for Image Description Toolkit.

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
    'settings_access_report',
    'SETTINGS_FILES',
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
    if not exe_dir:
        # Run from source: the repo's scripts/ folder, wherever the cwd is
        # (CLAUDE.md's dev command runs from imagedescriber/).
        candidates.append(Path(__file__).resolve().parent.parent / 'scripts' / filename)
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
    """The file's settings: a dict, or None if the file exists but can't be read.

    utf-8-sig accepts a byte-order mark: PowerShell 5's ``-Encoding UTF8``
    writes one, and plain utf-8 then failed to parse the whole file, so every
    saved setting was dropped without a word (real-service check, 11/16/2026).
    None (with a warning) rather than {}, so a caller never mistakes a file it
    couldn't read -- one caught mid-save, say -- for an empty one and writes
    over it (#441 review: _migrate_once did exactly that, deleting the file's
    settings and API keys).
    """
    import json
    import logging
    if not _exists_file(path):
        return {}
    try:
        with path.open('r', encoding='utf-8-sig') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:                                     # noqa: BLE001
        logging.getLogger(__name__).warning(
            "Couldn't read the settings in %s, so they weren't used this time "
            "(the file is left as it is): %s", path, exc)
        return None


def load_json_config(
    filename: str,
    explicit: Optional[str] = None,
    env_var_file: Optional[str] = None,
):
    """``(config, path, source)``: the settings to use and the file they came from.

    The user's saved copy (or an explicit path naming it) has the shipped
    defaults filled in under it; an explicit path or file env var to some other
    file is read as it is. A user file that can't be read is left untouched and
    the defaults are used.
    """
    path, source = resolve_config(filename, explicit=explicit, env_var_file=env_var_file)
    config = _read_json(path)
    readable = config is not None
    config = config or {}
    if _is_user_file(path, filename):
        if readable:
            config = _migrate_once(path, filename, config)
        defaults_path, _ = resolve_defaults(filename)
        if _exists_file(defaults_path):
            config = merge_defaults(config, _read_json(defaults_path) or {})
    return config, path, source


#: Marks a user copy as checked by _migrate_once, so it is checked only once.
MIGRATED_KEY = "_settings_checked_by"
#: Default models IDT shipped before minicpm-v4.6 (June 2026).
_OLD_SHIPPED_MODELS = {"moondream", "moondream:latest", "gemma3:latest"}


def _migrate_once(path: Path, filename: str, config: dict) -> dict:
    """One-time fix-up of a user copy written before 4.9 read it first.

    Configure copied every shipped file into the user folder the first time it
    opened. On an installed Windows copy those copies were never read, so the
    one that can now hurt is a stale shipped default model: moondream:latest
    until June 2026, which the installer no longer pulls, so every
    description would fail with a 404. A default model equal to an old shipped
    default is removed, so the current one fills in. Done once, and marked, so
    choosing moondream yourself afterwards sticks.

    Only ever called with a file that was read successfully, and written
    through a temporary file, so a reader never sees it half-written.
    """
    if filename != 'image_describer_config.json' or MIGRATED_KEY in config:
        return config
    config = dict(config)
    if config.get('default_model') in _OLD_SHIPPED_MODELS:
        del config['default_model']
    config[MIGRATED_KEY] = "4.9"
    try:
        import json
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')
        os.replace(temp, path)
    except OSError:
        pass        # read-only or locked: fixed in memory now, and again next time
    return config


#: The settings files Configure reads and saves.
SETTINGS_FILES = ('image_describer_config.json', 'video_frame_extractor_config.json',
                  'workflow_config.json')


def settings_access_report() -> list:
    """Lines saying whether this process can reach each settings file.

    For the startup log. Every check catches its own error, so the report
    names exactly which call macOS refuses and on which path -- the Configure
    dialog only ever said "Operation not permitted" (macOS 27, 11/20/2026:
    the app launched from Finder couldn't load its settings, but the same app
    launched from Terminal could).
    """
    lines = [f"cwd: {_safe(os.getcwd)}"]
    user_dir = get_user_config_dir()
    lines.append(f"user config dir {user_dir}: {_probe_stat(user_dir)}")
    lines.append(f"  listdir: {_safe(lambda: sorted(os.listdir(user_dir)))}")
    for name in SETTINGS_FILES:
        p = user_dir / name
        lines.append(f"  {name}: stat {_probe_stat(p)}; read {_probe_read(p)}")
        try:
            _config, path, source = load_json_config(name)
            lines.append(f"    load_json_config: ok, from {source} ({path})")
        except Exception as exc:                                # noqa: BLE001
            lines.append(f"    load_json_config: FAILED {exc!r} "
                         f"(path {getattr(exc, 'filename', None)!r})")
        try:
            dpath, dsource = resolve_defaults(name)
            lines.append(f"    defaults: {dsource} ({dpath})")
        except Exception as exc:                                # noqa: BLE001
            lines.append(f"    defaults: FAILED {exc!r} "
                         f"(path {getattr(exc, 'filename', None)!r})")
    return lines


def _safe(fn):
    try:
        return fn()
    except Exception as exc:                                    # noqa: BLE001
        return f"FAILED {exc!r}"


def _probe_stat(p: Path) -> str:
    try:
        st = os.stat(p)
        return f"ok (mode {oct(st.st_mode & 0o777)})"
    except Exception as exc:                                    # noqa: BLE001
        return f"FAILED {exc!r}"


def _probe_read(p: Path) -> str:
    try:
        with open(p, 'rb') as f:
            return f"ok ({len(f.read())} bytes)"
    except Exception as exc:                                    # noqa: BLE001
        return f"FAILED {exc!r}"


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
