"""
Common utilities for IDT wxPython applications.

Provides standardized functionality for:
- Path resolution in frozen and development modes
- JSON config file management with backup/restore
- Modified state tracking for document-based windows
- Standardized dialogs (file, directory, message, about)
- Utility functions for timestamps and filename sanitization
"""

import wx
import wx.adv
import json
import shutil
import sys
import re
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

try:
    from idt_core.config_loader import load_json_config
except ImportError:
    load_json_config = None

try:
    from idt_core import app_replaced
except ImportError:
    app_replaced = None


def _with_replaced_notice(message: str) -> str:
    """``message``, led by "quit and reopen" if the app was replaced while open.

    Whatever fails after that is a symptom, not the problem (see
    idt_core/app_replaced.py), so the one thing worth doing comes first.
    """
    try:
        if app_replaced is not None and app_replaced.replaced():
            return f"{app_replaced.notice()}\n\nThe error was: {message}"
    except Exception:
        pass
    return message


def watch_for_replacement() -> None:
    """Call once at startup, before the main loop, in a frozen app.

    Records the executable (idt_core/app_replaced.py) and, from then on, an
    exception no handler caught -- wx would only print it -- shows "quit and
    reopen" if the app has been replaced since, once. Otherwise the exception
    goes where it went before.
    """
    if app_replaced is None:
        return
    app_replaced.remember()
    previous = sys.excepthook
    told = []

    def hook(exc_type, exc, tb):
        previous(exc_type, exc, tb)
        try:
            if not told and app_replaced.replaced():
                told.append(True)
                wx.CallAfter(wx.MessageBox, app_replaced.notice(),
                             "Please reopen", wx.OK | wx.ICON_WARNING)
        except Exception:
            pass

    sys.excepthook = hook


# ==================== PATH RESOLUTION ====================

def get_base_directory() -> Path:
    """
    Get the base directory of the application.
    
    In frozen mode (PyInstaller), returns the directory containing the executable.
    In development mode, returns the project root directory.
    
    Returns:
        Path: Base directory path
    """
    if getattr(sys, 'frozen', False):
        # Frozen mode - return exe directory
        return Path(sys.executable).parent
    else:
        # Development mode - assume we're in a subdirectory, go to parent
        # This works for scripts in viewer/, prompt_editor/, etc.
        return Path(__file__).parent.parent


def find_file(filename: str, search_dirs: List[Union[str, Path]] = None) -> Optional[Path]:
    """
    Find a file by searching multiple directories.
    
    Args:
        filename: Name of file to find
        search_dirs: List of directories to search (default: common locations)
        
    Returns:
        Path to file if found, None otherwise
    """
    if search_dirs is None:
        base = get_base_directory()
        search_dirs = [
            base,
            base / 'scripts',
            base / 'models',
            Path.cwd(),
        ]
    
    # Convert all to Path objects
    search_dirs = [Path(d) for d in search_dirs]
    
    for directory in search_dirs:
        if not directory.exists():
            continue
            
        file_path = directory / filename
        if file_path.exists() and file_path.is_file():
            return file_path
    
    return None


def find_scripts_directory() -> Optional[Path]:
    """
    Find the scripts directory in frozen or development mode.
    
    Returns:
        Path to scripts directory if found, None otherwise
    """
    base = get_base_directory()
    
    if getattr(sys, 'frozen', False):
        # Frozen mode - check writable locations first, then bundled scripts
        candidates = [
            base / 'scripts',                 # Next to exe (writable)
            base.parent / 'scripts',          # One level up (writable)
            Path(sys._MEIPASS) / 'scripts',  # PyInstaller temp directory (read-only)
        ]
    else:
        # Development mode
        candidates = [
            base / 'scripts',
            base.parent / 'scripts',
        ]
    
    for path in candidates:
        if path.exists() and path.is_dir():
            return path

    return None


def writable_scripts_directory() -> Optional[Path]:
    """Where to WRITE config files: the user config dir, always.

    config_loader reads it before any shipped copy. Every other place is
    either overwritten (the installer replaces {app}\\scripts on each upgrade,
    an update replaces a folder build's <app>-lib) or read after it.
    """
    try:
        from idt_core.config_loader import get_user_config_dir
    except ImportError:
        return None
    user_dir = get_user_config_dir()
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def find_config_file(filename: str) -> Optional[Path]:
    """The config file in use for ``filename``: config_loader's answer.

    Kept for older callers. It used to search its own order and, in a frozen
    build, create {exe}\\scripts and copy a template there -- a third place
    settings could land, which an upgrade replaces. Read with
    config_loader.load_json_config; save to config_loader.writable_config_path.
    """
    try:
        from idt_core.config_loader import resolve_config
    except ImportError:
        return None
    path, source = resolve_config(filename)
    return None if source == 'missing_fallback' else path


# ==================== CONFIG MANAGEMENT ====================

class ConfigManager:
    """
    Manage JSON configuration files with backup/restore functionality.
    
    Features:
    - Load/save JSON configs with error handling
    - Automatic backup before save (.bak suffix)
    - Timestamp-based backups for archival
    - Get/set nested values by path
    - Restore from backup
    
    Example:
        config = ConfigManager(Path('config.json'))
        config.load()
        value = config.get_value(['section', 'key'], default='default')
        config.set_value(['section', 'key'], 'new_value')
        config.save()  # Creates config.json.bak automatically
    """
    
    def __init__(self, config_file: Path):
        """
        Initialize config manager.
        
        Args:
            config_file: Path to config JSON file
        """
        self.config_file = Path(config_file)
        self.config_data = {}
    
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from file.
        
        Returns:
            Dict containing config data
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        
        try:
            # Try config_loader first for frozen mode compatibility
            if load_json_config:
                # The filename argument is required; it was missing, so this
                # raised TypeError and fell to the except below.
                self.config_data, _, _ = load_json_config(self.config_file.name,
                                                          explicit=str(self.config_file))
            else:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
            return self.config_data
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in config file: {self.config_file}",
                e.doc, e.pos
            )
    
    def save(self, create_backup: bool = True):
        """
        Save configuration to file.
        
        Args:
            create_backup: If True, create .bak file before saving
            
        Raises:
            IOError: If file cannot be written
        """
        # Create backup if requested and file exists
        if create_backup and self.config_file.exists():
            self.create_backup()
        
        # Ensure parent directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save config
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise IOError(f"Failed to save config file: {e}")
    
    def create_backup(self, timestamp: bool = False) -> Path:
        """
        Create a backup of the config file.
        
        Args:
            timestamp: If True, append timestamp to backup name
            
        Returns:
            Path to backup file
        """
        if not self.config_file.exists():
            raise FileNotFoundError(f"Cannot backup non-existent file: {self.config_file}")
        
        if timestamp:
            # Create timestamped backup: config_backup_20260108_143022.json
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{self.config_file.stem}_backup_{timestamp_str}{self.config_file.suffix}"
            backup_path = self.config_file.parent / backup_name
        else:
            # Create simple .bak backup: config.json.bak
            backup_path = self.config_file.with_suffix(self.config_file.suffix + '.bak')
        
        shutil.copy2(self.config_file, backup_path)
        return backup_path
    
    def restore_backup(self, backup_file: Optional[Path] = None):
        """
        Restore configuration from backup.
        
        Args:
            backup_file: Path to backup file (default: use .bak file)
            
        Raises:
            FileNotFoundError: If backup file doesn't exist
        """
        if backup_file is None:
            backup_file = self.config_file.with_suffix(self.config_file.suffix + '.bak')
        
        backup_file = Path(backup_file)
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")
        
        shutil.copy2(backup_file, self.config_file)
        self.load()  # Reload from restored file
    
    def get_value(self, path: List[str], default: Any = None) -> Any:
        """
        Get a value from nested config using path.
        
        Args:
            path: List of keys to traverse (e.g., ['section', 'subsection', 'key'])
            default: Default value if path doesn't exist
            
        Returns:
            Value at path, or default if not found
            
        Example:
            value = config.get_value(['model_settings', 'temperature'], default=0.7)
        """
        current = self.config_data
        
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        
        return current
    
    def set_value(self, path: List[str], value: Any):
        """
        Set a value in nested config using path.
        
        Creates intermediate dictionaries as needed.
        
        Args:
            path: List of keys to traverse (e.g., ['section', 'subsection', 'key'])
            value: Value to set
            
        Example:
            config.set_value(['model_settings', 'temperature'], 0.9)
        """
        if not path:
            raise ValueError("Path cannot be empty")
        
        current = self.config_data
        
        # Navigate to parent of target
        for key in path[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        
        # Set final value
        current[path[-1]] = value
    
    def get_data(self) -> Dict[str, Any]:
        """Get the entire config data dictionary."""
        return self.config_data
    
    def set_data(self, data: Dict[str, Any]):
        """Set the entire config data dictionary."""
        self.config_data = data


# ==================== MODIFIED STATE TRACKING ====================

class ModifiedStateMixin:
    """
    Mixin class for tracking modified state in document-based windows.
    
    Provides:
    - modified flag tracking
    - Window title updates with * indicator
    - Unsaved changes confirmation dialog
    
    Usage:
        class MyFrame(wx.Frame, ModifiedStateMixin):
            def __init__(self):
                wx.Frame.__init__(self, None, title="My App")
                ModifiedStateMixin.__init__(self)
                self.original_title = "My App"
                
            def on_edit(self, event):
                self.mark_modified()
                
            def on_save(self, event):
                # ... save logic ...
                self.clear_modified()
    """
    
    def __init__(self):
        """Initialize modified state tracking."""
        self.modified = False
        self.original_title = ""
    
    def mark_modified(self):
        """Mark document as modified and update window title."""
        if not self.modified:
            self.modified = True
            self._update_title()
            # Update UI state if the method exists (for enabling save buttons, etc.)
            if hasattr(self, 'update_ui_state'):
                self.update_ui_state()
    
    def clear_modified(self):
        """Clear modified flag and update window title."""
        if self.modified:
            self.modified = False
            self._update_title()
            # Update UI state if the method exists (for disabling save buttons, etc.)
            if hasattr(self, 'update_ui_state'):
                self.update_ui_state()
    
    def update_window_title(self, app_name: str, document_name: str = ""):
        """
        Set the base window title with app name and optional document name.
        
        This is the public API for apps to update their window title context.
        The modified state indicator (*) is automatically added when needed.
        
        Args:
            app_name: Name of the application (e.g., "Prompt Editor")
            document_name: Optional document/file name to append (e.g., "config.json")
        
        Example:
            self.update_window_title("Prompt Editor", "image_describer_config.json")
            # Results in: "Prompt Editor - image_describer_config.json"
            # Or when modified: "Prompt Editor - image_describer_config.json *"
        """
        if document_name:
            self.original_title = f"{app_name} - {document_name}"
        else:
            self.original_title = app_name
        self._update_title()
    
    def _update_title(self):
        """Update window title to reflect modified state (internal)."""
        if hasattr(self, 'original_title') and self.original_title:
            title = self.original_title
        else:
            title = self.GetTitle().rstrip(' *')
            self.original_title = title
        
        if self.modified:
            self.SetTitle(f"{title} *")
        else:
            self.SetTitle(title)
    
    def confirm_unsaved_changes(self, parent=None) -> bool:
        """
        Show confirmation dialog if there are unsaved changes.
        
        Args:
            parent: Parent window (default: self)
            
        Returns:
            True if OK to proceed (saved or discarded changes)
            False if cancelled
        """
        if not self.modified:
            return True
        
        if parent is None:
            parent = self
        
        # CRITICAL FIX: Force parent window to front before showing dialog
        # This prevents the dialog from being hidden behind STAY_ON_TOP windows
        try:
            parent.Raise()
            parent.SetFocus()
        except Exception:
            pass  # Ignore if parent doesn't support these methods
        
        result = ask_yes_no_cancel(
            parent,
            "You have unsaved changes. Save before closing?",
            "Unsaved Changes"
        )
        
        if result == wx.ID_YES:
            # Call save method if it exists
            if hasattr(self, 'on_save'):
                self.on_save(None)
                return True
            elif hasattr(self, 'save'):
                self.save()
                return True
            else:
                return True
        elif result == wx.ID_NO:
            return True
        else:  # CANCEL
            return False


class NoFocusPanel(wx.Panel):
    """A panel that is only drawn on, and never a Tab stop.

    A wx.Panel with no focusable children takes focus itself, and on Windows
    SetCanFocus(False) doesn't stop that, so JAWS and NVDA landed on an empty
    "panel" (ImageDescriber's picture preview, between Viewer mode's list and
    its description; Kelly, 11/19/2026). Saying it accepts no focus does.
    """

    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False


# ==================== NUMBER FIELDS ====================

class _AccessibleName(wx.Accessible):
    """Gives a control the name a screen reader reads (childId 0 only, so its
    value or text is still read normally)."""

    def __init__(self, win, label: str):
        super().__init__(win)
        self._label = label

    def GetName(self, childId):
        if childId:
            return (wx.ACC_NOT_IMPLEMENTED, None)
        return (wx.ACC_OK, self._label)


def set_screen_reader_name(window, label: str) -> None:
    """Make ``label`` what JAWS, NVDA and VoiceOver call ``window``.

    SetName alone isn't enough on Windows: a native edit box takes its name
    from the static label just before it, so a field after "Value:" was read
    as "Value:" whatever SetName said (installed-build settings check,
    11/16/2026). A wx.Accessible answers for it there; macOS has no
    wx.Accessible and uses the name (shared/mac_accessibility publishes it).
    """
    window.SetName(label)
    try:
        window.SetAccessible(_AccessibleName(window, label))
    except (NotImplementedError, AttributeError):
        pass


def number_field(parent, info: Dict[str, Any], value: Any, name: str) -> wx.TextCtrl:
    """A text field for a number, named with its range for screen readers.

    A text field, not a SpinCtrl: a spin box rewrites a typed 150 to its
    maximum as soon as focus leaves it, so Tab to OK saved 100 without a word
    (#405, #406). Check it on OK with refuse_bad_number().
    """
    from shared.number_entry import spoken_range
    text = "" if value is None else str(value)
    field = wx.TextCtrl(parent, value=text)
    set_screen_reader_name(field, f"{name}{spoken_range(info)}")
    return field


def refuse_bad_number(parent, control: wx.TextCtrl, info: Dict[str, Any], title: str):
    """``(True, value)`` for a good entry; for a bad one, say why and ``(False, None)``.

    A message box rather than help text: JAWS doesn't read help text on focus.
    Focus goes back to the field with its text selected.
    """
    from shared.number_entry import validate_number
    value, error = validate_number(info, control.GetValue())
    if error:
        wx.MessageBox(error, title, wx.OK | wx.ICON_WARNING, parent)
        control.SetFocus()
        control.SelectAll()
        return False, None
    return True, value


# ==================== DIALOGS ====================

def show_error(parent, message: str, title: str = "Error"):
    """
    Show an error message dialog.
    
    Args:
        parent: Parent window
        message: Error message to display
        title: Dialog title
    """
    wx.MessageBox(_with_replaced_notice(message), title, wx.OK | wx.ICON_ERROR, parent)


def show_warning(parent, message: str, title: str = "Warning"):
    """
    Show a warning message dialog.
    
    Args:
        parent: Parent window
        message: Warning message to display
        title: Dialog title
    """
    wx.MessageBox(_with_replaced_notice(message), title, wx.OK | wx.ICON_WARNING, parent)


def show_info(parent, message: str, title: str = "Information"):
    """
    Show an information message dialog.
    
    Args:
        parent: Parent window
        message: Info message to display
        title: Dialog title
    """
    wx.MessageBox(message, title, wx.OK | wx.ICON_INFORMATION, parent)


def ask_yes_no(parent, message: str, title: str = "Confirm") -> bool:
    """
    Show a yes/no confirmation dialog.
    
    Args:
        parent: Parent window
        message: Question to ask
        title: Dialog title
        
    Returns:
        True if user clicked Yes, False if No
    """
    result = wx.MessageBox(message, title, wx.YES_NO | wx.ICON_QUESTION, parent)
    return result == wx.YES


def ask_yes_no_cancel(parent, message: str, title: str = "Confirm") -> int:
    """
    Show a yes/no/cancel confirmation dialog.
    
    Args:
        parent: Parent window
        message: Question to ask
        title: Dialog title
        
    Returns:
        wx.ID_YES, wx.ID_NO, or wx.ID_CANCEL
    """
    dlg = wx.MessageDialog(parent, message, title, wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
    result = dlg.ShowModal()
    dlg.Destroy()
    return result


def open_file_dialog(parent, message: str = "Open File", wildcard: str = "All files (*.*)|*.*",
                     default_dir: str = "", default_file: str = "") -> Optional[str]:
    """
    Show a file open dialog.
    
    Args:
        parent: Parent window
        message: Dialog title
        wildcard: File filter wildcard
        default_dir: Default directory
        default_file: Default filename
        
    Returns:
        Selected file path, or None if cancelled
        
    Example:
        path = open_file_dialog(self, "Open Config",
                               wildcard="JSON files (*.json)|*.json")
    """
    dlg = wx.FileDialog(
        parent, message,
        defaultDir=default_dir,
        defaultFile=default_file,
        wildcard=wildcard,
        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
    )
    
    if dlg.ShowModal() == wx.ID_OK:
        path = dlg.GetPath()
        dlg.Destroy()
        return path
    
    dlg.Destroy()
    return None


def save_file_dialog(parent, message: str = "Save File", wildcard: str = "All files (*.*)|*.*",
                     default_dir: str = "", default_file: str = "") -> Optional[str]:
    """
    Show a file save dialog.
    
    Args:
        parent: Parent window
        message: Dialog title
        wildcard: File filter wildcard
        default_dir: Default directory
        default_file: Default filename
        
    Returns:
        Selected file path, or None if cancelled
        
    Example:
        path = save_file_dialog(self, "Save Config",
                               wildcard="JSON files (*.json)|*.json",
                               default_file="config.json")
    """
    dlg = wx.FileDialog(
        parent, message,
        defaultDir=default_dir,
        defaultFile=default_file,
        wildcard=wildcard,
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    )
    
    if dlg.ShowModal() == wx.ID_OK:
        path = dlg.GetPath()
        dlg.Destroy()
        return path
    
    dlg.Destroy()
    return None


def select_directory_dialog(parent, message: str = "Select Directory",
                            default_path: str = "") -> Optional[str]:
    """
    Show a directory selection dialog.
    
    Args:
        parent: Parent window
        message: Dialog title
        default_path: Default directory path
        
    Returns:
        Selected directory path, or None if cancelled
    """
    dlg = wx.DirDialog(
        parent, message,
        defaultPath=default_path,
        style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST
    )
    
    if dlg.ShowModal() == wx.ID_OK:
        path = dlg.GetPath()
        dlg.Destroy()
        return path
    
    dlg.Destroy()
    return None


def show_about_dialog(parent, app_name: str, version: str,
                     description: str, developers: List[str] = None,
                     website: str = ""):
    """
    Show a standardized About dialog using HTML for screen reader accessibility.
    
    Args:
        parent: Parent window
        app_name: Application name
        version: Version string
        description: App description (supports newlines)
        developers: List of developer names
        website: Website URL
        
    Example:
        show_about_dialog(self, "MyApp", "1.0.0",
                         "An amazing application",
                         developers=["John Doe"],
                         website="https://example.com")
    """
    import wx.html
    
    # Create dialog
    dlg = wx.Dialog(parent, title=f"About {app_name}", 
                    style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
    dlg.SetSize((500, 400))
    
    # Create HTML window for content
    # The name carries the version: wxHtmlWindow draws its own text and screen
    # readers may get nothing from it but this name (#415).
    html_window = wx.html.HtmlWindow(dlg, style=wx.html.HW_SCROLLBAR_AUTO,
                                     name=f"{app_name}, version {version}")
    html_window.SetStandardFonts()
    
    # Build HTML content with semantic structure for screen readers
    html_content = f"""
    <html>
    <body>
        <h1>{app_name}</h1>
        <p><strong>Version:</strong> {version}</p>
        """
    
    # Add description (convert newlines to HTML)
    if description:
        # Replace bullet points and newlines with HTML
        desc_html = description.replace('\n\n', '</p><p>')
        desc_html = desc_html.replace('\n• ', '<br>• ')
        desc_html = desc_html.replace('\n', '<br>')
        html_content += f"<p>{desc_html}</p>"
    
    # Add developers if provided
    if developers:
        html_content += "<p><strong>Developed by:</strong><br>"
        for dev in developers:
            html_content += f"{dev}<br>"
        html_content += "</p>"
    
    # Add website if provided
    if website:
        html_content += f'<p><strong>Website:</strong> <a href="{website}">{website}</a></p>'
    
    # Add license info
    html_content += """
        <p><strong>License:</strong> Licensed under the terms of the project license.</p>
    </body>
    </html>
    """
    
    html_window.SetPage(html_content)
    
    # Create OK button
    ok_btn = wx.Button(dlg, wx.ID_OK, "OK")
    ok_btn.SetDefault()
    
    # Layout
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(html_window, 1, wx.ALL | wx.EXPAND, 10)
    sizer.Add(ok_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)
    
    dlg.SetSizer(sizer)
    
    # Set focus to OK button for keyboard access
    wx.CallAfter(ok_btn.SetFocus)
    
    # Show modal
    dlg.ShowModal()
    dlg.Destroy()


# ==================== UTILITIES ====================

def sanitize_filename(filename: str, preserve_case: bool = True) -> str:
    """
    Remove invalid characters from filename.
    
    Removes characters that are invalid in filenames across platforms:
    - Windows: < > : " / \\ | ? *
    - All: control characters
    
    Preserves: alphanumeric, underscore, hyphen, period
    
    Args:
        filename: Filename to sanitize
        preserve_case: If True, preserve case; if False, lowercase
        
    Returns:
        Sanitized filename
        
    Example:
        sanitize_filename("My File: (1).txt")  # "MyFile1.txt"
    """
    # Remove invalid characters
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    
    # Replace spaces and other whitespace with nothing (or could use '_')
    cleaned = re.sub(r'\s+', '', cleaned)
    
    # Remove any remaining non-alphanumeric except . - _
    cleaned = re.sub(r'[^a-zA-Z0-9._-]', '', cleaned)
    
    if not preserve_case:
        cleaned = cleaned.lower()
    
    # Ensure not empty
    if not cleaned:
        cleaned = "file"
    
    return cleaned


def format_timestamp(dt: Union[datetime, str, None], include_seconds: bool = False) -> str:
    """
    Format timestamp consistently across all apps.
    
    Format: M/D/YYYY H:MMP (no leading zeros, A/P suffix)
    Examples: "3/25/2025 7:35P", "10/16/2025 8:03A"
    
    Args:
        dt: datetime object, ISO string, or None
        include_seconds: If True, include seconds in output
        
    Returns:
        Formatted timestamp string, or empty string if dt is None
    """
    if dt is None:
        return ""
    
    # Convert string to datetime if needed
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except (ValueError, TypeError):
            return dt  # Return original if can't parse
    
    # Format date: M/D/YYYY
    date_str = f"{dt.month}/{dt.day}/{dt.year}"
    
    # Format time: H:MM[SS]P/A
    hour_12 = dt.hour % 12
    if hour_12 == 0:
        hour_12 = 12
    
    am_pm = "A" if dt.hour < 12 else "P"
    
    if include_seconds:
        time_str = f"{hour_12}:{dt.minute:02d}:{dt.second:02d}{am_pm}"
    else:
        time_str = f"{hour_12}:{dt.minute:02d}{am_pm}"
    
    return f"{date_str} {time_str}"


def get_app_version() -> str:
    """The application's version.

    Search order:
    1. Built: VERSION in the bundled data folder (sys._MEIPASS), where the specs
       put it, then beside the exe. Never the current directory, which may be
       another project's.
       From source: VERSION in the repo root (find_file's usual places).
    2. idt_core.__version__, which the release process keeps equal to VERSION

    About said "Version: 1.0.0" in every built copy (#415): the specs bundle
    VERSION into _MEIPASS, which find_file never searched, and the last resort
    was a made-up "1.0.0" rather than the version the code itself carries.
    """
    try:
        if getattr(sys, 'frozen', False):
            version_file = None
            for folder in (getattr(sys, '_MEIPASS', None), get_base_directory()):
                if folder and (Path(folder) / 'VERSION').is_file():
                    version_file = Path(folder) / 'VERSION'
                    break
        else:
            version_file = find_file('VERSION')
        if version_file:
            text = version_file.read_text(encoding='utf-8').strip()
            if text:
                return text
    except Exception:
        pass

    try:
        from idt_core import __version__
        return __version__
    except Exception:
        return "unknown"


# ==================== ACCESSIBLE LISTBOX COMPONENTS ====================

class AccessibleDescriptionListBox(wx.Accessible):
    """
    Custom accessible object for ListBox that provides full text to screen readers
    while allowing visual truncation in the ListBox display.
    
    This solves a key accessibility challenge: wxPython ListBox doesn't support
    different visual vs screen-reader text. This class overrides the accessibility
    API to announce full descriptions to screen readers while the ListBox displays
    truncated versions.
    
    Used by: DescriptionListBox (wrapper class below)
    """
    
    def __init__(self, listbox, descriptions_data):
        """
        Initialize accessible wrapper.
        
        Args:
            listbox: The wx.ListBox being wrapped
            descriptions_data: List of dicts with 'description' key + optional metadata
        """
        super().__init__()
        self.listbox = listbox
        self.descriptions_data = descriptions_data
    
    def GetName(self, childId):
        """Return full description text for screen readers"""
        if childId == wx.ACC_SELF:
            # A list can say what it is ("Viewer, all descriptions"); the
            # editor's keeps the name it has always had.
            return wx.ACC_OK, getattr(self.listbox, "accessible_name", None) or "Descriptions"

        # childId is 1-based for list items
        if childId > 0 and childId <= len(self.descriptions_data):
            idx = childId - 1
            entry = self.descriptions_data[idx]
            
            # Return full description text to screen reader
            full_text = entry.get('description', '')
            return wx.ACC_OK, full_text
        
        return wx.ACC_NOT_IMPLEMENTED, ""
    
    def GetValue(self, childId):
        """Return full description as value"""
        if childId > 0 and childId <= len(self.descriptions_data):
            idx = childId - 1
            return wx.ACC_OK, self.descriptions_data[idx].get('description', '')
        return wx.ACC_NOT_IMPLEMENTED, ""
    
    def GetDescription(self, childId):
        """Return full description"""
        if childId > 0 and childId <= len(self.descriptions_data):
            idx = childId - 1
            return wx.ACC_OK, self.descriptions_data[idx].get('description', '')
        return wx.ACC_NOT_IMPLEMENTED, ""


class DescriptionListBox(wx.ListBox):
    """
    Drop-in replacement for wx.ListBox that displays truncated text visually
    but provides full descriptions to screen readers.
    
    This is essential for any ListBox displaying long text (100+ characters).
    Visual truncation saves screen space, but full text must be available to
    assistive technology users via screen readers.
    
    Usage:
        # Create the listbox
        desc_list = DescriptionListBox(parent, name="Description list")
        
        # Load descriptions (each dict must have 'description' key)
        descriptions = [
            {'description': 'Long text here...', 'model': 'gpt4', ...},
            {'description': 'Another long text...', 'model': 'claude', ...},
        ]
        desc_list.LoadDescriptions(descriptions)
        
        # Later, get the full description for a selected item
        idx = desc_list.GetSelection()
        full_desc = desc_list.GetFullDescription(idx)
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize the accessible description listbox"""
        super().__init__(*args, **kwargs)
        self.descriptions_data = []
        self.custom_accessible = None

    def Clear(self):
        """Empty the list and what its accessible object reads (#423).

        Clearing only the visible items left the accessible object answering
        with the previous picture's descriptions for items no longer there.
        """
        super().Clear()
        self.descriptions_data = []
        if self.custom_accessible is not None:
            self.custom_accessible.descriptions_data = self.descriptions_data

    def Set(self, items, *args, **kwargs):
        """Plain strings (a chat's turns): the screen reader reads the items
        themselves, not descriptions left from the last LoadDescriptions."""
        super().Set(items, *args, **kwargs)
        self.descriptions_data = []
        if self.custom_accessible is not None:
            self.custom_accessible.descriptions_data = self.descriptions_data

    def LoadDescriptions(self, descriptions_list, truncate_at=100):
        """
        Load descriptions into the listbox with accessibility support.
        
        Args:
            descriptions_list: List of description dicts, each with:
                - 'description' (str): Full description text (100-500+ chars typical)
                - Other keys are optional metadata (model, prompt_style, etc.)
            truncate_at: Character count at which to truncate display (default: 100)
                        On macOS, truncation is disabled because wx.Accessible
                        doesn't work with VoiceOver - full text is needed for
                        screen reader accessibility.
        """
        self.Clear()
        self.descriptions_data = descriptions_list
        
        # Platform detection: macOS needs full text for VoiceOver accessibility
        # wx.Accessible only works on Windows
        is_macos = sys.platform == 'darwin'
        
        # Add items
        for entry in descriptions_list:
            description = entry.get('description', '')
            
            if is_macos:
                # macOS: No truncation - VoiceOver needs actual ListBox text
                # wx.Accessible doesn't work on macOS, so full text must be in the list
                display_text = description
            else:
                # Windows/Other: Truncate for visual display
                # wx.Accessible provides full text to screen readers
                display_text = (description[:truncate_at] + "..." 
                               if len(description) > truncate_at 
                               else description)
            
            self.Append(display_text)
        
        # Custom accessible for Windows screen readers. wx.Accessible is
        # Windows-only: on macOS constructing it raises NotImplementedError,
        # which wx swallowed in the caller's handler, silently skipping the
        # rest of display_image_info whenever a described image was selected.
        try:
            self.custom_accessible = AccessibleDescriptionListBox(self, self.descriptions_data)
            self.SetAccessible(self.custom_accessible)
        except (NotImplementedError, AttributeError):
            self.custom_accessible = None
    
    def GetFullDescription(self, index):
        """
        Get the full description dict for an item.
        
        Args:
            index: 0-based index of the item
            
        Returns:
            Dict with full 'description' and other metadata, or empty dict if invalid index
        """
        if 0 <= index < len(self.descriptions_data):
            return self.descriptions_data[index]
        return {}
