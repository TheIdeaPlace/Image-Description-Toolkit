#!/usr/bin/env python3
"""
Configure Dialog for ImageDescriber

Dialog version of IDT Configure for integration into ImageDescriber.
Manages configuration files:
- image_describer_config.json
- video_frame_extractor_config.json
- workflow_config.json

Features:
- Tabbed interface for configuration categories
- Settings list with arrow navigation
- Type-specific editors (bool, int, float, choice, string)
- Screen reader readable explanations
- Save/Load functionality
- Professional, accessible interface
- Dialog buttons: OK (save & close), Cancel (discard), Apply (save & continue)
"""

import sys
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import wx
import platform

try:
    from idt_core.config import DEFAULT_OLLAMA_MODEL
except ImportError:
    DEFAULT_OLLAMA_MODEL = "minicpm-v4.6"

logger = logging.getLogger(__name__)


def readable_text(parent, text: str, name: str, width: int = 580) -> "wx.TextCtrl":
    """Explanatory text a keyboard or screen reader user can reach.

    A wx.StaticText is skipped by Tab, so a screen reader user only heard it by
    exploring the screen, and most never did. A read-only, multi-line text box
    is a Tab stop whose text can be read with the cursor. Sized to its text, so
    the layout barely changes.
    """
    # A scroll bar appears only if the text outgrows the box (large Windows text
    # sizes), so the end of the text is never hidden.
    box = wx.TextCtrl(parent, value=text,
                      style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
    name_for_screen_readers(box, name)
    per_line = max(20, (width - 16) // max(1, box.GetCharWidth()))
    lines = sum(max(1, -(-len(line) // per_line)) for line in text.split("\n"))
    box.SetMinSize((width, box.GetCharHeight() * (lines + 1) + 8))
    return box


def first_tab_stop(window):
    """The first control under ``window`` that Tab would reach, depth first."""
    for child in window.GetChildren():
        if isinstance(child, (wx.StaticText, wx.StaticBox)) or not child.IsShown():
            if isinstance(child, wx.StaticBox):
                found = first_tab_stop(child)
                if found is not None:
                    return found
            continue
        if child.IsEnabled() and child.AcceptsFocusFromKeyboard():
            return child
        found = first_tab_stop(child)
        if found is not None:
            return found
    return None


def name_for_screen_readers(box, label: str) -> None:
    """Set ``label`` as the control's name for screen readers on every platform.

    shared.wx_common.set_screen_reader_name, kept under this name for the
    callers here (one implementation, so the two can't drift apart)."""
    from shared.wx_common import set_screen_reader_name
    set_screen_reader_name(box, label)


#: Plain names for settings whose code name doesn't read well once its
#: underscores become spaces.
_SETTING_LABELS = {
    "html_report_title": "HTML report title",
    "max_image_size": "Maximum image size",
    "max_frames_per_video": "Maximum frames per video",
    "compression_enabled": "Compress images",
    "metadata_enabled": "Extract metadata",
}


def setting_label(setting_name: str) -> str:
    """What the settings list and the editor call a setting: a plain name.

    The list showed the code name, so a screen reader said "default_provider:
    ollama" (#422). Underscores become spaces and the first letter is
    capitalised; a few names that still read badly have their own label.
    """
    if setting_name in _SETTING_LABELS:
        return _SETTING_LABELS[setting_name]
    text = setting_name.replace("_", " ").strip()
    return text[:1].upper() + text[1:]


#: The prompt styles offered when the settings file has none, which only a
#: broken file does: these are the shipped prompts' names.
_FALLBACK_PROMPT_STYLES = ["detailed", "concise", "narrative", "artistic",
                           "technical", "colorful", "simple"]


def prompt_style_choices(config: Optional[Dict[str, Any]]) -> List[str]:
    """The prompt styles Configure offers: every prompt in the settings file.

    A hard-coded list of seven missed accessibility, aialttext and every prompt
    added in the Prompt Editor (#469). Same order as Processing Options.
    """
    variations = (config or {}).get("prompt_variations") if isinstance(config, dict) else None
    if isinstance(variations, dict) and variations:
        return [str(name) for name in variations]
    return list(_FALLBACK_PROMPT_STYLES)


def _choice_label(setting_info: Dict[str, Any], value: Any) -> Any:
    """What a choice setting shows for ``value``: its entry in "choice_labels", else itself."""
    return setting_info.get("choice_labels", {}).get(value, value)


#: Setting types whose empty value means "automatic": IDT's default for the
#: provider and model (issue #392). Stored by removing the key.
_AUTO_TYPES = ("float_or_auto", "int_or_auto", "choice_or_auto")
AUTOMATIC_LABEL = "Automatic"


def _display_value(setting_info: Dict[str, Any], value: Any) -> Any:
    """What the settings list shows for ``value``."""
    if setting_info.get("type") in _AUTO_TYPES and value in (None, ""):
        return setting_info.get("choice_labels", {}).get("", AUTOMATIC_LABEL)
    return _choice_label(setting_info, value)




_AUTO_NOTE = ("Leave it on Automatic to use IDT's default for the model you pick. "
              "A setting a model cannot take is skipped, and the run log says so.")

#: (provider key in the settings file, name shown, settings it takes). Only
#: what each provider can use is offered (issue #392): a toolkit, not one form
#: with every knob for every provider.
_GENERATION_PROVIDERS = (
    ("ollama", "Ollama", ("thinking", "temperature", "top_p", "top_k",
                          "repeat_penalty", "max_output_tokens")),
    ("openai", "OpenAI", ("thinking", "effort", "temperature", "top_p",
                          "max_output_tokens")),
    ("claude", "Claude", ("thinking", "effort", "max_output_tokens")),
    ("claude-code", "Claude Code", ("thinking", "effort", "max_output_tokens")),
    ("apple", "Apple Intelligence", ("temperature", "max_output_tokens")),
    ("mlx", "MLX", ("max_output_tokens",)),
)


def _generation_entry(provider: str, label: str, setting: str) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"file": "image_describer", "path": ["generation", provider, setting]}
    if setting == "thinking":
        if provider == "ollama":
            entry.update(
                type="choice_or_auto", choices=["", "off", "on", "auto"],
                choice_labels={"": "Automatic (off)", "off": "Off", "on": "On",
                               "auto": "The model's own default"},
                description=("Whether a thinking model reasons before it describes. "
                             "Automatic turns thinking off for descriptions: the "
                             "reasoning is thrown away, and on a thinking model it is "
                             "most of the time per image. Some models keep thinking "
                             "anyway (every qwen3-vl thinking tag does); for those, "
                             "choose the model's '-instruct' tag instead."))
        elif provider == "claude-code":
            entry.update(
                type="choice_or_auto", choices=["", "off"],
                choice_labels={"": AUTOMATIC_LABEL, "off": "Off (low effort)"},
                description=("Claude decides when to think. Off asks for low effort, "
                             "the closest it allows. For more thinking, raise the effort."))
        else:
            entry.update(
                type="choice_or_auto", choices=["", "off", "on"],
                choice_labels={"": AUTOMATIC_LABEL, "off": "Off (least effort)", "on": "On"},
                description=(f"Whether {label} reasons before it describes. Its current "
                             "models cannot switch reasoning off entirely, so Off asks "
                             "for the least effort the model takes instead."))
    elif setting == "effort":
        levels = ["", "minimal", "low", "medium", "high"] if provider == "openai" \
            else ["", "low", "medium", "high"]
        entry.update(
            type="choice_or_auto", choices=levels,
            choice_labels={"": AUTOMATIC_LABEL},
            description=(f"How hard {label} reasons before answering. Lower is faster "
                         "and cheaper; descriptions rarely need high. Overrides Thinking."
                         + (" Minimal means the least the model takes: low on the "
                            "o-series, GPT-6 Astra, GPT-6.1 Sol, GPT-6.2 Sol and GPT-6.2 "
                            "Astra; minimal on the original GPT-5 models; none on the "
                            "others." if provider == "openai" else "")))
    elif setting == "temperature":
        entry.update(
            type="float_or_auto", range=[0.0, 2.0],
            description=("How varied the wording is: lower is more consistent, higher "
                         "more varied. Automatic uses the model's own setting."
                         + (" OpenAI's reasoning models accept only their own, so it is "
                            "skipped for them." if provider == "openai" else "")))
    elif setting == "top_p":
        entry.update(type="float_or_auto", range=[0.0, 1.0],
                     description="Nucleus sampling cutoff. Lower is more focused.")
    elif setting == "top_k":
        entry.update(type="int_or_auto", range=[1, 500],
                     description="How many candidate words are considered at each step. "
                                 "Lower is more focused.")
    elif setting == "repeat_penalty":
        entry.update(type="float_or_auto", range=[0.0, 2.0],
                     description="How strongly repeated words are discouraged. 1 is none.")
    elif setting == "max_output_tokens":
        entry.update(
            type="int_or_auto", range=[50, 32000],
            description=("The most a description may be, in tokens (about three quarters "
                         "of a word each). Too low cuts descriptions off; the run log "
                         "says when that happens."
                         + (" Thinking counts against it." if provider in
                            ("openai", "claude", "claude-code") else "")))
    entry["description"] = f"{entry['description']} {_AUTO_NOTE}"
    return entry


_SETTING_NAMES = {
    "thinking": "thinking", "effort": "effort", "temperature": "temperature",
    # Spaces, not underscores: a screen reader says "top underscore p".
    "top_p": "top p", "top_k": "top k", "repeat_penalty": "repeat penalty",
    "max_output_tokens": "output limit",
}


#: Providers that only run on a Mac. Listing their settings elsewhere only adds
#: entries a screen reader user has to pass that can never apply.
_MAC_ONLY_PROVIDERS = ("apple", "mlx")


def generation_settings_metadata(include_mac: Optional[bool] = None) -> Dict[str, Dict[str, Any]]:
    """The Generation tab: "<provider> <setting>" for each setting it takes.

    ``include_mac`` defaults to whether this is a Mac.
    """
    if include_mac is None:
        include_mac = sys.platform == "darwin"
    settings: Dict[str, Dict[str, Any]] = {}
    for provider, label, names in _GENERATION_PROVIDERS:
        if provider in _MAC_ONLY_PROVIDERS and not include_mac:
            continue
        for setting in names:
            settings[f"{label} {_SETTING_NAMES[setting]}"] = _generation_entry(
                provider, label, setting)
    return settings


def normalise_generation_section(config: Optional[Dict[str, Any]]) -> None:
    """Rewrite each provider's generation settings in their canonical form.

    The settings file is hand-editable and idt_core reads it leniently:
    ``"thinking": false``, ``"OFF"``, ``num_predict`` and ``max_tokens`` all
    work. The dialog knows only canonical keys and values, so without this a
    hand-edited value showed wrongly and was dropped on OK (issue #392
    review). Unknown keys are kept, under "extra", which idt_core also reads.
    """
    try:
        from idt_core.generation import CONFIG_KEY, GenerationOptions
    except ImportError:                                             # pragma: no cover
        return
    if not isinstance(config, dict):
        return
    section = config.get(CONFIG_KEY)
    if not isinstance(section, dict):
        return
    for provider, settings in list(section.items()):
        if isinstance(settings, dict):
            canonical = GenerationOptions.from_dict(settings).to_dict()
            if canonical:
                section[provider] = canonical
            else:
                del section[provider]
    if not section:
        del config[CONFIG_KEY]


def default_provider_choices(system: Optional[str] = None):
    """``(choices, description)`` for the default provider, for this platform.

    Apple Intelligence runs only on a Mac and Windows AI only on Windows, so each
    is offered only there: both were listed everywhere, and choosing the other
    platform's one just failed later.
    """
    system = system or platform.system()
    choices = ["ollama", "openai", "claude", "claude-code"]
    description = ("Default AI provider to use when processing images. Ollama runs locally, "
                   "OpenAI and Claude require API keys, and claude-code uses your Claude "
                   "subscription through the Claude Code app (sign in with 'claude auth login').")
    if system == "Darwin":
        choices.append("apple")
        description += (" apple runs Apple Intelligence on this Mac (macOS 27; accept the terms "
                        "once with 'sudo fm license').")
    elif system == "Windows":
        choices.append("windows-ai")
        description += (" Windows-AI runs Windows' own model on a Copilot+ PC (it takes no "
                        "prompt; its models are kinds of description).")
    return choices, description


def _remove_path(config: Dict[str, Any], path: List[str]) -> None:
    """Delete ``path`` from nested dicts, then any parents it leaves empty."""
    parents = []
    node = config
    for key in path[:-1]:
        if not isinstance(node, dict) or key not in node:
            return
        parents.append((node, key))
        node = node[key]
    if isinstance(node, dict):
        node.pop(path[-1], None)
    for parent, key in reversed(parents):
        if isinstance(parent.get(key), dict) and not parent[key]:
            del parent[key]
        else:
            break


def _choice_value(setting_info: Dict[str, Any], label: str) -> str:
    """The value a shown choice stands for: the reverse of :func:`_choice_label`."""
    for value, shown in setting_info.get("choice_labels", {}).items():
        if shown == label:
            return value
    return label


class ApiKeyEditDialog(wx.Dialog):
    """Dialog for adding or replacing one provider's API key.

    Opened from a provider row on the API Keys tab, it is for that provider
    only: the title and the key box name it, and there is no provider list
    to pick from again (Kelly, 11/2026 -- arrowing to Claude and choosing Add
    Key, then having to choose Claude a second time, was a step too many).
    The provider list appears only when no provider is given.
    """

    #: (display label, canonical name used by idt_core.keys)
    PROVIDER_CHOICES = [
        ("OpenAI", "openai"),
        ("Claude (Anthropic)", "claude"),
        ("Ollama Web Search", "ollama.com"),
    ]

    @classmethod
    def label_for(cls, provider: str) -> str:
        """The display label for a canonical name; an unrecognised name as is."""
        for label, canonical in cls.PROVIDER_CHOICES:
            if canonical == (provider or "").lower():
                return label
        return provider

    def __init__(self, parent, provider="", api_key="", replacing=False):
        self.provider = provider
        self.api_key = api_key
        self.replacing = replacing
        if provider:
            verb = "Replace" if replacing else "Add"
            title = f"{verb} {self.label_for(provider)} API Key"
        else:
            title = "Add API Key"
        super().__init__(parent, title=title, size=(500, 250))

        self.setup_ui()

    def setup_ui(self):
        """Create the dialog UI"""
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Form grid
        form_sizer = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
        form_sizer.AddGrowableCol(1, 1)

        # Provider selection: only when the caller didn't say which.
        self.provider_choice = None
        if not self.provider:
            form_sizer.Add(wx.StaticText(panel, label="Provider:"), 0, wx.ALIGN_CENTER_VERTICAL)
            labels = [label for label, _canonical in self.PROVIDER_CHOICES]
            self.provider_choice = wx.Choice(panel, choices=labels, name="Provider")
            self.provider_choice.SetSelection(0)
            form_sizer.Add(self.provider_choice, 1, wx.EXPAND)
            key_label = "API key"
        else:
            key_label = f"{self.label_for(self.provider)} API key"

        # API Key text input, named for the provider so focus landing on it
        # says whose key it is.
        form_sizer.Add(wx.StaticText(panel, label=f"{key_label}:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.key_text = wx.TextCtrl(panel, value=self.api_key, style=wx.TE_PASSWORD,
                                    name=key_label)
        form_sizer.Add(self.key_text, 1, wx.EXPAND)

        sizer.Add(form_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Help text
        from idt_core.keys import credential_store_name
        store = credential_store_name()
        if store:
            note = (f"Keys are saved to {store} and shared by ImageDescriber, "
                    f"IDT Chat, and the idt command line.")
        else:
            note = "Note: API keys are stored in the config file. Keep your config file secure."
        sizer.Add(readable_text(panel, note, "Where keys are saved", width=450), 0, wx.ALL, 10)
        
        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK)
        cancel_btn = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        panel.SetSizer(sizer)
        
        # Bind OK to validation
        ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        # Enter in the key box presses OK: paste, Enter, done (#478). It did
        # nothing, because no button was the default.
        ok_btn.SetDefault()
        self.ok_btn = ok_btn

        # Focus where the typing goes: the key box when the provider is known,
        # the provider list otherwise.
        self.first_focus = self.provider_choice or self.key_text
        wx.CallAfter(self._focus_first)

    def _focus_first(self):
        if self and not self.IsBeingDeleted():
            self.first_focus.SetFocus()

    def on_ok(self, event):
        """Validate input before accepting"""
        provider, api_key = self.get_values()

        if not provider:
            show_warning(self, "Please select a provider.")
            return

        if not api_key:
            show_warning(self, "Please enter an API key.")
            self.key_text.SetFocus()
            return

        self.EndModal(wx.ID_OK)

    def get_values(self):
        """Get the entered (provider name, API key): the canonical name from
        the list, or the provider this dialog was opened for, as given."""
        if self.provider_choice is None:
            canonical = self.provider
        else:
            index = self.provider_choice.GetSelection()
            canonical = (self.PROVIDER_CHOICES[index][1]
                         if index != wx.NOT_FOUND else "")
        return canonical, self.key_text.GetValue().strip()

# Ensure project root is on sys.path so sibling modules (shared/) import in dev and frozen modes
# Works in both development mode (running script) and frozen mode (PyInstaller exe)
if getattr(sys, 'frozen', False):
    # Frozen mode - executable directory is base
    _project_root = Path(sys.executable).parent
else:
    # Development mode - use __file__ relative path
    _project_root = Path(__file__).parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Import shared utilities
try:
    from shared.wx_common import (
        find_config_file,
        ConfigManager,
        show_error,
        show_warning,
        show_info,
        open_file_dialog,
        save_file_dialog,
        show_about_dialog,
        get_app_version,
    )
except ImportError as e:
    print(f"ERROR: Cannot import shared.wx_common: {e}")
    print("This indicates a PyInstaller build issue or missing dependency.")
    sys.exit(1)

# The number check is shared with the video extraction and Download dialogs
# (#406); it lives in shared/number_entry.py. These names stay importable here.
# Below the sys.path set-up above, like the wx_common import.
from shared.number_entry import (NUMBER_TYPES, validate_number,  # noqa: E402
                                 spoken_range, VIDEO_INTERVAL_RANGE,
                                 SCENE_THRESHOLD_RANGE)
from idt_core.providers.registry import typed_name as typed_provider_name  # noqa: E402
from idt_core.providers.registry import display_name as provider_display_name  # noqa: E402


class SettingEditDialog(wx.Dialog):
    """Dialog for editing a single setting value"""
    
    def __init__(self, parent, setting_name: str, current_value: Any, setting_info: Dict[str, Any]):
        super().__init__(parent, title=f"Edit: {setting_label(setting_name)}", size=(450, 250))
        
        logger.info("SettingEditDialog.__init__ started for: %s", setting_name)
        
        self.setting_name = setting_name
        self.current_value = current_value
        self.setting_info = setting_info
        self.new_value = None
        self.editor = None
        self._focus_set = False
        
        try:
            self.setup_ui()
        except Exception as e:
            logger.error("Failed in setup_ui: %s", e, exc_info=True)
            raise
        
        # Bind to show event for reliable focus setting
        logger.info("SettingEditDialog: Binding EVT_SHOW")
        self.Bind(wx.EVT_SHOW, self._on_show)
        
        logger.info("SettingEditDialog.__init__ completed")
    
    def setup_ui(self):
        """Create the dialog UI"""
        try:
            logger.info("setup_ui: Creating panel")
            panel = wx.Panel(self)
            panel_sizer = wx.BoxSizer(wx.VERTICAL)
            
            # Add description
            logger.info("setup_ui: Adding description")
            if "description" in self.setting_info:
                desc_text = wx.StaticText(panel, label=self.setting_info["description"])
                desc_text.Wrap(400)
                panel_sizer.Add(desc_text, 0, wx.ALL, 10)
            
            # Create appropriate editor based on setting type
            setting_type = self.setting_info.get("type", "string")
            logger.info("setup_ui: Setting type is %s", setting_type)
            
            form_sizer = wx.FlexGridSizer(rows=2, cols=2, vgap=5, hgap=5)
            form_sizer.AddGrowableCol(1, 1)
            
            form_sizer.Add(wx.StaticText(panel, label="Value:"), 0, wx.ALIGN_CENTER_VERTICAL)
            
            if setting_type == "bool":
                self.editor = wx.CheckBox(panel)
                self.editor.SetValue(bool(self.current_value))
                form_sizer.Add(self.editor, 0, wx.EXPAND)
                
            elif setting_type == "int":
                # A text box, not a SpinCtrl: a spin box rewrites a typed 150 to
                # its maximum as soon as it loses focus (Tab to OK), so the value
                # was changed without a word. Checked on OK like every number.
                self.editor = wx.TextCtrl(panel)
                self.editor.SetValue("" if self.current_value is None else str(self.current_value))
                form_sizer.Add(self.editor, 0, wx.EXPAND)
                
            elif setting_type == "float":
                self.editor = wx.TextCtrl(panel)
                self.editor.SetValue(str(float(self.current_value or 0.0)))
                form_sizer.Add(self.editor, 0, wx.EXPAND)
                
            elif setting_type == "int_or_null":
                self.editor = wx.TextCtrl(panel)
                # Display empty string for None/null, otherwise the integer value
                if self.current_value is None:
                    self.editor.SetValue("")
                else:
                    self.editor.SetValue(str(int(self.current_value)))
                form_sizer.Add(self.editor, 0, wx.EXPAND)
                
            elif setting_type in ("float_or_auto", "int_or_auto"):
                # Empty means Automatic; checked on OK (see _on_ok).
                self.editor = wx.TextCtrl(panel)
                self.editor.SetValue("" if self.current_value is None else str(self.current_value))
                self.editor.SetHint(AUTOMATIC_LABEL)
                form_sizer.Add(self.editor, 0, wx.EXPAND)

            elif setting_type == "choice_or_auto":
                self.editor = wx.Choice(panel)
                choices = self.setting_info.get("choices", [])
                self.editor.Append([str(_display_value(self.setting_info, c)) for c in choices])
                current = "" if self.current_value is None else self.current_value
                if current in choices:
                    self.editor.SetSelection(choices.index(current))
                else:
                    # A value from a hand-edited file that this list does not
                    # offer: kept and selected, as the plain choice type does,
                    # so pressing OK does not silently change it.
                    self.editor.Append(f"{current} (current)")
                    self.editor.SetSelection(len(choices))
                form_sizer.Add(self.editor, 0, wx.EXPAND)

            elif setting_type == "choice":
                self.editor = wx.Choice(panel)
                choices = self.setting_info.get("choices", [])
                self.editor.Append([_choice_label(self.setting_info, c) for c in choices])
                
                # Handle current value - if it's not in the list, add it as first option
                if self.current_value:
                    if self.current_value in choices:
                        self.editor.SetStringSelection(str(_choice_label(self.setting_info, self.current_value)))
                    else:
                        # Add current value as first choice (user may have custom model)
                        self.editor.Insert(f"{self.current_value} (current)", 0)
                        self.editor.SetSelection(0)
                elif choices:
                    # No current value, select first choice
                    self.editor.SetSelection(0)
                    
                form_sizer.Add(self.editor, 0, wx.EXPAND)
                
            else:  # string or other
                self.editor = wx.TextCtrl(panel)
                self.editor.SetValue(str(self.current_value or ""))
                form_sizer.Add(self.editor, 0, wx.EXPAND)
            
            logger.info("setup_ui: Editor widget created: %s", type(self.editor).__name__)

            # Whichever branch built it, the editor is the only control here
            # and the setting's name is the only label it can be given: the
            # visible "Value:" static text says nothing about *which* value,
            # and on macOS nothing connects it to the field anyway.
            # A number's range goes in the name too: the "Range:" line below is
            # static text that JAWS and NVDA don't read when the field gets focus.
            # Spaces, not underscores: JAWS and NVDA read "_" as "underline".
            # Through an accessible object, not SetName alone: on Windows an edit
            # box takes its name from the "Value:" label before it, and the
            # installed-build check heard just "Value:".
            name_for_screen_readers(
                self.editor, f"{self._spoken_name()} value{spoken_range(self.setting_info)}")
            
            # Add range/limits info if available
            if "range" in self.setting_info:
                form_sizer.Add(wx.StaticText(panel, label=""), 0)
                range_label = wx.StaticText(panel, label=f"Range: {self.setting_info['range'][0]} to {self.setting_info['range'][1]}")
                form_sizer.Add(range_label, 0)
            
            logger.info("setup_ui: Adding form sizer to panel sizer")
            panel_sizer.Add(form_sizer, 0, wx.EXPAND | wx.ALL, 10)
            panel.SetSizer(panel_sizer)
            
            logger.info("setup_ui: Creating button sizer (as dialog children)")
            # Buttons - CreateButtonSizer creates buttons as children of the DIALOG, not panel
            btn_sizer = self.CreateButtonSizer(wx.OK | wx.CANCEL)
            self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
            logger.info("setup_ui: Button sizer created")
            
            # Dialog-level sizer (manages panel + buttons)
            logger.info("setup_ui: Creating dialog-level sizer")
            dialog_sizer = wx.BoxSizer(wx.VERTICAL)
            dialog_sizer.Add(panel, 1, wx.EXPAND)
            dialog_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
            
            logger.info("setup_ui: Setting dialog sizer and fitting")
            self.SetSizer(dialog_sizer)
            self.Fit()
            
            logger.info("SettingEditDialog.setup_ui completed, editor type: %s", type(self.editor).__name__)
        except Exception as e:
            logger.error("Exception in setup_ui: %s", e, exc_info=True)
            raise
    
    def _on_ok(self, event):
        """Refuse a value that cannot be used, saying why, and keep the dialog open.

        A message box rather than help text: JAWS does not read help text on
        focus, and a value silently replaced by a default is worse than none.
        """
        if self.setting_info.get("type") in NUMBER_TYPES:
            _value, error = validate_number(self.setting_info, self.editor.GetValue())
            if error:
                wx.MessageBox(error, self._spoken_name(), wx.OK | wx.ICON_WARNING, self)
                self.editor.SetFocus()
                self.editor.SelectAll()
                return
        event.Skip()

    def _on_show(self, event):
        """Handle dialog show event - set focus when dialog becomes visible"""
        event.Skip()  # Allow normal processing
        
        if not self._focus_set and self.editor:
            logger.info("SettingEditDialog shown, setting focus to editor")
            # Use CallAfter to ensure the dialog is fully rendered
            wx.CallAfter(self._set_editor_focus)
    
    def _set_editor_focus(self):
        """Set focus to the editor control"""
        if self.editor and not self._focus_set:
            try:
                self.editor.SetFocus()
                self._focus_set = True
                logger.info("Focus set to editor successfully")
            except Exception as e:
                logger.error("Failed to set focus to editor: %s", e)
    
    def _spoken_name(self) -> str:
        """The setting's name as a screen reader should say it."""
        return setting_label(self.setting_name)

    def GetValue(self):
        """Get the new value from the editor"""
        setting_type = self.setting_info.get("type", "string")

        if setting_type == "bool":
            return self.editor.GetValue()
        elif setting_type in NUMBER_TYPES:
            # _on_ok has refused anything invalid, so this is the checked value.
            value, error = validate_number(self.setting_info, self.editor.GetValue())
            if error is not None:
                return self.current_value      # never save a substitute
            return value
        elif setting_type == "choice_or_auto":
            choices = self.setting_info.get("choices", [])
            index = self.editor.GetSelection()
            if index == len(choices):            # the "(current)" entry
                return self.current_value
            value = choices[index] if 0 <= index < len(choices) else ""
            return value or None
        elif setting_type == "choice":
            value = self.editor.GetStringSelection()
            # Strip " (current)" suffix if present (added for custom values)
            if value.endswith(" (current)"):
                value = value[:-10]  # Remove " (current)"
            return _choice_value(self.setting_info, value)
        else:
            return self.editor.GetValue()


class ConfigureDialog(wx.Dialog):
    """Dialog for managing IDT configuration settings"""
    
    def __init__(self, parent, cached_ollama_models=None):
        # One short title, with no header repeating it inside: a screen reader
        # said "IDT Configure - Configuration Manager dialog IDT Configuration
        # Manager" on opening (#422).
        super().__init__(parent, title="Configure", size=(900, 650))

        logger.info("Configure dialog opened")
        
        # Cache of Ollama models for choice list population
        self.cached_ollama_models = cached_ollama_models
        
        # Find config files
        self.scripts_dir = self.find_scripts_directory()
        
        # Configuration file paths
        self.config_files = {
            "image_describer": self.scripts_dir / "image_describer_config.json",
            "video_extractor": self.scripts_dir / "video_frame_extractor_config.json",
            "workflow": self.scripts_dir / "workflow_config.json"
        }
        
        # Current configuration data
        self.configs = {}

        # Load all configs first: the prompt style list is the file's prompts.
        self.load_all_configs()

        # Settings metadata for each category
        self.settings_metadata = self.build_settings_metadata()

        # Category tab widgets (for refreshing on changes)
        self.category_widgets = {}

        # UI setup
        self.init_ui()

        logger.info("Configure dialog UI initialized")
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_dialog_close)
    
    def _get_ollama_models(self) -> List[str]:
        """Get list of available Ollama models for choice list (sorted alphabetically)"""
        # Use cached models if provided
        if self.cached_ollama_models is not None and len(self.cached_ollama_models) > 0:
            return sorted(self.cached_ollama_models)
        
        # Try to detect models if no cache provided
        try:
            from ai_providers import get_available_providers
            providers = get_available_providers()
            if 'ollama' in providers:
                ollama_provider = providers['ollama']
                models = ollama_provider.get_available_models()
                if models:
                    return sorted(models)
        except Exception as e:
            logger.warning(f"Could not detect Ollama models: {e}")
        
        # Fallback to common models if detection fails
        return [DEFAULT_OLLAMA_MODEL, "llava", "llama3.2-vision", "moondream"]
    
    def find_scripts_directory(self) -> Path:
        """The folder Configure reads and saves: the user config dir, always.

        config_loader reads this folder before the shipped defaults, so what is
        saved here is what processing, the Prompt Editor and the CLI use.

        macOS  : ~/Library/Application Support/IDT/
        Windows: %APPDATA%/IDT/
        Linux  : ~/.config/IDT/

        It used to be this folder only in a built copy, and the repo's scripts/
        folder when run from source, while config_loader read the exe's
        scripts folder (and on an installed copy, IDT_CONFIG_DIR) first. So on
        an installed copy nothing saved here reached processing (NVDA bug bash,
        11/15/2026). A file not saved yet is seeded from the same shipped
        defaults config_loader would read.
        """
        import shutil
        from idt_core.config_loader import get_user_config_dir, resolve_defaults

        user_dir = get_user_config_dir()
        user_dir.mkdir(parents=True, exist_ok=True)
        for name in ("image_describer_config.json", "video_frame_extractor_config.json",
                     "workflow_config.json"):
            dest = user_dir / name
            if dest.exists():
                continue
            defaults, _source = resolve_defaults(name)
            if defaults.is_file():
                try:
                    shutil.copy2(defaults, dest)
                except OSError as e:
                    logger.warning("Could not copy default %s to %s: %s", defaults, dest, e)
        return user_dir
    
    def build_settings_metadata(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Build metadata for all settings organized by category"""
        # Get available Ollama models for default_model choice list
        ollama_models = self._get_ollama_models()
        provider_choices, provider_description = default_provider_choices()

        return {
            "AI Model Settings": {
                "default_provider": {
                    "file": "image_describer",
                    "path": ["default_provider"],
                    "type": "choice",
                    "choices": provider_choices,
                    # Plain names ("Default provider: Ollama", #422); Windows-AI
                    # as typed: a screen reader says a lowercase "ai" as a word.
                    "choice_labels": {
                        p: (typed_provider_name(p) if p == "windows-ai" else provider_display_name(p))
                        for p in provider_choices},
                    "description": provider_description
                },
                "default_model": {
                    "file": "image_describer",
                    "path": ["default_model"],
                    "type": "choice",
                    "choices": ollama_models,
                    "description": "Default Ollama model to use for image descriptions. Select from detected models or refresh models from Process menu. This is used when the default provider is Ollama."
                },
            },
            # The old temperature/max_tokens/top_k/top_p/repeat_penalty entries
            # here edited model_settings, which nothing has read since June
            # 2026 (issue #392). These replace them, per provider.
            "Generation": generation_settings_metadata(),
            "Prompt Styles": {
                "default_prompt_style": {
                    "file": "image_describer",
                    "path": ["default_prompt_style"],
                    "type": "choice",
                    # Every prompt in the settings file, by its real name (#469;
                    # "Simple" capitalised matched none, guru bug bash S5).
                    "choices": prompt_style_choices(
                        getattr(self, "configs", {}).get("image_describer")),
                    "description": "Default prompt style for image descriptions. 'narrative' provides objective, detailed descriptions. 'artistic' focuses on composition and mood. 'technical' analyzes photographic aspects."
                }
            },
            "Video Extraction": {
                "extraction_mode": {
                    "file": "video_extractor",
                    "path": ["extraction_mode"],
                    "type": "choice",
                    "choices": ["time_interval", "scene_change"],
                    "description": "How to extract frames from videos. 'time_interval' extracts at regular intervals. 'scene_change' detects scene changes and extracts key frames."
                },
                "time_interval_seconds": {
                    "file": "video_extractor",
                    "path": ["time_interval_seconds"],
                    "type": "float",
                    "range": list(VIDEO_INTERVAL_RANGE),
                    "description": "Seconds between frame extractions when using time_interval mode. Lower = more frames. Recommended: 3-5 seconds for most videos."
                },
                "max_frames_per_video": {
                    "file": "video_extractor",
                    "path": ["max_frames_per_video"],
                    "type": "int_or_null",
                    "range": [1, 1000],
                    "description": "Maximum frames to extract per video (leave empty for unlimited). Recommended: Leave empty for automatic workflows, or set to 30-50 for manual control."
                },
                "scene_change_threshold": {
                    "file": "video_extractor",
                    "path": ["scene_change_threshold"],
                    "type": "float",
                    "range": list(SCENE_THRESHOLD_RANGE),
                    "description": "Sensitivity for scene change detection (higher = less sensitive). Recommended: 30 for most videos."
                },
                "image_quality": {
                    "file": "video_extractor",
                    "path": ["image_quality"],
                    "type": "int",
                    "range": [50, 100],
                    "description": "JPEG quality for extracted frames (50-100). Higher = better quality but larger files. Recommended: 85-95."
                },
                "preserve_directory_structure": {
                    "file": "video_extractor",
                    "path": ["preserve_directory_structure"],
                    "type": "bool",
                    "description": "Preserve the directory structure when extracting frames. If true, maintains folder hierarchy from source videos."
                }
            },
            "Processing Options": {
                "max_image_size": {
                    "file": "image_describer",
                    "path": ["processing_options", "default_max_image_size"],
                    "type": "int",
                    "range": [512, 2048],
                    "description": "Maximum image dimension (width or height) in pixels. Larger images use more memory. Recommended: 1024."
                },
                "batch_delay": {
                    "file": "image_describer",
                    "path": ["processing_options", "default_batch_delay"],
                    "type": "float",
                    "range": [0.0, 10.0],
                    "description": "Delay in seconds between processing images. Helps prevent memory buildup. Recommended: 1-3 seconds."
                },
                "compression_enabled": {
                    "file": "image_describer",
                    "path": ["processing_options", "default_compression"],
                    "type": "bool",
                    "description": "Compress images before processing to reduce memory usage. Recommended: enabled for large images."
                },
                "extract_metadata": {
                    "file": "image_describer",
                    "path": ["processing_options", "extract_metadata"],
                    "type": "bool",
                    "description": "Extract EXIF metadata from images and include in output. Provides camera settings, GPS, timestamps, etc."
                },
                "chronological_sorting": {
                    "file": "image_describer",
                    "path": ["processing_options", "chronological_sorting", "enabled_by_default"],
                    "type": "bool",
                    "description": "Automatically sort images by file modification time before processing. Ensures chronological order for photo collections."
                }
            },
            "Metadata Settings": {
                "metadata_enabled": {
                    "file": "image_describer",
                    "path": ["metadata", "enabled"],
                    "type": "bool",
                    "description": "Enable metadata extraction from images (GPS coordinates, dates, camera info). Adds location/date prefix to descriptions."
                },
                "include_location_prefix": {
                    "file": "image_describer",
                    "path": ["metadata", "include_location_prefix"],
                    "type": "bool",
                    "description": "Include location and date as prefix in descriptions (e.g., 'Austin, TX Mar 25, 2025: ...'). Requires Extract metadata."
                },
                "geocoding_enabled": {
                    "file": "image_describer",
                    "path": ["metadata", "geocoding", "enabled"],
                    "type": "bool",
                    "description": "Enable reverse geocoding to convert GPS coordinates to city/state/country. Requires internet access and adds API delay. Results are cached."
                },
                "geocoding_user_agent": {
                    "file": "image_describer",
                    "path": ["metadata", "geocoding", "user_agent"],
                    "type": "string",
                    "description": "User agent string for geocoding API requests. Must follow OpenStreetMap Nominatim usage policy."
                },
                "geocoding_delay": {
                    "file": "image_describer",
                    "path": ["metadata", "geocoding", "delay_seconds"],
                    "type": "float",
                    "range": [1.0, 5.0],
                    "description": "Delay in seconds between geocoding API requests. Minimum 1.0 second required by Nominatim usage policy."
                },
                "geocoding_cache_file": {
                    "file": "image_describer",
                    "path": ["metadata", "geocoding", "cache_file"],
                    "type": "string",
                    "description": "Path to geocoding cache file. Stores geocoded locations to minimize API calls."
                }
            },
            "Workflow Settings": {
                "base_output_directory": {
                    "file": "workflow",
                    "path": ["workflow", "base_output_dir"],
                    "type": "string",
                    "description": "Base directory for workflow output. Relative paths are relative to current directory."
                },
                "preserve_structure": {
                    "file": "workflow",
                    "path": ["workflow", "preserve_structure"],
                    "type": "bool",
                    "description": "Preserve input directory structure in output. Maintains folder organization from source."
                },
                "cleanup_intermediate": {
                    "file": "workflow",
                    "path": ["workflow", "cleanup_intermediate"],
                    "type": "bool",
                    "description": "Delete intermediate files after workflow completes. Saves disk space but removes debugging information."
                },
                "enable_video_extraction": {
                    "file": "workflow",
                    "path": ["workflow", "steps", "video_extraction", "enabled"],
                    "type": "bool",
                    "description": "Enable video frame extraction step in workflow."
                },
                "enable_image_conversion": {
                    "file": "workflow",
                    "path": ["workflow", "steps", "image_conversion", "enabled"],
                    "type": "bool",
                    "description": "Enable HEIC/HEIF to JPEG conversion step in workflow."
                },
                "enable_image_description": {
                    "file": "workflow",
                    "path": ["workflow", "steps", "image_description", "enabled"],
                    "type": "bool",
                    "description": "Enable AI image description step in workflow."
                },
                "enable_html_generation": {
                    "file": "workflow",
                    "path": ["workflow", "steps", "html_generation", "enabled"],
                    "type": "bool",
                    "description": "Enable HTML report generation step in workflow."
                },
                "conversion_quality": {
                    "file": "workflow",
                    "path": ["workflow", "steps", "image_conversion", "quality"],
                    "type": "int",
                    "range": [50, 100],
                    "description": "JPEG quality for HEIC/HEIF conversion (50-100). Higher = better quality but larger files."
                },
                "html_report_title": {
                    "file": "workflow",
                    "path": ["workflow", "steps", "html_generation", "title"],
                    "type": "string",
                    "description": "Title for generated HTML reports."
                }
            },
            "Output Format": {
                "include_timestamp": {
                    "file": "image_describer",
                    "path": ["output_format", "include_timestamp"],
                    "type": "bool",
                    "description": "Include processing timestamp in output files."
                },
                "include_model_info": {
                    "file": "image_describer",
                    "path": ["output_format", "include_model_info"],
                    "type": "bool",
                    "description": "Include AI model name and settings in output files."
                },
                "include_file_path": {
                    "file": "image_describer",
                    "path": ["output_format", "include_file_path"],
                    "type": "bool",
                    "description": "Include full file path in descriptions output."
                },
                "include_metadata": {
                    "file": "image_describer",
                    "path": ["output_format", "include_metadata"],
                    "type": "bool",
                    "description": "Include extracted EXIF metadata in descriptions output."
                }
            }
        }
    
    def init_ui(self):
        """Create the main user interface with tabbed categories"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # No header text: it repeated the title, and a screen reader read both (#422).

        # Create notebook with tabs for each category
        self.notebook = wx.Notebook(panel, style=wx.NB_TOP, name="Configuration categories")

        # Bind keyboard events for tab-accessible navigation.
        # EVT_CHAR_HOOK fires for all descendant controls, so on_notebook_char
        # guards against that by checking which window actually has focus.
        self.notebook.Bind(wx.EVT_CHAR_HOOK, self.on_notebook_char)
        
        # Create a tab for each category
        for category in self.settings_metadata.keys():
            tab_panel = self.create_category_tab(self.notebook, category)
            self.notebook.AddPage(tab_panel, category)
        
        # Add special API Keys tab
        api_keys_tab = self.create_api_keys_tab(self.notebook)
        self.notebook.AddPage(api_keys_tab, "API Keys")

        # Add Workspace tab — GUI front end for the same workspace_root the CLI
        # sets via `idt config --set workspace_root=...`
        workspace_tab = self.create_workspace_tab(self.notebook)
        self.notebook.AddPage(workspace_tab, "Workspace")

        # Add MLX Models tab (macOS only — hidden on other platforms)
        if platform.system() == "Darwin":
            mlx_tab = self.create_mlx_models_tab(self.notebook)
            self.notebook.AddPage(mlx_tab, "MLX Models")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        
        # Dialog buttons
        btn_sizer = self.create_dialog_buttons(panel)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        
        # Set focus to first tab's settings list for keyboard accessibility
        # Delay to ensure dialog is fully displayed
        wx.CallAfter(self._set_initial_focus)
    
    def on_notebook_char(self, event):
        """Handle keyboard navigation for notebook tabs.

        EVT_CHAR_HOOK fires for all descendant windows, so we only intercept
        when focus is ON the notebook tab bar itself — never when a child
        control (ListBox, TextCtrl, Button, …) has focus.  This prevents the
        Right-arrow from switching tabs while the user is navigating a
        settings list or reading the explanation panel.

        When notebook has focus, allow:
        - Left/Right arrows to switch tabs (macOS only; Windows' own control does it)
        - Cmd+Shift+[ and Cmd+Shift+] to switch tabs (macOS standard)
        - Enter/Space to move focus to content of current tab
        """
        focused = wx.Window.FindFocus()

        # Enter on a settings list opens Change Setting. The list's own key
        # handler never sees Enter on Windows: the dialog's keyboard handling
        # takes it for the default button first. This hook runs before that.
        # (Installed-build settings check, 11/16/2026: Enter did nothing,
        # only Space worked, though the user guide says Enter.)
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            for category, widgets in self.category_widgets.items():
                if widgets.get("settings_list") is focused:
                    self.change_setting(category, event)
                    return

        # Guard: only intercept when the notebook tab bar itself is focused
        if focused is not self.notebook:
            event.Skip()
            return

        keycode = event.GetKeyCode()
        current_page = self.notebook.GetSelection()
        page_count = self.notebook.GetPageCount()

        on_mac = platform.system() == "Darwin"
        if keycode in (wx.WXK_LEFT, wx.WXK_RIGHT) and not on_mac:
            # Windows' tab control moves between tabs on Left and Right itself, and
            # announces it. Moving here as well, then passing the key on, moved two
            # tabs per press, so arrowing round visited only every other tab (five
            # of ten), which a screen reader user heard as a tab bar with some tabs
            # missing (reported with JAWS, 11/2026).
            event.Skip()
            return

        # Arrow keys to switch tabs: all four on macOS, where the tab view doesn't
        # take them; Up and Down on Windows, whose tab control ignores them. The
        # key is passed on only on macOS (for VoiceOver's announcement); on
        # Windows passing it on is what caused the double move.
        if keycode in (wx.WXK_LEFT, wx.WXK_UP):
            self.notebook.SetSelection((current_page - 1) % page_count)
            if on_mac:
                event.Skip()
            return

        elif keycode in (wx.WXK_RIGHT, wx.WXK_DOWN):
            self.notebook.SetSelection((current_page + 1) % page_count)
            if on_mac:
                event.Skip()
            return
        
        # Cmd+Shift+[ and Cmd+Shift+] (macOS standard for previous/next tab)
        elif event.CmdDown() and event.ShiftDown():
            if keycode == ord('['):
                new_page = (current_page - 1) % page_count
                self.notebook.SetSelection(new_page)
                return
            elif keycode == ord(']'):
                new_page = (current_page + 1) % page_count
                self.notebook.SetSelection(new_page)
                return
        
        # Enter or Space to move focus into current tab's content
        elif keycode in (wx.WXK_RETURN, wx.WXK_SPACE):
            # Move focus to the first control in the tab, in Tab order. The old
            # loop looked only at the page's direct children, so it skipped the
            # settings list (inside a group box) and landed on Change Setting.
            current_tab = self.notebook.GetPage(current_page)
            target = first_tab_stop(current_tab) if current_tab else None
            if target is not None:
                target.SetFocus()
                return
            event.Skip()
            return
        
        # Let other keys pass through
        event.Skip()
    
    def _set_initial_focus(self):
        """Set focus to the first settings list in the first tab"""
        # Get first category
        first_category = list(self.settings_metadata.keys())[0]
        widgets = self.category_widgets.get(first_category)
        if widgets and 'settings_list' in widgets:
            widgets['settings_list'].SetFocus()

    def _is_activate_key(self, event: wx.KeyEvent) -> bool:
        """Return True for keys that should activate the selected setting."""
        key = event.GetKeyCode()
        return key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_SPACE)

    def _on_change_button_key(self, category: str, event: wx.KeyEvent):
        """Allow Enter/Space to activate the Change Setting button."""
        if self._is_activate_key(event):
            logger.info("Change Setting activated via button key: category=%s", category)
            self.change_setting(category, event)
            return
        event.Skip()

    def _on_settings_list_key(self, category: str, event: wx.KeyEvent):
        """Open the edit dialog from the settings list with Enter/Space."""
        if self._is_activate_key(event):
            logger.info("Change Setting activated via settings list key: category=%s", category)
            self.change_setting(category, event)
            return
        event.Skip()
    
    def create_category_tab(self, parent, category: str) -> wx.Panel:
        """Create a tab panel for a specific category"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        row = wx.BoxSizer(wx.HORIZONTAL)

        # Tab order is creation order: the settings list, then its explanation,
        # then Change Setting. The explanation used to bounce focus back to the
        # list, so a keyboard or screen reader user only heard what a setting
        # meant after opening Change Setting. It is now a read-only box you can
        # Tab to and read with the cursor, updated as the list selection moves.

        # Left: the settings list
        left_box = wx.StaticBox(panel, label="Settings:")
        left_sizer = wx.StaticBoxSizer(left_box, wx.VERTICAL)

        settings_list = wx.ListBox(left_box, style=wx.LB_SINGLE | wx.LB_NEEDED_SB, name=f"{category} settings")
        settings_list.Bind(wx.EVT_LISTBOX, lambda e: self.on_setting_selected(category, e))
        settings_list.Bind(wx.EVT_KEY_DOWN, lambda e: self._on_settings_list_key(category, e))
        left_sizer.Add(settings_list, 1, wx.EXPAND | wx.ALL, 5)
        row.Add(left_sizer, 1, wx.EXPAND | wx.ALL, 5)

        # Right: what the selected setting does
        right_box = wx.StaticBox(panel, label="Explanation:")
        right_sizer = wx.StaticBoxSizer(right_box, wx.VERTICAL)

        explanation_text = wx.TextCtrl(right_box, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        name_for_screen_readers(explanation_text, "Explanation")
        right_sizer.Add(explanation_text, 1, wx.EXPAND | wx.ALL, 5)
        row.Add(right_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(row, 1, wx.EXPAND)

        # Below both: Change Setting, so it comes after the explanation in Tab order.
        # No Alt letter: there is one of these on every settings tab, and a letter
        # repeated in one dialog cycles focus instead of pressing (hidden notebook
        # pages share the namespace; docs/KEYBOARD_SHORTCUTS.md). Enter on the
        # list opens the same editor.
        change_button = wx.Button(panel, label="Change Setting")
        change_button.Enable(False)
        change_button.Bind(wx.EVT_BUTTON, lambda e: self.change_setting(category, e))
        change_button.Bind(wx.EVT_KEY_DOWN, lambda e: self._on_change_button_key(category, e))
        sizer.Add(change_button, 0, wx.ALIGN_LEFT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        
        # Store references to widgets for later access
        self.category_widgets[category] = {
            'panel': panel,
            'settings_list': settings_list,
            'change_button': change_button,
            'explanation_text': explanation_text,
            'last_setting_name': None
        }
        
        # Populate the settings list
        self.load_category_settings(category)
        
        return panel
    
    def create_dialog_buttons(self, parent):
        """Create OK, Cancel, Apply buttons for the dialog"""
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        btn_sizer.AddStretchSpacer()
        
        # OK, Cancel, Apply buttons
        self.ok_btn = wx.Button(parent, wx.ID_OK, label="OK")
        self.ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        btn_sizer.Add(self.ok_btn, 0, wx.ALL, 5)
        
        self.cancel_btn = wx.Button(parent, wx.ID_CANCEL, label="Cancel")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
        
        self.apply_btn = wx.Button(parent, wx.ID_APPLY, label="Apply")
        self.apply_btn.Bind(wx.EVT_BUTTON, self.on_apply)
        btn_sizer.Add(self.apply_btn, 0, wx.ALL, 5)
        
        return btn_sizer
    
    def load_all_configs(self):
        """Load all configuration files"""
        from idt_core.config_loader import load_json_config
        for name, path in self.config_files.items():
            try:
                if path.exists():
                    # Through config_loader, so Configure shows what processing
                    # uses: the saved copy with any section it lacks filled in
                    # from the shipped defaults, after the one-time fix-up.
                    self.configs[name], _p, _s = load_json_config(path.name, explicit=str(path))
                else:
                    self.configs[name] = {}
                    print(f"Warning: {path} not found")
            except Exception as e:
                self.configs[name] = {}
                show_warning(self, f"Error loading {path}:\n{str(e)}")
        normalise_generation_section(self.configs.get("image_describer"))

    def load_category_settings(self, category: str):
        """Load settings for a specific category into its tab"""
        widgets = self.category_widgets.get(category)
        if not widgets:
            return
        
        settings_list = widgets['settings_list']
        explanation_text = widgets['explanation_text']
        
        # Clear current list
        settings_list.Clear()
        explanation_text.Clear()
        
        # Load settings for this category
        settings = self.settings_metadata.get(category, {})
        
        for setting_name, setting_info in settings.items():
            # Get current value
            current_value = self.get_setting_value(setting_info)
            
            # "Default provider: Ollama", never the code name (#422)
            display_text = f"{setting_label(setting_name)}: {_display_value(setting_info, current_value)}"

            settings_list.Append(display_text, setting_name)
        
        # Select first item if available
        if settings_list.GetCount() > 0:
            settings_list.SetSelection(0)
            self.on_setting_selected(category, None)
    
    def on_setting_selected(self, category: str, event):
        """Handle setting selection in a category tab"""
        widgets = self.category_widgets.get(category)
        if not widgets:
            return
        
        settings_list = widgets['settings_list']
        change_button = widgets['change_button']
        explanation_text = widgets['explanation_text']
        
        selection = settings_list.GetSelection()
        if selection == wx.NOT_FOUND:
            change_button.Enable(False)
            explanation_text.Clear()
            return
        
        setting_name = settings_list.GetClientData(selection)
        widgets['last_setting_name'] = setting_name
        setting_info = self.settings_metadata[category][setting_name]
        
        # Show explanation with range/choices info
        description = setting_info.get("description", "No description available")
        
        # Add range info if available
        if "range" in setting_info:
            description += f"\n\nRange: {setting_info['range'][0]} to {setting_info['range'][1]}"
        
        # Add choices if available
        if "choices" in setting_info:
            description += f"\n\nOptions: {', '.join(str(_choice_label(setting_info, c)) for c in setting_info['choices'])}"
        
        explanation_text.SetValue(description)
        
        change_button.Enable(True)
    
    def get_setting_value(self, setting_info: Dict[str, Any]) -> Any:
        """Get current value for a setting"""
        config_name = setting_info["file"]
        path = setting_info["path"]
        
        config = self.configs.get(config_name, {})
        
        # Navigate through nested path
        value = config
        for key in path:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def set_setting_value(self, setting_info: Dict[str, Any], new_value: Any):
        """Set a new value for a setting"""
        config_name = setting_info["file"]
        path = setting_info["path"]
        
        config = self.configs.get(config_name, {})

        if new_value is None and setting_info.get("type") in _AUTO_TYPES:
            # Automatic is stored as absence, and empty sections are pruned, so
            # the file only ever holds what the user chose.
            _remove_path(config, path)
            return

        # Navigate to the parent of the target key
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the value
        current[path[-1]] = new_value
    
    def change_setting(self, category: str, event):
        """Open dialog to change the selected setting in a category"""
        widgets = self.category_widgets.get(category)
        if not widgets:
            logger.warning("Change Setting requested but category widgets missing: %s", category)
            return
        
        settings_list = widgets['settings_list']
        
        selection = settings_list.GetSelection()
        if selection == wx.NOT_FOUND:
            setting_name = widgets.get('last_setting_name')
            if not setting_name:
                logger.warning("Change Setting requested with no selection: %s", category)
                return
            # Recover selection index for updates if focus cleared the listbox selection.
            for index in range(settings_list.GetCount()):
                if settings_list.GetClientData(index) == setting_name:
                    selection = index
                    break
        else:
            setting_name = settings_list.GetClientData(selection)
            widgets['last_setting_name'] = setting_name
        
        setting_info = self.settings_metadata[category][setting_name]

        logger.info("Opening SettingEditDialog: category=%s setting=%s", category, setting_name)
        
        current_value = self.get_setting_value(setting_info)
        
        # Open edit dialog (it manages its own focus via EVT_SHOW)
        dialog = SettingEditDialog(self, setting_name, current_value, setting_info)
        dialog.CentreOnParent()
        
        logger.info("Calling ShowModal() for SettingEditDialog")
        result = dialog.ShowModal()
        logger.info("ShowModal() returned: %s", "OK" if result == wx.ID_OK else "CANCEL")
        
        if result == wx.ID_OK:
            # Update the value
            new_value = dialog.GetValue()
            self.set_setting_value(setting_info, new_value)
            
            # Update the list item text to show new value
            display_text = f"{setting_label(setting_name)}: {_display_value(setting_info, new_value)}"
            settings_list.SetString(selection, display_text)
            
            # Refresh the display
            self.on_setting_selected(category, None)
        
        dialog.Destroy()
    
    def save_all_configs(self):
        """Save all configuration files"""
        try:
            for name, config in self.configs.items():
                path = self.config_files[name]
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)

            # Reload API keys in providers after saving
            self._reload_provider_api_keys()

            # Workspace root lives in ~/.idt/config.json (shared with the CLI),
            # not in the JSON config files handled above.
            self._save_workspace_config()

            return True
        except Exception as e:
            show_error(self, f"Error saving configurations:\n{str(e)}")
            return False
    
    def _save_image_describer_config(self):
        """Save just the image_describer config file
        
        Used for immediate persistence of API key changes.
        """
        try:
            config = self.configs.get("image_describer", {})
            path = self.config_files["image_describer"]
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            # Reload API keys in providers after saving
            self._reload_provider_api_keys()
            
            return True
        except Exception as e:
            show_error(self, f"Error saving image_describer configuration:\n{str(e)}")
            return False
    
    def _reload_provider_api_keys(self):
        """Reload API keys from config into provider instances
        
        This must be called after saving API keys via the Configure dialog
        to make them available without restarting the application.
        """
        try:
            from ai_providers import get_all_providers
            
            # Get all provider instances
            providers = get_all_providers()
            
            # Reload API keys for providers that support it
            for provider_name, provider in providers.items():
                if hasattr(provider, 'reload_api_key'):
                    try:
                        provider.reload_api_key()
                        print(f"Reloaded API key for {provider_name}")
                    except Exception as e:
                        print(f"Warning: Failed to reload API key for {provider_name}: {e}")
        except Exception as e:
            print(f"Warning: Failed to reload provider API keys: {e}")
    
    def on_ok(self, event):
        """Handle OK button - save and close"""
        if self.save_all_configs():
            self.EndModal(wx.ID_OK)
    
    def on_cancel(self, event):
        """Handle Cancel button - discard changes and close"""
        # Could add confirmation dialog here if tracking modifications
        self.EndModal(wx.ID_CANCEL)
    
    def on_apply(self, event):
        """Handle Apply button - save but keep dialog open"""
        if self.save_all_configs():
            show_info(self, "All configurations saved successfully!")
    
    def on_dialog_close(self, event):
        """Handle dialog close event"""
        # Could add unsaved changes check here
        if event.CanVeto():
            self.EndModal(wx.ID_CANCEL)
        else:
            self.Destroy()
    
    def create_workspace_tab(self, parent) -> wx.Panel:
        """Create the Workspace tab for configuring where .idtw bundles are saved.

        This is the GUI front end for the same setting the CLI exposes as
        `idt config --set workspace_root=...`; both read and write
        ~/.idt/config.json through UserConfig, so they cannot drift apart.
        """
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        try:
            from idt_core.config import UserConfig
            cfg = UserConfig.load()
            self._workspace_initial_custom = cfg.workspace_root or ""
            default_display = str(cfg.workspace_root_path())
        except Exception:
            self._workspace_initial_custom = ""
            default_display = str(Path.home() / "Documents" / "idt")

        sizer.Add(readable_text(
            panel,
            "Default location where workspace bundles (.idtw files) are saved "
            "when you run a batch without opening an existing workspace.\n\n"
            "Leave blank to use the built-in default: ~/Documents/idt",
            "About the workspace location"), 0, wx.ALL, 10)

        # Read-only display of the resolved path
        sizer.Add(wx.StaticText(panel, label="Resolved default location:"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.workspace_current_text = wx.TextCtrl(
            panel, value=default_display,
            style=wx.TE_READONLY,
            name="Resolved workspace location"
        )
        sizer.Add(self.workspace_current_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Editable custom path
        sizer.Add(wx.StaticText(panel, label="Custom location (leave blank to use default):"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        path_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.workspace_path_text = wx.TextCtrl(
            panel, value=self._workspace_initial_custom,
            name="Custom workspace location"
        )
        self.workspace_path_text.Bind(wx.EVT_TEXT, lambda e: self._update_workspace_display())
        path_sizer.Add(self.workspace_path_text, 1, wx.EXPAND | wx.RIGHT, 5)
        browse_btn = wx.Button(panel, label="Browse...")
        browse_btn.Bind(wx.EVT_BUTTON, self._on_workspace_browse)
        path_sizer.Add(browse_btn, 0)
        sizer.Add(path_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        reset_btn = wx.Button(panel, label="Reset to Default")
        reset_btn.Bind(wx.EVT_BUTTON, self._on_workspace_reset)
        sizer.Add(reset_btn, 0, wx.LEFT | wx.BOTTOM, 10)

        sizer.Add(readable_text(
            panel,
            "This setting is shared with the idt command-line tool and stored in "
            "~/.idt/config.json. You can also change it from the terminal with:\n"
            "    idt config --set workspace_root=<path>\n"
            "    idt config --set workspace_root=   (to reset to default)",
            "Workspace location from the command line"), 0, wx.ALL, 10)

        panel.SetSizer(sizer)
        return panel

    def _on_workspace_browse(self, event):
        """Open a directory picker for the workspace root."""
        current = self.workspace_path_text.GetValue().strip()
        default_path = current if current else str(Path.home() / "Documents")
        dlg = wx.DirDialog(
            self, "Choose default workspace location",
            defaultPath=default_path,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.workspace_path_text.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _on_workspace_reset(self, event):
        """Clear the custom workspace root, reverting to ~/Documents/idt."""
        self.workspace_path_text.SetValue("")

    def _update_workspace_display(self):
        """Keep the resolved-path display in sync as the user types."""
        if not hasattr(self, 'workspace_current_text'):
            return
        try:
            from idt_core.config import UserConfig
            custom = self.workspace_path_text.GetValue().strip()
            cfg = UserConfig()
            cfg.workspace_root = custom or None
            self.workspace_current_text.SetValue(str(cfg.workspace_root_path()))
        except Exception:
            pass

    def _save_workspace_config(self):
        """Persist the workspace root to ~/.idt/config.json via UserConfig."""
        if not hasattr(self, 'workspace_path_text'):
            return
        try:
            from idt_core.config import UserConfig
            cfg = UserConfig.load()
            custom = self.workspace_path_text.GetValue().strip()
            cfg.workspace_root = custom or None
            cfg.save()
            logger.info("Workspace root saved: %s", cfg.workspace_root_path())
        except Exception as e:
            logger.warning("Failed to save workspace config: %s", e)

    def create_api_keys_tab(self, parent) -> wx.Panel:
        """Create the API Keys management tab"""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Description
        desc_text = wx.StaticText(panel, label="Manage API keys for cloud AI providers:")
        sizer.Add(desc_text, 0, wx.ALL, 10)
        
        # ListBox for API keys
        list_label = wx.StaticText(panel, label="Saved API Keys:")
        sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        self.api_keys_list = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB, name="API Keys list")
        self.api_keys_list.Bind(wx.EVT_KEY_DOWN, self.on_api_key_list_key)
        sizer.Add(self.api_keys_list, 1, wx.EXPAND | wx.ALL, 10)
        
        # Buttons. One button sets the selected provider's key; its label
        # follows the selection ("Add Key" when there's none, "Replace Key"
        # when there is), so it says what it will do before it's pressed.
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._api_keys_btn_sizer = btn_sizer

        self.add_key_btn = wx.Button(panel, label=self.ADD_KEY_LABEL)
        self.add_key_btn.Bind(wx.EVT_BUTTON, self.on_add_api_key)
        btn_sizer.Add(self.add_key_btn, 0, wx.ALL, 5)

        self.test_key_btn = wx.Button(panel, label="&Test Key")
        self.test_key_btn.Bind(wx.EVT_BUTTON, self.on_test_api_key)
        self.test_key_btn.Enable(False)
        btn_sizer.Add(self.test_key_btn, 0, wx.ALL, 5)

        self.delete_key_btn = wx.Button(panel, label="Delete Key")
        self.delete_key_btn.Bind(wx.EVT_BUTTON, self.on_delete_api_key)
        self.delete_key_btn.Enable(False)
        btn_sizer.Add(self.delete_key_btn, 0, wx.ALL, 5)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        # Test Key's result: read-only text in the Tab order, right after the
        # buttons. Focus goes to it when a test starts ("Testing your ...
        # key...") and it is read again when the answer comes, so a screen
        # reader hears the result without hunting for it.
        sizer.Add(wx.StaticText(panel, label="Test result:"), 0, wx.LEFT | wx.RIGHT, 10)
        self.key_test_result = wx.TextCtrl(
            panel, value=self.KEY_TEST_INTRO,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            name="Test result")
        name_for_screen_readers(self.key_test_result, "Test result")
        self.key_test_result.SetMinSize((600, self.key_test_result.GetCharHeight() * 4 + 8))
        sizer.Add(self.key_test_result, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        #: The running test's token: a result is shown only if it carries the
        #: current one, so one that arrives after the dialog moved on is dropped.
        self._key_test_token = None

        # Help text
        sizer.Add(readable_text(
            panel,
            "API keys are required for OpenAI and Claude (Anthropic), and for the "
            "optional Ollama web search in chat (free key from ollama.com). "
            "Ollama itself runs locally and needs no key. Keys are shared with "
            "IDT Chat and the idt command line. A Claude key must be assigned to a "
            "workspace in the Claude Console (new keys are, by default). "
            "Test Key sends one short request with the selected provider's key to "
            "check that it works. For Claude and OpenAI that request is paid for "
            "on your account and costs a small fraction of a cent; for Ollama web "
            "search it is one web search, which counts toward your ollama.com "
            "usage limits.",
            "About API keys", width=600), 0, wx.ALL, 10)

        panel.SetSizer(sizer)

        # Bind selection event
        self.api_keys_list.Bind(wx.EVT_LISTBOX, self.on_api_key_selected)

        # Load current API keys
        self.load_api_keys()

        return panel

    ADD_KEY_LABEL = "Add Key"
    REPLACE_KEY_LABEL = "Replace Key"
    KEY_TEST_INTRO = ("Select a provider with a key and choose Test Key to check "
                      "that the key works. The result appears here.")

    def _selected_api_key_provider(self):
        """The selected row's provider name, or None."""
        selection = self.api_keys_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return None
        return self.api_keys_list.GetClientData(selection)

    def _is_known_provider(self, provider) -> bool:
        return any(canonical == provider
                   for _label, canonical in ApiKeyEditDialog.PROVIDER_CHOICES)

    def _provider_has_key(self, provider) -> bool:
        """Whether there's a key for this row: from idt_core.keys for the
        known providers; an unrecognised row is listed only when it has one."""
        if not provider:
            return False
        if not self._is_known_provider(provider):
            return True
        return getattr(self, "_api_key_sources", {}).get(provider) is not None

    def _sync_api_key_buttons(self):
        """Label and enable the buttons for the selected row."""
        from idt_core.key_check import can_test

        provider = self._selected_api_key_provider()
        has_key = self._provider_has_key(provider)
        label = self.REPLACE_KEY_LABEL if has_key else self.ADD_KEY_LABEL
        if self.add_key_btn.GetLabel() != label:
            self.add_key_btn.SetLabel(label)
            self._api_keys_btn_sizer.Layout()
        self.test_key_btn.Enable(bool(has_key and can_test(provider)
                                      and self._key_test_token is None))
        self.delete_key_btn.Enable(bool(has_key))
    
    #: Config-file spellings that mean each canonical provider; used when a
    #: key is migrated out of the plaintext config into the credential store.
    _CONFIG_SPELLINGS = {
        "claude": {"claude", "anthropic"},
        "openai": {"openai", "open_ai", "open ai"},
        "ollama.com": {"ollama.com", "ollama_com", "ollama cloud", "ollama_cloud"},
    }

    def _purge_config_key(self, canonical) -> bool:
        """Drop every config-file spelling of ``canonical``'s key.

        Called after a key is written to the credential store: leaving the
        plaintext copy behind would defeat the point of the store, and the
        store already outranks the config in resolution order.
        """
        config = self.configs.setdefault("image_describer", {})
        api_keys = config.get("api_keys")
        if not isinstance(api_keys, dict):
            return False
        # The fallback is lowercased because the comparison below is: an
        # unrecognised provider row (e.g. "Gemini") would otherwise never
        # match its own config entry and could not be deleted.
        spellings = self._CONFIG_SPELLINGS.get(
            canonical, {str(canonical).strip().lower()})
        doomed = [k for k in api_keys
                  if str(k).strip().lower() in spellings]
        for key in doomed:
            del api_keys[key]
        return bool(doomed)

    def load_api_keys(self):
        """Populate the list: one row per provider, saying where its key is.

        No key material is shown — the old list displayed the first 8 and
        last 4 characters of every stored key, which is more of a secret
        than a settings screen should leak.
        """
        from idt_core.keys import key_source

        # Keep the same provider selected across a reload (after Add, Replace
        # or Delete), so focus and the buttons stay with the row just changed.
        previous = self._selected_api_key_provider()
        self.api_keys_list.Clear()
        # Remembered for the buttons: looking a source up again on every
        # arrow press would run the Keychain's `security` tool per key press
        # on a Mac.
        self._api_key_sources = {}
        known = set()
        for label, canonical in ApiKeyEditDialog.PROVIDER_CHOICES:
            source = key_source(canonical)
            self._api_key_sources[canonical] = source
            status = {
                "environment": "set via environment variable",
                "credential store": "stored securely",
                "config file": "stored in the config file",
                "legacy file": "stored in a legacy key file",
                None: "not set",
            }.get(source, source)
            index = self.api_keys_list.Append(f"{label}: {status}")
            self.api_keys_list.SetClientData(index, canonical)
            known.update(self._CONFIG_SPELLINGS.get(canonical, {canonical}))

        # Any other key sitting in the config file gets a row of its own.
        # Listing only the three canonical providers made a key written by an
        # older build (or by hand) invisible AND undeletable — it stayed in
        # plaintext in image_describer_config.json with no way to remove it
        # from this screen.
        config = self.configs.get("image_describer", {})
        api_keys = config.get("api_keys")
        if isinstance(api_keys, dict):
            for name, value in api_keys.items():
                if str(name).strip().lower() in known or name == "description":
                    continue
                if not (isinstance(value, str) and value.strip()):
                    continue
                index = self.api_keys_list.Append(
                    f"{name}: stored in the config file (unrecognised provider)")
                self.api_keys_list.SetClientData(index, name)

        # A row is always selected, so the key button always knows whose key
        # it sets and never has to ask.
        if self.api_keys_list.GetCount():
            index = 0
            for i in range(self.api_keys_list.GetCount()):
                if self.api_keys_list.GetClientData(i) == previous:
                    index = i
                    break
            self.api_keys_list.SetSelection(index)
        self._sync_api_key_buttons()

    def on_api_key_selected(self, event):
        """Handle API key selection"""
        self._sync_api_key_buttons()
        # The last result belongs to the row it was for; a new row starts
        # from the explanation (not while a test is still running).
        if self._key_test_token is None:
            self.key_test_result.ChangeValue(self.KEY_TEST_INTRO)

    def _store_key(self, canonical, api_key):
        """Save one key: credential store first, config file as fallback.

        When the store takes the key, any plaintext copy in the config is
        removed — the store outranks the config in resolution order, so a
        stale config copy would be both a leak and a lie.
        """
        from idt_core.keys import credential_store_name, set_api_key

        if credential_store_name() and set_api_key(canonical, api_key):
            if self._purge_config_key(canonical):
                self._save_image_describer_config()
            return True

        # No usable store on this platform: keep the config-file behaviour.
        # setdefault, not get: .get("image_describer", {}) hands back a fresh
        # throwaway dict when the section is absent, so the key was written
        # into a temporary that died at return - saved, reported as success,
        # and gone.
        config = self.configs.setdefault("image_describer", {})
        config.setdefault("api_keys", {})[canonical] = api_key
        self._save_image_describer_config()
        return True

    def _store_unrecognised_key(self, name, api_key):
        """Replace an unrecognised provider's key where it lives: in the
        config file, under the same name. The credential store would hide it
        (only known providers are read from there) and nothing would use it."""
        config = self.configs.setdefault("image_describer", {})
        config.setdefault("api_keys", {})[name] = api_key
        self._save_image_describer_config()

    def on_add_api_key(self, event):
        """Add or replace the selected provider's key.

        With a row selected (always, once the list is filled) the dialog is
        for that provider: no provider list, focus straight in the key box.
        The current key is never pre-filled: it may live in the credential
        store, and a settings dialog should not read secrets back just to
        display them masked.
        """
        provider = self._selected_api_key_provider()
        if provider:
            dialog = ApiKeyEditDialog(self, provider=provider,
                                      replacing=self._provider_has_key(provider))
        else:
            dialog = ApiKeyEditDialog(self)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return
            new_provider, new_key = dialog.get_values()
        finally:
            dialog.Destroy()
        if provider and not self._is_known_provider(provider):
            self._store_unrecognised_key(provider, new_key)
        else:
            self._store_key(new_provider, new_key)
        self._abandon_key_test()
        self._reload_provider_api_keys()
        self.load_api_keys()
        self.api_keys_list.SetFocus()

        if self._api_key_sources.get(new_provider) == "environment":
            from shared.wx_common import show_warning
            show_warning(
                self,
                f"The key was saved, but an environment variable still provides "
                f"a key for {ApiKeyEditDialog.label_for(new_provider)}, and IDT "
                f"uses that one first. Remove the environment variable to use "
                f"the key you saved.")

    # -- Test Key --------------------------------------------------------

    KEY_CHANGED_DURING_TEST = "The key changed while it was being tested. Test it again."

    def _abandon_key_test(self):
        """A key changed while a test ran: its answer would be about the old
        key, so drop it when it comes and say so now."""
        if self._key_test_token is not None:
            self._key_test_token = None
            self.key_test_result.ChangeValue(self.KEY_CHANGED_DURING_TEST)
            self.key_test_result.SetInsertionPoint(0)

    def on_test_api_key(self, event):
        """Test the selected provider's key with one tiny request, on a
        background thread. Returns True if a test started."""
        import threading

        from idt_core.key_check import can_test, test_api_key

        provider = self._selected_api_key_provider()
        if (self._key_test_token is not None or not provider
                or not can_test(provider) or not self._provider_has_key(provider)):
            return False
        label = ApiKeyEditDialog.label_for(provider)
        token = object()
        self._key_test_token = token
        self.key_test_result.ChangeValue(f"Testing your {label} key...")
        self.key_test_result.SetInsertionPoint(0)
        # Focus to the result before Test Key is turned off: a control turned
        # off with the focus on it leaves the focus nowhere.
        self.key_test_result.SetFocus()
        self.test_key_btn.Enable(False)

        def work():
            try:
                result = test_api_key(provider)
            except Exception:                                   # noqa: BLE001
                # test_api_key never raises; this is only a backstop, and its
                # text is not shown because it was not scrubbed.
                from idt_core.key_check import KeyTestResult
                result = KeyTestResult(False, "The test didn't finish.")
            try:
                wx.CallAfter(self._key_test_done, token, result)
            except Exception:                                   # noqa: BLE001
                pass    # the app is closing; nothing to show it in

        threading.Thread(target=work, name="api-key-test", daemon=True).start()
        return True

    def _key_test_done(self, token, result):
        """Show a finished test's result, unless the dialog is gone or the
        test is no longer the current one."""
        if not self or self.IsBeingDeleted() or token is not self._key_test_token:
            return
        self._key_test_token = None
        self._sync_api_key_buttons()
        self.key_test_result.ChangeValue(self.key_test_text(result))
        self.key_test_result.SetInsertionPoint(0)
        focus = wx.Window.FindFocus()
        if focus is not None and focus.GetId() == self.key_test_result.GetId():
            # A screen reader doesn't read a focused box's new text by itself;
            # moving focus away and straight back makes JAWS and NVDA read it.
            fallback = self.test_key_btn if self.test_key_btn.IsEnabled() else self.api_keys_list
            fallback.SetFocus()
            wx.CallLater(100, self._refocus_key_test_result)

    @staticmethod
    def key_test_text(result) -> str:
        """The result box's text: the short verdict on a line of its own,
        then the detail. JAWS and NVDA read only the cursor's line when focus
        lands in a multi-line box, so that line has to be the answer. A key
        that works is one short line ("Your Claude key works. That test cost
        0.00038 cents."), so it stays whole."""
        if not result.ok and result.verdict and result.detail:
            return f"{result.verdict}\n{result.detail}"
        return result.message

    def _refocus_key_test_result(self):
        if self and not self.IsBeingDeleted() and self.IsShown():
            self.key_test_result.SetFocus()

    def on_delete_api_key(self, event):
        """Delete the selected provider's stored key"""
        from idt_core.keys import delete_api_key

        selection = self.api_keys_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        provider = self.api_keys_list.GetClientData(selection)
        label = ApiKeyEditDialog.label_for(provider)

        # Confirm deletion
        from shared.wx_common import ask_yes_no
        if not ask_yes_no(self, f"Delete API key for {label}?", "Confirm Delete"):
            return

        # Focus first: Delete Key is about to be turned off (the row has no
        # key now), and a control turned off with the focus on it leaves the
        # focus nowhere.
        self.api_keys_list.SetFocus()

        # Remove from the credential store and from the config file.
        delete_api_key(provider)
        if self._purge_config_key(provider):
            self._save_image_describer_config()
        self._abandon_key_test()
        self._reload_provider_api_keys()
        self.load_api_keys()

        remaining = self._api_key_sources.get(provider)
        if remaining == "environment":
            from shared.wx_common import show_warning
            show_warning(
                self,
                f"The stored key was removed, but an environment variable "
                f"still provides a key for {label}.")

    def on_api_key_list_key(self, event):
        """Handle keyboard navigation in API keys list"""
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_TAB and not event.ShiftDown():
            # Move focus to the Add Key / Replace Key button
            if self.add_key_btn:
                self.add_key_btn.SetFocus()
            return
        event.Skip()

    # ------------------------------------------------------------------
    # MLX Models tab — lets users add/remove custom HuggingFace model IDs
    # without needing a new build.  Persisted in image_describer_config.json
    # under the key "mlx_extra_models".
    # ------------------------------------------------------------------

    def create_mlx_models_tab(self, parent) -> wx.Panel:
        """Create the MLX Models management tab (macOS only)."""
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(readable_text(
            panel,
            "Add extra MLX model IDs from the mlx-community HuggingFace hub.\n"
            "These supplement the built-in model list without requiring a new build.\n"
            "Example: mlx-community/gemma-4-26b-a4b-it-4bit",
            "About extra MLX models"), 0, wx.ALL, 10)

        # --- Built-in models (read-only reference) ---
        builtin_label = wx.StaticText(panel, label="Built-in models (read-only):")
        sizer.Add(builtin_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.mlx_builtin_list = wx.ListBox(
            panel,
            style=wx.LB_SINGLE | wx.LB_NEEDED_SB,
            name="Built-in MLX models"
        )
        self.mlx_builtin_list.Enable(False)
        sizer.Add(self.mlx_builtin_list, 1, wx.EXPAND | wx.ALL, 10)

        # --- User-defined extra models ---
        extra_label = wx.StaticText(panel, label="Your extra models:")
        sizer.Add(extra_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.mlx_extra_list = wx.ListBox(
            panel,
            style=wx.LB_SINGLE | wx.LB_NEEDED_SB,
            name="User MLX models"
        )
        self.mlx_extra_list.Bind(wx.EVT_LISTBOX, self.on_mlx_extra_selected)
        sizer.Add(self.mlx_extra_list, 1, wx.EXPAND | wx.ALL, 10)

        # --- Buttons ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.mlx_add_btn = wx.Button(panel, label="Add Model")
        self.mlx_add_btn.Bind(wx.EVT_BUTTON, self.on_mlx_add)
        btn_sizer.Add(self.mlx_add_btn, 0, wx.ALL, 5)

        self.mlx_remove_btn = wx.Button(panel, label="Remove Model")
        self.mlx_remove_btn.Bind(wx.EVT_BUTTON, self.on_mlx_remove)
        self.mlx_remove_btn.Enable(False)
        btn_sizer.Add(self.mlx_remove_btn, 0, wx.ALL, 5)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)

        help_text = wx.StaticText(
            panel,
            label="Changes are saved immediately. The model will appear in the MLX "
                  "model dropdown the next time you open the processing options."
        )
        help_text.SetForegroundColour(wx.Colour(100, 100, 100))
        help_text.Wrap(580)
        sizer.Add(help_text, 0, wx.ALL, 10)

        panel.SetSizer(sizer)

        # Populate lists
        self._load_mlx_lists()

        return panel

    def _load_mlx_lists(self):
        """Populate both MLX list boxes from code defaults and config."""
        # Built-in list
        self.mlx_builtin_list.Clear()
        try:
            from ai_providers import MLXProvider
            for m in MLXProvider.KNOWN_MODELS:
                self.mlx_builtin_list.Append(m)
        except Exception:
            pass

        # User extras from config
        self.mlx_extra_list.Clear()
        config = self.configs.get("image_describer", {})
        for m in config.get("mlx_extra_models", []):
            self.mlx_extra_list.Append(m)

        self.mlx_remove_btn.Enable(False)

    def on_mlx_extra_selected(self, event):
        """Enable Remove button when an extra model is selected."""
        self.mlx_remove_btn.Enable(self.mlx_extra_list.GetSelection() != wx.NOT_FOUND)

    def on_mlx_add(self, event):
        """Prompt user for a model ID and add it to the extra list."""
        dlg = wx.TextEntryDialog(
            self,
            "Enter the full HuggingFace model ID:\n(e.g. mlx-community/gemma-4-26b-a4b-it-4bit)",
            caption="Add MLX Model",
            value="mlx-community/"
        )
        if dlg.ShowModal() == wx.ID_OK:
            model_id = dlg.GetValue().strip()
            dlg.Destroy()
            if not model_id:
                return

            # Guard against duplicates (built-in or already in extra list)
            try:
                from ai_providers import MLXProvider
                builtin = MLXProvider.KNOWN_MODELS
            except Exception:
                builtin = []
            config = self.configs.get("image_describer", {})
            extras = config.get("mlx_extra_models", [])

            if model_id in builtin:
                show_warning(self, f"'{model_id}' is already in the built-in model list.")
                return
            if model_id in extras:
                show_warning(self, f"'{model_id}' is already in your extra models.")
                return

            extras.append(model_id)
            config["mlx_extra_models"] = extras
            self._save_image_describer_config()
            self._load_mlx_lists()
        else:
            dlg.Destroy()

    def on_mlx_remove(self, event):
        """Remove the selected extra model after confirmation."""
        selection = self.mlx_extra_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return

        model_id = self.mlx_extra_list.GetString(selection)

        from shared.wx_common import ask_yes_no
        if not ask_yes_no(self, f"Remove '{model_id}' from your extra models?", "Confirm Remove"):
            return

        config = self.configs.get("image_describer", {})
        extras = config.get("mlx_extra_models", [])
        if model_id in extras:
            extras.remove(model_id)
        config["mlx_extra_models"] = extras
        self._save_image_describer_config()
        self._load_mlx_lists()

