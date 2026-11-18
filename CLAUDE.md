# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Image Description Toolkit (IDT) is an AI-powered batch image/video description tool with three standalone applications:
- **`idt`** — CLI dispatcher (`cli/main.py`) routing to all sub-commands
- **`ImageDescriber`** — wxPython batch processing GUI (`imagedescriber/imagedescriber_wx.py`) with integrated viewer (`viewer_components.py`), chat (`chat_window_wx.py`), workspace manager (`workspace_manager.py`), prompt editor, and configuration manager
- **`IDT Chat`** — standalone accessible chat client (`chatapp/chat_app_wx.py`). Not an image tool; a general-purpose chat client for Ollama/Claude/OpenAI built for keyboard and screen reader use.

Also the repo's one non-Python project: **`windows_ai_helper/`**, a small packaged C# app that describes pictures with Windows' on-device model on Copilot+ PCs. Windows only lets a packaged app use that model, so IDT runs this helper rather than calling the API from Python. Its README covers the protocol, building, and what the package must declare. Built and tested by `.github/workflows/windows-ai-helper.yml`; its protocol tests run with `dotnet test windows_ai_helper/IdtWindowsAI.Tests`.

Supported AI providers: Ollama (local/cloud), OpenAI GPT-4o, Claude (Anthropic API), Claude Code (Claude on the user's subscription via the `claude` CLI, provider key `claude-code`), Apple Intelligence (on-device on macOS 27+, provider key `apple`), and MLX (macOS Apple Silicon, GUI only).

## Commands

### Testing
```bash
pytest pytest_tests/
python run_unit_tests.py        # Python 3.13-compatible alternative
pytest --cov=scripts pytest_tests/
pytest -m unit pytest_tests/   # markers: slow, integration, unit, regression
```

### Building (Windows)
```batch
BuildAndRelease\WinBuilds\builditall_wx.bat   # all three apps
cd idt && build_idt.bat                        # CLI only
cd imagedescriber && build_imagedescriber_wx.bat
cd chatapp && build_chatapp.bat
```

### Building (macOS)
```bash
./BuildAndRelease/MacBuilds/builditall_macos.command   # all three apps
cd imagedescriber && ./build_imagedescriber_wx.sh
cd chatapp && ./build_chatapp.sh
```

### Smoke Testing After Build
```bash
dist/idt/idt.exe version          # Windows: version, Python, exe path
dist/idt/idt.exe prompts          # reads the shipped config; lists the prompt styles
./dist/idt version            # macOS
```

### Syntax Validation
```bash
python -m py_compile <file>
```

## Architecture

### Dual Execution Model
All code must support both modes:
- **Development**: `python cli/main.py describe <folder>` (CLI), `python imagedescriber/imagedescriber_wx.py` (GUI)
- **Production**: PyInstaller frozen executables (`idt.exe describe <folder>`)
- **Detection**: `getattr(sys, 'frozen', False)`
- **Paths**: Always use `idt_core/config_loader.py` (`load_json_config`, `writable_config_path`), never raw `Path()` or `open()` for config files

### Core Pipeline (`idt_core/`, driven by `cli/main.py` and ImageDescriber)
`idt describe <folder>` runs these steps into one `.idtw` workspace bundle:
1. Scan the folder → `idt_core/scanner.py` (`scan_images`, `is_heic`)
2. Video frame extraction → `idt_core/video.py` (`extract_frames_to_dir`), into `<bundle>/derived/frames/`
3. HEIC conversion → `idt_core/converter.py` (`save_heic_copy`), into `<bundle>/derived/converted/`
4. EXIF and geocoding → `idt_core/metadata.py` (`MetadataExtractor`, `NominatimGeocoder`)
5. AI description → `idt_core/pipeline.py` (`WorkspacePipeline.run()`, a generator of events) and `idt_core/providers/`
6. HTML report → `idt_core/exporter.py` (`export_workspace_html`), into `<bundle>/reports/`

Workspaces: `idt_core/workspace.py`. A bundle is `<name>.idtw` under the workspace root (`~/Documents/idt` by default), holding `manifest.json`, `descriptions/` sidecars, `derived/`, `logs/`, `reports/`, and `images/` only when originals are copied. ImageDescriber converts its in-memory workspace to and from bundles through `idt_core/gui_bridge.py`. There are no `wf_*` folders any more.

### Configuration Resolution Order (`idt_core/config_loader.py`)
Two layers: the user's saved settings over the shipped defaults.
1. Explicit path from caller
2. File environment variable, when a caller passes one
3. **The user config dir** (`%APPDATA%\IDT`, `~/Library/Application Support/IDT`, `~/.config/IDT`; `IDT_USER_CONFIG_DIR` replaces it) — what Configure, the Prompt Editor and Import Configuration save
4. The shipped defaults: `IDT_CONFIG_DIR` → frozen exe dir `/scripts/` → `_MEIPASS/scripts/` → the repo's `scripts/` (from source) → cwd

`load_json_config` fills any top-level section the user copy lacks from the defaults (top level only, so deleted prompt styles stay deleted). Save with `writable_config_path()`, never to `scripts/` beside the exe: the installer replaces it on every upgrade. Before #407 the exe's `scripts/` came first, so nothing saved in Configure reached processing on an installed Windows copy. The test suite points `IDT_USER_CONFIG_DIR` at scratch and clears `IDT_CONFIG_DIR`.

### AI Model Registry (Single Source of Truth)
All model lists live in the provider modules under `idt_core/providers/`:
- `idt_core/providers/claude.py` — Claude model list and metadata (sourced from Anthropic SDK)
- `idt_core/providers/openai_provider.py` — OpenAI model list and metadata (sourced from OpenAI SDK)
- `idt_core/providers/ollama.py` — Ollama models are dynamic (queries the running Ollama service at runtime)
- `idt_core/providers/claude_code.py` — Claude Code provider: runs `claude -p` per request, billed to the user's subscription. Refuses to run unless `claude auth status` reports a claude.ai login, and strips `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_BASE_URL` from the child. Never use `--bare` there (bare mode is API-key only). Chat side: `idt_core/chat/claude_code.py`.
- `idt_core/providers/apple.py` — Apple Intelligence provider: starts one `fm serve` per process on a Unix socket under `/tmp` and kills it at exit. The endpoint is OpenAI-shaped but diverges in three ways, two of them silent — `stream` defaults to **true** (omitting it returns an event stream a JSON caller cannot parse), `max_tokens` is ignored so length control must use `max_completion_tokens`, and requests serialize server-side so batches gain nothing from parallelism. Gated on a machine-wide `sudo fm license`, which the user must run; `fm models` exits non-zero on a licensed Mac (because `pcc` is unavailable), so never read its exit code. Chat side: `idt_core/chat/apple.py`.
- `idt_core/providers/registry.py` — **provider capabilities** (streaming, system prompt, attachment MIME types, API key requirement). Replaced the deleted `models/provider_configs.py`.

Imported by CLI, GUI, and chat features. Never duplicate model lists elsewhere.

### Chat Engine (`idt_core/chat/`)
Provider-agnostic and **wx-free**. Backs `idt chat`, the standalone IDT Chat app, and eventually ImageDescriber's chat window.

- `ChatEngine.send()` is a **generator of events**, matching `WorkspacePipeline.run()`. Callers decide output.
- Cancellation is `gen.close()` — `GeneratorExit` reaches the provider's `finally`, which closes the stream. Partial responses are always persisted.
- API keys resolve through `idt_core/keys.py` only. Do not add a sixth lookup.
- `ChatSession.context_tokens` (last exchange) and `billed_tokens` (sum) are different numbers — do not conflate them.

**There is exactly one chat implementation.** `ChatProcessingWorker` (~690 lines of inline SDK calls in `workers_wx.py`) was deleted in August 2026. All three surfaces reach the engine through `shared/chat_worker_wx.py`, which marshals events onto the wx UI thread with a `weakref` to the window.

ImageDescriber keeps its own persistence: chat turns are still `ImageDescription` objects on a chat `ImageItem`, so existing `.idtw` workspaces load unchanged. The engine is constructed with `store=None` there.

### Key Shared Utilities
- `idt_core/workspace.py` — `Workspace` (open/create a bundle, items, `status()`), `WorkspaceDefaults`
- `idt_core/metadata.py` — `MetadataExtractor` (EXIF date priority order), `prompt_context()` vs `display_context()`
- `idt_core/keys.py` — the one API key lookup
- `imagedescriber/workspace_manager.py` — `get_default_workspaces_root()`, `sanitize_workspace_name()`
- `shared/wx_common.py` — wxPython helpers
- `shared/utility_functions.py` — `sanitize_name()`, `sanitize_filename()` for filesystem-safe names
- `scripts/` now holds only the three shipped default config JSON files

## Critical Rules

### PyInstaller Frozen Mode Imports
`from scripts.X`, `from imagedescriber.X`, `from analysis.X` **always fail in frozen mode**. Use:
```python
# At module level — NOT inside functions
try:
    from config_loader import load_json_config   # frozen mode
except ImportError:
    from scripts.config_loader import load_json_config  # dev mode
```

### wx Silent Failures
wxPython **swallows all exceptions** in event handlers. When a button/menu/handler silently does nothing, run in dev mode first:
```bash
cd imagedescriber && .winenv/Scripts/python imagedescriber_wx.py   # Windows
cd imagedescriber && python imagedescriber_wx.py                    # macOS
```
Reproduce the action — the exception prints to stderr immediately. Do not investigate architecture before doing this.

**Instructive example (8 hours wasted, April 2026):** A commit moved `logger = logging.getLogger(__name__)` from module scope into `main()`. Every event handler calling `logger.info(...)` silently raised `NameError`. `on_close`, `on_process_single`, and all other handlers appeared to do nothing; Alt+F4 was broken. Fix: 1 line. Discovery time in dev mode: under 30 seconds.

### Before Any Code Change
1. `grep -r "name"` to find ALL usages before renaming/changing signatures
2. Check all callers — incomplete refactors caused 23% of commits to be bug fixes
3. Verify PyInstaller compatibility with try/except import pattern
4. Functions >500 lines require extra scrutiny

### After Core File Changes
For changes to `cli/main.py`, `idt_core/pipeline.py`, `idt_core/workspace.py`, or any file listed in `hiddenimports` in the per-app `.spec` files (e.g., `imagedescriber/imagedescriber_wx.spec`, `idt/idt.spec`):
1. `python -m py_compile <file>`
2. Build the exe
3. Run with test data: `dist\idt\idt.exe describe testimages --limit 2` (creates `Documents\idt\testimages.idtw`)
4. Check `<bundle>.idtw/logs/*.log` for errors
5. Only then claim the fix is complete

### When Something Regresses
1. `git log v<tag>..HEAD --oneline -- <file>` to find the breaking commit
2. Run in dev mode, reproduce, read the exception
3. Only then look at architecture

## Conventions

### Virtual Environment
Windows virtual env uses `.winenv` (dot prefix), not `winenv`:
```batch
call .winenv\Scripts\activate.bat   ✓
call winenv\Scripts\activate.bat    ✗
```

### Date/Time Format
`M/D/YYYY H:MMP` — no leading zeros, A/P suffix. Examples: `3/25/2025 7:35P`, `10/16/2025 8:03A`.

EXIF priority: `DateTimeOriginal` > `DateTimeDigitized` > `DateTime` > file mtime.

### Window Titles
Always show stats: `"XX%, X of Y images described"`. Live mode adds `"(Live)"` suffix.

### Accessibility (WCAG 2.2 AA)
- Use `wx.ListBox` instead of `wx.ListCtrl` (single tab stop)
- Set `name=` parameter in widget constructors for screen reader labels
- `wx.ListBox` items: concatenate data into single strings (no multi-column)

### Session Summaries
Create `docs/WorkTracking/YYYY-MM-DD-session-summary.md` for non-trivial sessions. Include: files changed, decisions, test results, what was NOT tested.

## Additional Reference
- `docs/KEYBOARD_SHORTCUTS.md` — every accelerator and Alt mnemonic in both GUIs, Windows and macOS, plus the rules a new one must clear
- `docs/DEVELOPER_GUIDE.md` — comprehensive developer guide (architecture, `idt_core` inventory, CLI commands, build system, testing, conventions)
- `.github/copilot-instructions.md` — full agent guidelines and protocols
- `docs/WorkTracking/PRE_COMMIT_VERIFICATION_CHECKLIST.md` — pre-commit checklist
- `BuildAndRelease/BUILD_SYSTEM_REFERENCE.md` — build troubleshooting
