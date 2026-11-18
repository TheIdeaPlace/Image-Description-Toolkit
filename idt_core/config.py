"""
User-level configuration stored in ~/.idt/config.json.
Project-level overrides live in the .idt/project.json beside each source directory.
API keys are never stored here — read from environment variables by providers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Prompt library — SINGLE SOURCE OF TRUTH.
#
# IDT's researched prompt set lives in scripts/image_describer_config.json
# (key "prompt_variations"). The GUI, the legacy CLI, and idt_core all read
# that one file so every surface offers the exact same named prompts. Do NOT
# hardcode a prompt list here — that is what caused the CLI and GUI to drift
# apart in v4.5. The fallback below is an emergency net only, used solely if
# the shared config cannot be loaded (missing/corrupt); it is intentionally
# tiny so a silent fallback is obvious rather than masquerading as the real set.
# ---------------------------------------------------------------------------
_FALLBACK_PROMPTS: dict[str, str] = {
    "narrative": (
        "Describe this image in a narrative style. Start with the overall scene, "
        "then describe specific objects and people from left to right. Include colors, "
        "clothing details, and spatial relationships. Use concrete, specific language."
    ),
}
_FALLBACK_DEFAULT_PROMPT = "narrative"


def _load_shared_config() -> tuple[dict[str, str], str, str]:
    """Load prompts and defaults from image_describer_config.json.

    Returns (prompts, default_prompt_name, default_ollama_model).
    Single source of truth for all surfaces: CLI, GUI, and idt_core.
    To change the default Ollama model, edit image_describer_config.json
    → "default_model". All Python code reads from there at import time.
    """
    try:
        from idt_core.config_loader import load_json_config
    except ImportError:
        try:
            from config_loader import load_json_config          # frozen mode
        except ImportError:
            return dict(_FALLBACK_PROMPTS), _FALLBACK_DEFAULT_PROMPT, "llama3.2-vision"

    config, _path, _src = load_json_config('image_describer_config.json')
    variations = dict(config.get("prompt_variations") or {}) if config else {}
    if not variations:
        return dict(_FALLBACK_PROMPTS), _FALLBACK_DEFAULT_PROMPT, "llama3.2-vision"
    default_prompt = (config.get("default_prompt_style") or "").strip()
    if default_prompt not in variations:
        default_prompt = "narrative" if "narrative" in variations else next(iter(variations))
    # Keep the tag. It used to be cut off ("moondream:1.8b" became "moondream"),
    # which names a different Ollama model or none at all: with moondream:1.8b
    # as the default, every `idt describe` failed with a 404 (NVDA bug bash,
    # 11/15/2026), and "qwen3-vl:8b-instruct" would have become the thinking
    # "qwen3-vl". Only ":latest" says nothing, so only that is dropped.
    raw_model = (config.get("default_model") or "llama3.2-vision").strip()
    default_model = raw_model[:-len(":latest")] if raw_model.endswith(":latest") else raw_model
    return variations, default_prompt, default_model


# Loaded once at import time from the shared config JSON, through config_loader:
# the user's saved settings first, then the shipped scripts/image_describer_config.json.
# Editing the shipped file changes the default for anyone who hasn't saved their own.
BUILT_IN_PROMPTS, DEFAULT_PROMPT_NAME, DEFAULT_OLLAMA_MODEL = _load_shared_config()


def _shared_default_provider() -> tuple:
    """(Configure's default provider, whether the user saved settings).

    The provider is ImageDescriber's key ("claude", "mlx"...) or "ollama"; the
    command line translates it (cli.main._cli_provider). The flag says whether
    the shared config came from the user config dir -- Configure -- rather
    than only the shipped defaults, so `idt config` can say which.
    """
    try:
        from idt_core.config_loader import get_user_config_dir, load_json_config
    except ImportError:
        try:
            from config_loader import get_user_config_dir, load_json_config  # frozen mode
        except ImportError:
            return "ollama", False
    try:
        config, path, _src = load_json_config('image_describer_config.json')
        from_configure = bool(path) and Path(path).resolve().parent == get_user_config_dir().resolve()
    except Exception:
        return "ollama", False
    provider = ((config or {}).get("default_provider") or "ollama").strip() or "ollama"
    return provider, from_configure


#: Configure's default provider. Configure's default_model is a different
#: thing: "the default Ollama model, used when the provider is Ollama"
#: (configure_dialog.py), so it is never paired with another provider.
DEFAULT_PROVIDER, DEFAULTS_FROM_CONFIGURE = _shared_default_provider()

_CONFIG_FILE = Path.home() / ".idt" / "config.json"

#: The defaults ~/.idt/config.json can override. Before 4.9 every save wrote
#: all three -- ImageDescriber's startup update check saves this file -- so
#: whatever was the default that day was frozen in, and Configure's later
#: choices never reached the command line (4.9.0 guru bug bash, S6). Now only
#: the ones a user set (`idt config --set`) are saved, listed under "user_set".
_DEFAULT_KEYS = ("default_provider", "default_model", "default_prompt_name")

#: A file from before 4.9 (no "user_set") whose three defaults ALL match
#: these was frozen in, not chosen, so it's ignored and Configure's settings
#: apply. If any one differs, the file is a user's choices and all its
#: defaults are kept together -- judging each key alone could keep a model
#: and drop the provider it went with (#455 review).
_FROZEN_OLD_DEFAULTS = {
    "default_provider": {"ollama"},
    "default_model": {"minicpm-v4.6", "moondream", "moondream:1.8b",
                      "llama3.2-vision", "gemma3", "gemma3:latest"},
    "default_prompt_name": {"narrative", "detailed"},
}


@dataclass
class UserConfig:
    # Unless set with `idt config --set`, these are Configure's (the shared
    # config in the user config dir), so the two tools agree.
    default_provider: str = DEFAULT_PROVIDER
    default_model: str = DEFAULT_OLLAMA_MODEL
    default_prompt_name: str = DEFAULT_PROMPT_NAME
    custom_prompts: dict[str, str] = field(default_factory=dict)
    workspace_root: Optional[str] = None  # None → ~/Documents/idt
    # Whether new workspaces copy the user's originals into images/ (self-contained,
    # portable) or reference them in place. Default off. See
    # docs/design/image-handling-lifecycle.md.
    copy_originals: bool = False
    # Whether `idt download` (CLI) and the ImageDescriber download dialog (GUI) save
    # a downloaded image's HTML alt text as its own description (model "Website Alt
    # Text"), in addition to any AI-generated one. Default on.
    preserve_alt_text: bool = True
    # Whether ImageDescriber checks GitHub for a newer release at startup. The
    # manual Help > Check for Updates always runs regardless. See idt_core/updater.py.
    auto_check_updates: bool = True
    # A version the user chose "Skip This Version" on; the startup check never
    # offers that exact version again. Manual checks ignore it.
    skipped_update_version: Optional[str] = None
    # ISO timestamp of the last startup check, used to throttle to once a day so
    # every launch does not hit the GitHub API.
    last_update_check: Optional[str] = None
    # Which of _DEFAULT_KEYS the user set; only those are saved.
    user_set: set = field(default_factory=set)
    # The provider a user-set default_model was set for (CLI key), so changing
    # the default provider later doesn't send it to the wrong one (#455 review).
    default_model_provider: Optional[str] = None

    def set_default(self, key: str, value: str) -> None:
        """Set one of the default provider/model/prompt as the user's choice."""
        if key not in _DEFAULT_KEYS:
            raise KeyError(key)
        setattr(self, key, value)
        self.user_set.add(key)

    def workspace_root_path(self) -> Path:
        """Resolved workspace root. Defaults to ~/Documents/idt."""
        if self.workspace_root:
            return Path(self.workspace_root).expanduser().resolve()
        return Path.home() / "Documents" / "idt"

    @classmethod
    def load(cls) -> "UserConfig":
        if not _CONFIG_FILE.exists():
            return cls()
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        obj = cls()
        for key in ("workspace_root", "skipped_update_version", "last_update_check"):
            if key in data:
                setattr(obj, key, data[key])
        marked = data.get("user_set")
        model_provider = data.get("default_model_provider")
        if marked is None:   # a file from before 4.9
            frozen = all(data.get(k) in _FROZEN_OLD_DEFAULTS[k] for k in _DEFAULT_KEYS)
            marked = [] if frozen else [k for k in _DEFAULT_KEYS if data.get(k)]
            # Old files saved the provider and model together: they go together.
            if "default_model" in marked and data.get("default_provider"):
                model_provider = data["default_provider"]
        for key in _DEFAULT_KEYS:
            if data.get(key) and key in marked:
                setattr(obj, key, data[key])
                obj.user_set.add(key)
        if "default_model" in obj.user_set and model_provider:
            obj.default_model_provider = model_provider
        obj.custom_prompts = data.get("custom_prompts", {})
        obj.copy_originals = bool(data.get("copy_originals", False))
        obj.preserve_alt_text = bool(data.get("preserve_alt_text", True))
        obj.auto_check_updates = bool(data.get("auto_check_updates", True))
        return obj

    def save(self) -> None:
        _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {key: getattr(self, key) for key in _DEFAULT_KEYS if key in self.user_set}
        data["user_set"] = sorted(k for k in self.user_set if k in _DEFAULT_KEYS)
        if "default_model" in self.user_set and self.default_model_provider:
            data["default_model_provider"] = self.default_model_provider
        data.update({
            "custom_prompts": self.custom_prompts,
            "copy_originals": self.copy_originals,
            "preserve_alt_text": self.preserve_alt_text,
            "auto_check_updates": self.auto_check_updates,
        })
        if self.workspace_root:
            data["workspace_root"] = self.workspace_root
        if self.skipped_update_version:
            data["skipped_update_version"] = self.skipped_update_version
        if self.last_update_check:
            data["last_update_check"] = self.last_update_check
        _CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_prompt_text(self, name: str) -> Optional[str]:
        """Look up a prompt by name — custom prompts override built-ins."""
        return self.custom_prompts.get(name) or BUILT_IN_PROMPTS.get(name)

    def list_prompts(self) -> dict[str, str]:
        """All available prompts: built-ins plus any user-defined ones."""
        return {**BUILT_IN_PROMPTS, **self.custom_prompts}
