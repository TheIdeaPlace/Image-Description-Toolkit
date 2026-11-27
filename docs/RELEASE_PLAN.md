# IDT release plan: 4.9.0 to 5.0

Written 11/20/2026 against origin/main at 6e46b55 (4.9.0 published that day). 95 open issues
read, with comments. Read-only: no issue or PR was changed.

The idea for every release: one theme, a few areas of the app, a list of what to listen to,
and the same 10-minute smoke check. Anything not in a release's areas doesn't get retested
by ear.

"Unverified" means I couldn't confirm it from the code or history.

---

## 1. Already fixed or no longer relevant (close candidates)

### Fixed

| Issue | Evidence |
|---|---|
| #39 Claude 5 MB image limit | `converter.fit_image(max_bytes, max_side)` (`idt_core/converter.py:118`). Commit ce76eb9 (#487) fits pictures to Claude's limits in ImageDescriber, idt and chat. |
| #49 image retention / copies | Originals are referenced unless `copy_originals` is set (`workspace.py:708`), and there are no `wf_*` copies. |
| #58 user guide install section | `docs/USER_GUIDE.md:72-90` covers the installer first. |
| #63 custom config in the GUI | Settings go through `config_loader` and the user config dir, and there's Tools > Import Configuration (`imagedescriber_wx.py:10257`). |
| #70 IDT_CONFIG_DIR confusion | The user dir now outranks `IDT_CONFIG_DIR` (`config_loader.py:105-113`, #407), and the installer removes an old `IDT_CONFIG_DIR` (`installer.iss:194-202`). |
| #71 Viewer extra tab stop | e8b3f5a (#491): no Tab stop on the picture panel. |
| #91 OpenAI empty descriptions saved | `empty_answer_error` raises (`openai_provider.py:272, 545`); the GUI worker treats a still-empty answer as a failure (`workers_wx.py:689-748`). |
| #92 model parameter constraints | `idt_core/generation.py` (#392) drops a field the model can't take instead of sending it. |
| #95 Configure tabs in tab order | 14bc6fb (#401). |
| #97 Mac build in GitHub Actions | `build-macos.yml` builds, signs and notarizes, and Mac releases ship from it. |
| #107 image list as a tree | 6d9fc7ef converted it to `wx.TreeCtrl`, with a DataView adapter on macOS. |
| #223 dynamic model management | Live Claude and OpenAI lists (`claude.list_models_live`, `claude.py:212`) merged with the curated catalog (#267, 4.5.1). |
| #224 signed builds and release workflow | `release.yml` has published 4.7.0, 4.8.0, 4.8.1 and 4.9.0. |
| #230 follow-ups | Item 1 is done (#231). Item 3 is done: providers raise `ProviderError` (`raise_provider_error`, `ai_providers.py:524-560`; PR #234). Item 2 (branch protection) was recorded as "won't do". Items 4 and 5 are standing advice, which the coverage-floor ratchet already covers. |

### Obsolete (the code it describes is gone)

| Issue | Why |
|---|---|
| #10 alternative view | There's no such view in the wx View menu. |
| #12 Alt+Enter for Properties | There's no Properties command in the wx app (unverified). Refile as a feature if it's wanted. |
| #28 model performance analyzer | `Tests/` and `analysis/` are gone. |
| #31 list navigation performance | Written about the Qt list. The wx tree replaced it. Speed under wx is unverified. |
| #48 flat view | There's no flat view in wx. |
| #51 "unknown" prompt in combine | `combine` reads `prompt_name` from description sidecars and no longer parses `wf_` folder names. |
| #59 model "unknown" in the workflow path | Workflow paths and `wf_*` folders are gone. |
| #66 git history force push | About 2025 branches. |
| #67, #68, #69 chat test plans | `ChatProcessingWorker` was deleted. Chat goes through `idt_core/chat` now. |

### Close with a note

- **#22 Copilot+ / Windows AI:** delivered as the Windows AI provider in 4.8.0. The ONNX and LLaVA ideas in it are stale.
- **#201 frozen-mode checks for 4.5:** five signed releases have shipped since. Re-test `--showgui` once as part of #468, then close.
- **#14 unsaved prompt on a fresh load:** probably fixed. `modified=False` at start (`wx_common.py:410`), and `confirm_unsaved_changes` returns early (`:477`). Claude should confirm it in the VM, then close.
- **#62 config tests:** `test_settings_reach_processing.py` (19 tests, real fixtures) now covers what mattered. Close, or retitle as "resolution-order suite for config_loader".
- **#76 testing strategy:** superseded by the CI in place and by section 6 of this plan.

---

## 2. 4.9.1: what 4.9.0 left broken or confusing

**Theme:** ImageDescriber says when things finish, puts focus where you expect, and the
HTML report reads cleanly.

**Areas:** batch window, chat window, IDT Chat app, Editor (focus after opening),
exports/reports (HTML only), dialogs/Configure (one Ctrl+Tab fix, one Gallery fix).

| # | Item | Size | Notes |
|---|---|---|---|
| 1 | **#409** batch completion is announced | S | On PR #438. Doesn't need the DLL: it moves focus to the completion window. NVDA heard "Batch Complete … 3/3 images" in the VM (out/pr438-nvda-check.md). |
| 2 | ~~**#410** ImageDescriber chat replies are read~~ | moved out | Decided 11/27/2026: not in 4.9.1. Waits on the NVDA DLL. |
| 3 | ~~**#439** IDT Chat replies under NVDA~~ | moved out | As #410. |
| 4 | **#493** focus on the image tree after Ctrl+O | S | Still open. `load_workspace` (`imagedescriber_wx.py:5539`) has no `_focus_current_mode` call, unlike every other path. The fix is the one in the issue: `wx.CallAfter(self._focus_current_mode)` at the end, plus a test spying on SetFocus. Repro (Ctrl+O through the real dialog, cold open with the progress window) to be done in the VM first. |
| 5 | **#422 (rest)** Ctrl+Tab reads a tab's first item twice | S, unknown cause | Plain names and the single title shipped in 4.9.0 (#505). Needs an NVDA speech capture in the VM before any code changes. If no cause is found in a session, move it to 4.12 rather than hold the release. |
| 6 | **#465 (rest)** Markdown shown literally in HTML | S–M | See below. |
| 7 | **#438 as its own item: the NVDA controller DLL** | decision | See below. |
| 8 | **#428** Gallery dialog reads all four style descriptions on opening | S | Cause found: `ExportHtmlGalleryDialog` (`dialogs_wx.py:1713`) puts a `StaticText` hint beside every radio button (`:81`), so all four are read on opening. Keep only the tooltip or accessible description, and show the selected style's text in one field. It belongs here because 4.9.1 already touches exports. |
| 9 | **OpenAI's 12/11/2026 shutdowns** (#514) | S, **date-driven** | Added 11/26/2026. OpenAI ends API access to GPT-5, GPT-5 mini, GPT-5 nano, GPT-5 pro, o3 and o3-pro on 12/11/2026. #514 retires the four IDT offered (the pro models never were) and says "OpenAI has shut down …" when one still chosen fails. The default, GPT-6 Luna, isn't affected. This gives 4.9.1 a deadline: ship by 12/10, or 4.9.0 keeps offering four models that stop working while it's installed. |
| 10 | **Already on main (#511):** Apple refusal fallback, OneDrive-safe workspaces | done | Merged 11/23/2026. A photo Apple's guardrails decline is retried with technical, then artistic. A briefly missing manifest is waited for, never recreated. Run logs survive OneDrive replacing the file. Only needs the smoke check by ear. |

**The 4.9.1 label is right on all six issues** (#409, #410, #422, #439, #465, #493). None
should move. #422 and #465 are only the leftovers after 4.9.0's partial fixes.

### #465: Markdown, and whether ImageDescriber shows it literally too

Nothing in IDT renders or strips Markdown, except speech (`strip_for_speech`,
`shared/speech_engine.py:264`). No prompt asks for plain text, and no Markdown library is
a dependency.

| Surface | How it shows text | Markdown literal? |
|---|---|---|
| HTML report (`exporter.py:406-407`) | escaped, `\n` turned into `<br>` | yes |
| Legacy `.idt` HTML (`exporter.py:191,204`) | escaped figcaption | yes |
| ImageDescriber Export HTML (`imagedescriber_wx.py:6616`) | same as the report | yes |
| Gallery, all four styles (`gallery_exporter.py:231-251`) | escaped `<p>` | yes |
| TXT and CSV exports, `combine`, `show`, `--quiet` output | raw | yes (fine for raw data) |
| Embed into EXIF | raw | yes (stored as written; leave it) |
| ImageDescriber editor (`imagedescriber_wx.py:1617`) | plain TextCtrl | yes (right for an editor) |
| Description list (`AccessibleDescriptionListBox`) | raw, spoken in full | **yes**, read aloud as "#", "**", "-" |
| Viewer mode (`viewer_components.py:302, 683`) | read-only TextCtrl | **yes** |
| Chat history and Selected message (both apps) | raw | yes (chat answers are Markdown by nature) |

**For 4.9.1:** a wx-free helper, `markdown_to_safe_html()`, that escapes first and then
turns a small subset into tags: headings demoted to `<p><strong>` so they don't break the
report's h1–h4 outline, bold and italic, lists, and paragraphs. No new dependency
(Python-Markdown passes raw HTML through, so it's unsafe without a sanitizer). It changes
four call sites: `exporter.py:204` and `:406`, `gallery_exporter.py:238/248`, and
`imagedescriber_wx.py:6616`. Tests: escaping (a `<script>` in a description stays text),
each construct, and the heading levels.

**Not in 4.9.1 (decision 3):** `strip_markdown()` for the Viewer, the description list and
the TXT exports. It changes what's read in the main lists, so it gets its own listening
pass in 4.10.

**Optional, cheap:** add "plain prose, no Markdown headings or lists" to the shipped
prompts. That doesn't fix existing descriptions, so it's in addition to the above, not
instead of it.

### #438 and the DLL

- **What's on the PR:** `shared/uia_notify.py` plus NV Access's `nvdaControllerClient.dll`
  (x64 and arm64, LGPL 2.1, unmodified, with the license file) in both specs.
- **Why the DLL:** NVDA ignores UIA notifications from wx windows. That was measured: the
  notification was accepted and nothing was spoken. The controller client spoke the whole
  reply once, with focus left in place.
  - The fallback, the focus bounce, is cut off by NVDA when focus returns to the message
    box, so a long reply is lost.
  - JAWS gets the UIA notification. Whether JAWS speaks one from a wx window is **not yet
    checked by ear**.
- **IDT Chat's Speech setting already uses the same DLL** (`shared/speech/speak-engine.ps1:72-110`),
  but it only finds a copy on disk, and NVDA's installer doesn't put one there (the script
  says so at line 13). So in practice that route works almost nowhere today.
- **The PR now conflicts with main.** #414, #421, #427, #475 and #412 went into 4.9.0 as
  #506. The branch needs rebuilding as #409 + #410 + #439 only.
- **Options:**
  - **(a) Ship the DLL.** This is the only route measured to work with NVDA. LGPL is
    satisfied by shipping it unmodified, with its license and a source pointer, and
    loading it dynamically, which `ctypes.WinDLL` does.
  - **(b) Ship without it.** #409 works; #410 and #439 stay as the clipped focus bounce
    under NVDA.
  - **(c) Split it:** ship #409 now, and #410 and #439 when the DLL is decided.
- **Recommendation: (a),** with the DLL's license added to the installer's third-party
  notices, and a CI step that checks the DLL is present in the frozen build (`dist/.../shared/nvda/<arch>`).

### 4.9.1 test plan

- **Claude, before Kelly listens:**
  - the installed CI build in the VM;
  - the NVDA speech capture of bug bash flows 02 (describe a folder) and 05 (chat), plus
    IDT Chat's send;
  - Ctrl+O through the dialog, cold and warm;
  - an HTML report and a gallery from a Claude workspace with Markdown, checked in
    NVDA browse mode (headings list, no "number sign" read);
  - that the DLL loads from the installed folder.
- **Kelly, by ear, JAWS then NVDA, about 15 minutes:**
  1. Run a batch to the end: you should hear "Batch Complete" and the summary.
  2. Escape: focus should be on the image tree.
  3. (Not in 4.9.1: chat replies stay on the focus bounce until the DLL is decided.)
  4. Press Enter while a reply is pending: you should hear "Still waiting…".
  5. Send one message in IDT Chat.
  6. Ctrl+O a large workspace: focus should land on the tree.
  7. Ctrl+Tab through Configure: no item read twice.
  8. Open the Gallery dialog: it should open on the style choice.
  9. Open the HTML report: headings and lists should read as such.
  10. With an OpenAI key: the OpenAI model list in Configure has no GPT-5, GPT-5 Mini, GPT-5 Nano or O3.
- Plus the smoke checklist (section 6).

---

## 3. Releases after 4.9.1

Planned order. Each is one focused session plus Claude's VM validation, and touches two or
three areas.

### 4.9.2: the command line tells the truth (bug fixes only)

**Theme:** CLI output, exit status and messages match what happened.

**Areas:** CLI, exports/reports (CLI side only). No GUI change, so there's almost nothing
to hear.

| Issue | Size | Note |
|---|---|---|
| #458 stdin workspace name; stdin ignores `--limit/--embed/--show-descriptions` | S | `cli/main.py:1395-1404` uses `startswith`; switch to `os.path.commonpath` |
| #459 `--workspace .\relws` lands in the root | S | `cli/main.py:606, 639` |
| #461 `idt watch --quiet` not flushed | S | `:2720-2730`; the stdin `--quiet` print at `:1374` too |
| #466 `idt models` with Ollama absent says ok | S | `ollama.py:610-613` swallows the error |
| #470 `status --all --json` row shape | S | `:1744` against `:1693` |
| #471 raw WinError on an unreachable share | S | `:1784` |
| #472 chat defaults to Ollama; empty reply exits 0; Windows-AI error | S–M | `:2558`, `:2505`, `:3518`. The `--think` help is already fixed. |
| #473 "referenced originals" counts frames | S | `:902-914` |
| #462 combine TSV/CSV newlines | S | `:2134` |
| #463 `combine --sort date` ignores the EXIF date | S | `:2176` |
| #464 CSV one row per picture; `anthropic` against `claude` | S–M | Normalise the provider name at write time (`exporter.py:448`, `cli/main.py:2136`) |

**Why here:** all are verified and small, they're confined to `cli/main.py`, `exporter.py`
and `ollama.py`, and they're tested by unit tests plus a frozen `idt.exe` run. Cheapest
release to verify. #464 needs decision 4.

### 4.10: plain text where people read, and video frames that stay put

**Theme:** what you read in the lists and exports is clean, and a workspace's frames are
right after re-extracting or moving it.

**Areas:** describe pipeline, video, Viewer, Editor (description list), exports/reports (TXT).

| Issue | Size | Note |
|---|---|---|
| #465 follow-up: `strip_markdown()` in the Viewer, the description list labels and TXT exports | S | Only if decision 3 says yes |
| #474 near-empty Ollama answer saved as success; leading newline | S | `ollama.py:551-583`. Part of "clean text". |
| #5 frames described out of time order | S | `workspace.items()` sorts as text (`workspace.py:771`), so `_10.00s` comes before `_5.00s`; also `gui_bridge.py:470` |
| #373 a moved `.idtw` re-adds its frames | M | Match frames relative to `derived/` (`workspace.py:633-682`) |
| #460 re-extracting with other options adds frames | M | Shares the re-registration fix with #373 |

**Why here:** #373 and #460 are one change to frame registration. #5 sits on the same
path. Text cleanup is user-visible in the two lists, so it needs one listening pass, and
pairing it with a pipeline release keeps the GUI areas to two.

### 4.11: provider answers you can trust

**Theme:** a model that can't give a real answer says so instead of saving something bad.

**Areas:** providers, describe pipeline, Mac (MLX).

| Issue | Size | Note |
|---|---|---|
| #399 thinking model fills Ollama's small context | M | Set `num_ctx` for describe (reuse `chat/providers.py:224-265`) and diagnose instead of retrying |
| #430 two fallback default models | S | `llama3.2-vision` at `config.py:48-62`, `ollama.py:24`, `workspace.py:36`, `imagedescriber_wx.py:4017, 4218`. Use one constant (decision 5). |
| #369 IDT-side guard for Windows AI corruption | S–M | Detect a digit run inside a word or a runaway repeat, then retry with Detailed or flag it. The Microsoft bug is upstream (WindowsAppSDK#6852). Needs Kelly's Copilot+ PC for a short run. |
| #102 MLX wall-clock timeout | M | Mac only. Needs a subprocess to be real (see the issue). |
| #337 lengthen `aialttext`/`simple` for Apple refusals | S | Prompt text only, measured against the two known-refusing photos on the Mac |
| #324 remaining model-list items | S | Largely done in 4.9.0 (#445, #453). Check what's left, then close. |

**Why here:** everything is in `idt_core/providers` plus the prompt config. Little to hear:
error wording in two message boxes. Kept after 4.10 so prompt changes don't collide with
the text-cleanup work.

**Unverified:** whether the Ollama pickers already filter out non-vision models (#225 §6).
`model_capabilities()` exists (`ollama.py:164`). Check before planning work on it.

### 4.12: ImageDescriber dialogs and settings say what they do

**Theme:** every dialog reads cleanly, and no setting is dead.

**Areas:** dialogs/Configure, Editor.

| Issue | Size | Note |
|---|---|---|
| #420 Download dialog reads "×" and stray fragments | S | `download_dialog.py:75, 123-124`, still present |
| #433 Workflow Settings tab does nothing; `include_location_prefix` unread | S | `configure_dialog.py:978, 1010`. Remove the tab (decision 6). |
| #357 Configure opens before the model refresh lands | S–M | `imagedescriber_wx.py:9977-9979` |
| #84 image preview setting not remembered | S | `imagedescriber_wx.py:786` |
| #384 leftovers | S | Prefix codes run together ("d2E5", `imagedescriber_wx.py:3399`; spacing only, since the codes are by design); emoji in "⏳ Status" (`batch_progress_dialog.py:477`) and "⚠️ Processing Failed" (`imagedescriber_wx.py:2263`); `crash_log.txt` in the working directory (`:11049`); IDT Chat announce policy not saved (`chat_app_wx.py:772`) |
| #8 paste doesn't start processing | S | Behaviour change (decision 7) |

**Why here:** all are dialog and settings polish, heard in one pass through Configure,
Download and the View menu. None blocks anything earlier.

**If time is short before 5.0,** fold 4.12 into a 5.0.1 instead.

**Realism note:** that's 4.9.1 through 4.12 (five releases) plus 5.0 in about six weeks. At
one release a week that's possible for 4.9.x and 4.10. It's tight if each needs a VM pass
and Kelly's listening. If 5.0 must land by 12/31, drop 4.12 into 5.0.x and keep 5.0 small
(see below).

---

## 4. 5.0

5.0 should be about one thing users notice: **how IDT is installed and updated.** That's
the one change that touches install location and behaviour people rely on. Everything else
below is big or needs design, and can be 5.x.

| Item | Why it waits / what it needs |
|---|---|
| **#238 Velopack** + **#377 App Kit baseline** (updater, Report a Bug, crash handler, version in one place) + **#53** install location + **#384** version in three places | Moves the install from `C:\idt` (Inno, admin) to per-user `%LocalAppData%`. Needs a migration for 4.x installs, the PATH option and the winget Ollama step redone, and the Windows AI helper's MSIX registration re-checked. GHManage and QuickMail are the working references. L. Changes behaviour users rely on, so it's a major version. |
| **#239** macOS update beyond "here is a DMG" | Same theme, Mac side. 6e46b55 (#508) added a quit-and-reopen notice. A `.pkg` or in-place replace is M–L and needs a real Mac. |
| **#442** Windows App SDK 1.8 to 2.6 | Builds fail because Dependabot bumped Runtime/Base to 2.6.5 but left `Microsoft.WindowsAppSDK.AI` at 1.8.79 (`ComponentReference.targets: expected 2.6.5, but 1.8.79 was referenced`). It needs the AI package moved to a matching 2.x, a check that users' Windows App Runtime gets the 2.x framework, and a short run on the Copilot+ PC. It belongs with 5.0's installer work, since the helper's install changes anyway. Until then, close #442 and add a Dependabot ignore for major versions of that group. |
| **#398** Codex provider | New provider, about the size of claude-code (~1,800 lines / 31 files for #325). Open questions on plan limits, sign-in expiry mid-batch and OpenAI's terms. 5.x, after 5.0. |
| **#469** custom prompts shared between CLI and GUI | Design: one prompt store for `~/.idt/config.json` and ImageDescriber's settings, and which wins. Changes where user prompts live. 5.0 if it falls out of the config moves, otherwise 5.x. |
| **#202** retire the legacy `.idt` Project reader and the old `Pipeline` | Drops read support for pre-4.5 projects. A format change, so it fits a major version. M. |
| **#79** one video extraction implementation | Three copies remain (`imagedescriber_wx.py:1230/1283`, `workers_wx.py:1791-1962`, `idt_core/video.py`). Refactor, M–L. Wants the 4.10 frame fixes first. |
| **#226** keep or drop the bundled MLX provider | Product call: must "DMG only, no other install" on-device stay true? Plus a benchmark. Decides #125 and #102's future. |
| **#270** web search for Claude chat (server-side) | M: `pause_turn`, result-block shapes, citations, cost notice. OpenAI deliberately left out. 5.x. |
| **#268** IDT Chat follow-ups | Several M items (settings dialog, rename, search, context gauge, BMP/TIFF, PDF for Ollama). 5.x. |
| **#78 / #90** remove items from a workspace, Delete key | New command with confirmation, plus bundle cleanup. M. 5.x. |
| **#177** workspace cleanup command | Needs a design for what's safe to delete. M. 5.x. |

---

## 5. Later or won't do

| Issue | Recommendation | Reason |
|---|---|---|
| #13 standard folder picker for Load Directory | Later; ask Kelly | The custom dialog carries the recursive option. Changing it is a UX call. |
| #15 Details view | Won't do as written | The single-string tree rows are deliberate (one tab stop, read as one line). The Properties/details already read in the description list. |
| #41 guideme arrow keys | Won't do | Numbered input is the screen-reader-friendly choice, as the issue itself says. |
| #50 `idt describe photo.jpg` | Later (5.x) | Real gap (`cli/main.py:824-826`), but stdin describe (`describe -`) covers one file today. |
| #72 model descriptions and prices in pickers | Later | Names shipped (#448). Prices in a combo box are long to hear. |
| #83 auto-announce batch counts | Close once #409 ships | The title now carries progress (#412), and completion is announced. A per-image chatter setting is optional. |
| #87 Ollama window left open by the installer | Fold into 5.0 | The Velopack rework replaces that installer step. |
| #88 GPS "City, Country" | Later; small | `metadata.py:67-68`. Needs a format decision. |
| #93 Claude system prompt, Batches/Files APIs | Later | The rest of #93 is fixed. Batches is a 50% cost saving but an architecture change. |
| #103 VoiceOver jump-to-top in lists | Later, Mac | wx accessibility bridge limitation; investigation only. |
| #104 Apple Photos import | Later | Entitlements and Full Disk Access. |
| #123 gallery client-side switching | Later | Enhancement, M–L. |
| #124 skip Live Photo companion videos | 5.x | Small, opt-in, but a new option across CLI and GUI. |
| #125 MLX models from config | Waits on #226 | Partly done (`mlx_extra_models`). |
| #225 gemma4 hallucination | Close | Not an IDT defect. The camera-in-prompt bug was fixed (5ef6f07). Confirm the vision filter, then close. |

---

## 6. Testing approach, every release from here on

### 6.1 What automated tests cover now

There are about 125 test files and about 2,700 tests. The wx tests build real, usually
hidden, windows and skip unless `IDT_REQUIRE_WX=1`.

| Area | Covered by | Kind | Gaps |
|---|---|---|---|
| CLI | test_cli_bugbash_490 (50), test_cli_models_command (32), test_cli_provider_defaults (35), smoke/test_entry_points | logic, `--help` subprocesses | no `combine` test file; `guide.py` is 0% |
| Describe pipeline | test_idt_core (74), test_workspace_pipeline_halt (46), test_workspace_bundle, test_image_side_limit, test_exif_* | logic, temp bundles | scanner and converter only indirectly |
| Providers | ~20 files: apple (45), windows_ai (56+17), provider_options (56), generation_options (61), key_check, retry_contract, model_catalog… plus a stub HTTP server integration test | mocked SDKs | no real describe call (by design) |
| Editor | test_gui_smoke, test_editor_shown_description, test_list_relabel, test_open_workspace_wx, test_mode_switch_focus, test_menu_shortcuts, test_mnemonics, window_title_builder | wx frames; menus by AST | the image tree's accessible name isn't asserted; no focus test for Ctrl+O |
| Viewer | test_viewer_order, test_viewer_menu_target | hidden frame | no name, focus or announcement checks; 23% floor |
| Batch window | test_batch_stop_restart (120), test_batch_window_summary, test_batch_checkpoint, test_cost_meter_every_batch… | wx dialog driven | title text checked; completion focus only on PR #438 |
| Dialogs / Configure | test_configure_dialog_keyboard, number_validation, api_keys_wx, prompt_editor_names, generation_ui, settings_reach_processing… | wx dialogs | **Gallery dialog: no tests.** Download dialog: number fields only. |
| Chat window | test_chat_settings_focus, test_save_chats_in_saved_workspace | wx | nothing checks that a reply is announced |
| IDT Chat | test_chat_app_smoke (36), chat engine and providers (100+), gui/test_alt_mnemonics_windows, test_mac_accessibility | wx + logic | the best accessibility checks in the repo (names, labels, Alt collisions) |
| Exports | test_gallery_exporter (3), test_usage_line_outside, test_stats_every_description | logic | thin on gallery and HTML structure |
| Video | test_video_frames_folder (24), test_play_video | logic + wx | no GUI extraction dialog tests |
| Windows AI helper | IdtWindowsAI.Tests (27) | dotnet protocol and server | no real model (needs the NPU) |
| Mac | build-macos runs unit + gui with wx; test-macos | logic, Cocoa in process | MLX untested by design |
| Installer / updater | test_updater (37), spec and .bat checks | static | nothing installs the installer |
| Docs | axe WCAG 2.2 AA on generated HTML (publish-docs.yml) | | |

### CI

| Workflow | What it runs |
|---|---|
| coverage.yml (Windows) | the only full Windows suite, with wx, and the floors |
| build-macos.yml | unit + gui with wx, frozen `idt --help` per command, signing, DMG |
| test-macos.yml | full suite; `IDT_REQUIRE_WX` not set, so wx tests may skip (unverified) |
| cli-validation.yml | the required check: py_compile and `--help` from source |
| integration-test-windows.yml | builds, installs Ollama, then frozen `idt describe testimages`, checks the bundle and report, and that ImageDescriber.exe and IDTChat.exe stay up 15 s. From `dist`, not the installer. |
| build-windows.yml | build, sign, installer; no tests |
| windows-ai-helper.yml | dotnet tests |
| release.yml | tag; version and notes checks; both builds; publish |
| codeql.yml, model-prices.yml, publish-docs.yml | as named |

**Not covered anywhere in CI:** running the installer, any GUI test against the frozen app,
and anything a screen reader says. `integration/test_frozen_executable.py` looks for
`dist/idt.exe`, an old path, so it probably always skips (unverified). There's no `gui`
pytest marker, so window-opening tests can only be excluded by path or by not having wx.

### 6.2 What only a person can check

- How it sounds: verbosity, order, whether something is read twice or cut off. A speech
  capture shows the words, not whether they're pleasant to hear.
- JAWS: no automation exists for JAWS speech, so every JAWS result is by ear. JAWS and UIA
  notifications from wx windows are still unknown (#410).
- Whether a flow feels right: where focus lands "makes sense", whether a message is
  needed.
- Anything on the Copilot+ NPU (Windows AI) or a real Mac with VoiceOver.

### 6.3 Fixed smoke checklist (about 10 minutes, every release, JAWS; NVDA when announcements changed)

On the installed build from the release's folder:

1. **Install over the previous version.** It launches, and Help > About says the new
   version.
2. **Ctrl+O a saved workspace.** You hear the title with "XX%, X of Y images described",
   and focus is on the image tree.
3. **Arrow down three pictures.** Each row is read once, with its status prefix.
4. **Tab to the description list, then the editor.** You hear one description, no blank
   first line.
5. **Switch to Viewer mode and back (the mode keys).** Each switch is announced, and focus
   is in the new view.
6. **Press P on an undescribed picture** (Ollama). It's described, and focus doesn't jump.
7. **Process Undescribed on 3 pictures.** The batch window title shows progress, and you
   hear "Batch Complete" at the end. Escape returns to the tree.
8. **Ctrl+T, ask one question.** You hear the reply.
9. **Open Configure (Ctrl+Shift+C) and close it.** It's read as one short title, with plain
   setting names.
10. **IDT Chat: send one message.** You hear the reply.
11. **In a terminal: `idt version` and `idt describe testimages --limit 1`.** It exits 0,
    and the report opens in a browser with headings.

### 6.4 Per-area listening list (only when that area changed)

| Area | Listen for |
|---|---|
| Editor | tree rows read once; prefixes; Find (Ctrl+F); rename (F2); menus' Alt letters; focus after Load Directory, Open, Save |
| Viewer | opens on the newest description; list order; Descriptions menu acts on the one read; no extra Tab stop |
| Batch window | title progress not spoken after every picture; the stats list sections; cost rows in cents; completion; Stop and resume |
| Dialogs/Configure | each tab by Ctrl+Tab; each setting's name and value; Change Setting; Add/Replace/Test Key; number fields refuse bad values aloud |
| Download, Video, Gallery, Process dialogs | opening speech short; every field named; defaults |
| Chat window | reply read once and in full; Enter mid-turn; Chat Settings order; history list lines |
| IDT Chat | reply; attachments; the Speech setting; web search toggle; the announce policies |
| Exports | HTML report and gallery in browse mode: headings, alt, no doubled text, lists |
| Providers | each error message box is short and says what to do; key prompts |
| Video | extraction progress; frames in time order in the tree |
| Mac | VoiceOver on the same flows (when Mac code changed) |
| Installer/updater | install, upgrade, "update available" message, relaunch |

### 6.5 Automation that would most reduce listening

In order of value per effort:

1. **NVDA speech capture of fixed flows in the vmtest VM (sr-test skill), per release.**
   The bug bash flows already exist (`OneDrive\testing\idt\nvda-bugbash-2026-11-15\steps\01-09`).
   - Turn them into expected-speech files and run them against each release's installed
     build.
   - A diff of what NVDA said against last release's capture shows exactly what changed.
   - Kelly then listens only to the diffs, and the JAWS checks for those.
   - This is what would have caught #409, #410 and #420 before release.
2. **UIA name, role and focus assertions on the frozen app in the VM.** Small
   pywinauto/UIA script per window: every focusable control has a name, no control is
   named "×" or empty, and focus after Ctrl+O, mode switch and batch end. Cheaper and less
   flaky than speech, and catches the "empty image tree name" class (2026-10-06 summary).
3. **An in-process wx accessibility sweep in pytest:** for every dialog the app can open,
   walk the children and assert each focusable control has a non-empty `GetName()` that
   isn't a code name (`default_provider`), and that no StaticText ends up as a field's
   label by accident (#420). It runs in coverage.yml on every PR. Start with Gallery and
   Download, which have no tests today.
4. **Install-then-smoke in CI:** run the installer silently (`/VERYSILENT`) on the Windows
   runner, then the frozen `idt` smoke and the 15 s GUI survival check against the
   installed copy. Fix `test_frozen_executable.py`'s path.
5. **A `gui` pytest marker** so the windowless suite can run anywhere and the wx suite is
   sent to the VM on purpose (memory: feedback-gui-tests-in-vm).
6. **HTML report checks:** run axe (already used for docs) on a generated report and
   gallery in CI.

### 6.6 What Claude verifies itself before Kelly listens

Per memory: feedback-ai-does-functional-validation. All on the **installed** CI build in the
VM, with evidence in a report beside the build:

- The release's own changes, end to end, each with the request sent, the run log and the
  output.
- The wx test suite in the VM, plus the NVDA speech capture of the 9 flows, diffed
  against the last release.
- The UIA sweep (once built).
- The smoke checklist above run under NVDA by Claude first, so Kelly's pass is
  confirmation, not discovery.
- The CLI matrix: describe, video, watch, combine, export, status and show, with exit
  codes.
- For a settings change: every setting × provider (Ollama local, Claude, OpenAI; Claude
  Code and Apple where reachable).
- Windows AI only on Kelly's PC, short runs. Mac by CI plus a real Mac when one is
  reachable.
- **Kelly's TESTING.md then lists only:** the smoke checklist, the per-area listening
  items for the areas changed, and the JAWS checks no automation can do.

---

## 7. Decisions only Kelly can make

**Decided 11/27/2026.** Every recommendation was taken except decision 1. The NVDA DLL
isn't shipped for now, so 4.9.1 ships #409 alone (decision 2). #410 and #439 left the
4.9.1 milestone and wait on the DLL. Decision 10 is done: #442 and #512 are closed, and
Dependabot skips Windows App SDK majors (#515). Decision 8 is done: 28 issues closed with
the evidence above. #23 stays open, because its flag is still in `ai_providers.py` (set to
`False`, not removed), so it moved to 4.12. #201 and #14 stay open until their one check
each. Milestones exist for every release, and each open issue is in one.

| # | Question | Recommended |
|---|---|---|
| 1 | Ship NV Access's `nvdaControllerClient.dll` (LGPL, unmodified) so NVDA reads chat replies in full (#410, #439)? | Yes, in 4.9.1, with its license in the installer's notices. |
| 2 | If the DLL is a no, ship #409 alone in 4.9.1 and leave chat replies on the focus bounce? | Yes, rather than hold #409. |
| 3 | Strip Markdown in the Viewer, the description list and TXT exports (the editor and CSV stay raw)? | Yes, in 4.10. HTML exports get rendered Markdown in 4.9.1 either way. |
| 4 | One provider name in exports: `claude` or `anthropic` (#464)? | `claude`, the name users pick. |
| 5 | One fallback Ollama model (#430): `minicpm-v4.6` everywhere? | Yes. |
| 6 | Remove Configure's Workflow Settings tab rather than wire it up (#433)? | Remove it. |
| 7 | Should pasting an image start describing it (#8)? | No. Keep P; close #8. |
| 8 | Close the ~25 fixed and obsolete issues in section 1? | Yes, with the evidence above as the comment. |
| 9 | Is 5.0 the installer and update release (Velopack, per-user install, App Kit), with Codex, prompt sharing and the rest in 5.x? | Yes. That's the only way 5.0 lands by 12/31. |
| 10 | Close #442 and pin the Windows App SDK to 1.x until 5.0? | Yes. |
| 11 | Keep the bundled MLX provider (#226)? | Decide after a 1-hour benchmark on the Mac. Until then, no new MLX work (#102, #125). |
| 12 | Five point releases before 5.0, or fold 4.12 into 5.0.x? | Fold 4.12 if 4.10 slips past 12/10. |
