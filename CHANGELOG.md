## [Unreleased]

### 🐛 Bug Fixes

**Markdown in descriptions reads properly in HTML exports (#465)**
- Models often format descriptions with Markdown: `## Setting`, `**Foreground:**`, `- a red chair`. The HTML report, ImageDescriber's Export HTML and all four gallery styles showed it as typed, so a screen reader read "number sign number sign Setting" and "star star". Now headings show as bold lines, `**bold**` and `*italic*` as bold and italic, and lists as real lists.
- Headings are bold paragraphs, not HTML headings, so the page's own heading structure (a heading for each picture) stays intact.
- Anything that looks like HTML in a description is still shown as text, never run.
- Not changed yet: the Viewer, the description list and TXT exports still show Markdown as typed (planned for 4.10).

**OpenAI's December shutdowns: GPT-5, GPT-5 mini, GPT-5 nano and o3 are no longer offered**
- OpenAI shuts these down on 12/11/2026, so they're gone from the OpenAI model list in ImageDescriber, Configure and `idt models`. Workspaces described with them still show their names, and `idt stats` still prices them. GPT-5 pro and o3-pro, also shutting down, were never offered.
- If one of them is still chosen in your settings, describing a picture fails with OpenAI's "does not exist" message followed by "OpenAI has shut down GPT-5 Mini. Choose another OpenAI model, such as GPT-6 Luna." Before, it said only that the model doesn't exist. The default, GPT-6 Luna, isn't affected.

**A photo Apple Intelligence declines is tried again with another prompt style**
- When Apple's safety guardrails decline one photo, IDT asks again with the **technical** prompt, then **artistic**, keeping the photo's location. The description records the style that wrote it, and the run log says so, for example `[narrative refused; used technical]`.
- In an 11,559-image iPhone library run, 9 photos were declined. On a retry these two styles described all 9. Most of the others were declined on several of the 9.
- A custom prompt is never swapped for a built-in one. Both ImageDescriber and the `idt` command line do this.

**A workspace in OneDrive no longer loses its settings at the end of a long run**
- At the end of a 29-hour batch, the workspace's settings were replaced with the defaults (Ollama, the detailed prompt), as if the workspace had just been created. The descriptions were all kept. A cloud-synced folder can hide a file for a moment while it syncs, and IDT took the missing settings file as "no workspace here" and started a new one. IDT now waits for the file to come back, and if it doesn't, reports the problem and leaves the workspace unchanged.
- A run's log in the workspace's `logs` folder kept nothing after its third hour, though the run carried on for 26 more. Each line is now written to whatever file is there at the time, so a file the sync client swaps out no longer swallows the rest of the run.

## [4.9.0] - 2026-11-15

### ✨ New

**Generation settings for every provider (#392)**
- A new **Generation** tab under Tools → Configure Settings in ImageDescriber sets, per provider, what IDT asks a model for besides the prompt. Ollama: thinking, temperature, top p, top k, repeat penalty and output limit. OpenAI: thinking, effort, temperature, top p and output limit. Claude and Claude Code: thinking, effort and output limit. Apple Intelligence (temperature, output limit) and MLX (output limit) appear only on a Mac. Every setting starts on Automatic, which uses IDT's default for the chosen model.
- `idt describe`, `idt download`, `idt video` and `idt watch` take `--think`, `--no-think`, `--temperature` and `--max-tokens`, which override saved settings for that run. The command line and ImageDescriber read the same saved settings, under "generation" in the config file.
- A setting a provider or model can't take is skipped, with one note in the run log. An optional setting a model rejects is dropped and the request sent again, and the rejection is remembered for that model.
- IDT Chat has a **Chat → Thinking** menu and ImageDescriber's chat window has **Session → Thinking**, each with Automatic, On and Off. Before, a thinking model always thought in both, with no way to turn it off. The choice now reaches Claude, OpenAI reasoning models and Claude Code as well as Ollama. Where reasoning can't be switched off, Off asks for the least effort the model takes.
- Ollama model pickers in ImageDescriber mark thinking models "(thinks, slower)" and name the installed `-instruct` edition when there is one.

**Claude 5.5 models; Haiku 5.5 the default (#445)**
- The built-in Claude list adds Haiku 5.5, Sonnet 5.5, Opus 5.5 and Fable 5.1 and 5.2, so they're offered before a live refresh and offline. Mythos (verified organizations only) and the retired Opus 4.1 are no longer offered, but old workspaces still show their names.
- The default Claude model is `claude-haiku-5-5` (was `claude-opus-4-8`). With the Detailed prompt it cost about $1 per 1,000 images, against $13 for Sonnet 5.5, $30 for Opus 5.5 and $25 for Opus 4.8.
- Context and output limits match Anthropic's model list (1M context from 4.6 on). Claude chats still drop their oldest turns past 200K tokens, so a long chat doesn't re-send up to 800K tokens a turn.
- `idt stats` has a price for every listed Claude model; it had none for 5.x and charged Opus 4.8 and 4.6 at $15/$75 instead of $5/$25.
- ImageDescriber's batch window has a cost meter: Estimated Cost So Far, Average Cost per Image and Projected Batch Cost, from list prices shared with `idt stats` in `idt_core/pricing.py` (#451). A weekly workflow compares those prices with Anthropic's and OpenAI's pricing pages and keeps an issue up to date when they differ.
- Switching between Editor and Viewer mode moves focus into the view now showing, so screen readers announce it; before, focus stayed on the hidden view and nothing was said (#419, #452). Batch end, stop and error paths keep focus in the visible view.
- ImageDescriber shows and speaks models by name ("Claude Haiku 5.5"), not API ID, in description details, batch progress, Properties, Workspace Statistics, the chat window and the Viewer (#448). Exports keep the ID.
- `idt stats` totals tokens and cost across every description, not only each picture's current one, including whole-video descriptions (#450). It now has OpenAI list prices, and labels rows that have no per-token price ("no charge", "Ollama plan", "your plan", "no price", "no token data"). Costs with missing token counts read "at least". In `--json`, `provider` stays lowercase; `provider_name`, `descriptions`, `cost_is_partial` and `total_estimated_cost_usd` are new; `images` now counts pictures with any description by the model.
- `idt stats` counts input tokens for pictures ImageDescriber described (#446). They were saved only in the description's metadata, so the input cost was left out: $10.14 shown against $21.36 actual on a 6,819-picture workspace. Existing workspaces read correctly without being rewritten.

**OpenAI's current models; GPT-6 Luna the default (#453, #483)**
- The built-in OpenAI list has every image-input chat model OpenAI listed on 11/18/2026: GPT-6 Luna, GPT-6.1 Terra, GPT-6.2 Sol, GPT-6.2 Astra, GPT-6.1 Sol, GPT-6 Sol, GPT-6 Astra; GPT-5.6 Luna, Terra and Sol; GPT-5.5; GPT-5.4 and 5.4 mini; and, marked deprecated where OpenAI says so, GPT-5.4 nano, 5.2, 5.1, 5, 5 mini, 5 nano, o3, GPT-4.1, 4.1 mini, GPT-4o and 4o mini. The `-pro` models, `gpt-5.3-codex` and `gpt-live-1` aren't offered.
- The default OpenAI model is `gpt-6-luna` (was `gpt-5.2`): $0.10 in and $0.50 out per million tokens, the same as Claude Haiku 5.5. About $0.15 per 1,000 pictures with the Detailed prompt in a short test.
- `o1`, `o4-mini` and `gpt-4.1-nano`, which OpenAI has shut down, are no longer offered; workspaces described with them still show their names, and `idt stats` still prices them.
- Every new model has a list price, used by `idt stats` and the cost meter. GPT-6 Astra, GPT-6.1 Sol, GPT-6.2 Sol and GPT-6.2 Astra reject `reasoning_effort: "none"`, so Thinking Off and Minimal send them `low`.
- ImageDescriber's chat window falls back to the provider's default, not `gpt-4o`, when the model list can't be fetched.

**Configure → API Keys: Add Key for the selected provider, and Test Key (#485)**
- Add Key and Edit Key are one button whose label follows the selected row (**Add Key** or **Replace Key**). It opens the key dialog for that provider only, titled for it, with no provider dropdown and focus in the key field. A row is always selected, after Add, Replace and Delete too. A key for a provider IDT doesn't recognise, left in the config file, is replaced under the same name; before, Edit could save it under an empty provider name.
- **Test Key** (Alt+T) sends one tiny request with the selected key on a background thread: "Reply with the single word OK." on the cheapest priced model for Claude and OpenAI (today `claude-haiku-5-5` and `gpt-5-nano`), at the lowest reasoning effort for OpenAI; one web search for the Ollama web search key. The result goes in a read-only **Test result** box, which takes focus; a key that works gives one line with what the test cost, and a failure gives a short verdict first (key not accepted, out of credit, key not in a Claude workspace, organization on hold, model not available, rate limited, overloaded, server error, no connection or timeout), then what to do, then the provider's message with anything key-like removed. A result for a key replaced or deleted during the test is dropped.
- Enter in the key field presses OK (#478, #486): no button was the default, so Enter did nothing. An empty or blank key is still refused with a message, keeping the dialog open.
- Replace Key warns when an environment variable outranks the key just saved, as Delete did. The list reads each key's source once per load rather than on every arrow press (on a Mac, a Keychain call per key press).

**Exit codes for the describing commands (#454)**
- `idt describe` (folder, workspace and stdin), `idt download --describe`, `idt video` and `idt watch` exit 0 when every picture tried was described or there was nothing to do, 1 when nothing was described and something failed or the run couldn't start, 2 for a usage error, and 3 when some were described and some failed. They used to exit 0 even when every picture failed. A piped-in path that doesn't exist, and a video whose frames can't be extracted, count as failures; pictures skipped on purpose count as neither. `idt video` without `--describe` counts videos; `idt watch` covers the whole watch, up to Ctrl+C. Each command's `--help` lists the codes.

### ✨ Improvements

**The usage line stays in ImageDescriber, out of everything else (#489)**
- The line ImageDescriber appends to a description (`[Token Usage: … | Time: …]`, or `[Time: …]` alone) stays in the stored text and ImageDescriber's reading views, and is removed everywhere else by `idt_core.description_text.strip_usage_line`: copying, every exporter and the gallery, the HTML report's alt text, embedded metadata (`idt embed` and ImageDescriber's Embed), `idt show` and `idt combine`. Workspace Statistics now also removes the time-only form.

**Ollama descriptions: thinking off by default, and no more blank answers (#392)**
- Descriptions sent Ollama no options and no `think` setting, so thinking models reasoned at length on every picture and the reasoning was discarded (60 to 75 percent of the output, measured on an M5 Pro). Thinking is now off for descriptions unless you turn it on.
- No `qwen3-vl` thinking tag (2B, 8B and 32B were measured) honours "thinking off". For those, use the `-instruct` tag, such as `qwen3-vl:8b-instruct`. IDT logs once when a model keeps thinking and suggests it.
- An answer that is all reasoning is tried once more, then reported as a failure, instead of saved as a blank. One `qwen3-vl:2b` run had returned an empty description after 13,000 characters of reasoning. Reasoning text never reaches a description.
- The output limit is withheld for Ollama cloud models and while a model is thinking.
- Run logs, from the command line and ImageDescriber, record hidden reasoning and cut-off descriptions per image, and any provider notices. Timeouts from the HTTP library now count as transient.
- ImageDescriber describes with Ollama through the same code as the command line. A request that waits out the 30-minute limit isn't retried. Ollama Cloud now reports token usage.

**The command line follows Configure's defaults (#455, #431)**
- `~/.idt/config.json` froze in whatever defaults applied the day it was first saved, since every save wrote all three and ImageDescriber's startup update check saves it, so Configure's later choices never reached the command line. Now only defaults set with `idt config --set` are saved (listed under `user_set`); anything else comes from Configure, including its default provider, which wasn't read before. A file from before 4.9 whose three defaults all match old shipped defaults is treated as frozen and ignored; otherwise its values are kept as the user's. A new workspace therefore uses Configure's `default_prompt_style` (`narrative` as shipped) (#431).
- Configure's default model is its Ollama model and is used only with Ollama. A model set with `idt config --set` is recorded with its provider (`default_model_provider`), so changing the default provider later doesn't send it to the wrong one. If Configure's default provider is one only ImageDescriber can run (MLX), the command line says so and uses Ollama.
- `idt config` says where each default comes from ("set with idt config" or "from Configure"). `idt config --set` checks provider and prompt names before saving and accepts any case.

### 🐛 Bug Fixes

- Cmd+, did nothing in ImageDescriber or IDT Chat on macOS. wxWidgets 3.3 moves the `wx.ID_PREFERENCES` item to the application menu but gives it no Cmd+,; both items now carry `Ctrl+,` themselves. IDT Chat's Help → Keyboard Shortcuts lists it.
- Installing a new version over an ImageDescriber or IDT Chat that was still open made whatever was opened next fail with a misleading error, such as "Operation not permitted" for the settings file when opening Settings, or "Error -3 while decompressing data". The macOS apps load parts of themselves from the app file as they're first used, and the open copy was reading the new file. They now notice the app has been replaced and say to quit and reopen it; Configure logs its launch errors with the traceback.
- The batch cost meter was reset only on the main batch path: resuming a batch, a URL download, and auto-processing downloaded images or extracted frames started with the previous batch's cost and picture count, so the average opened wrong and drifted for many pictures, and the projection included the old batch. Pictures processed with P, a follow-up or an auto-rename during a batch were added to it too. `_start_batch_meters(options)` resets the meter (and names the batch's provider, model and prompt) wherever a batch window opens; `_meter_picture` counts only the batch's own pictures. The GUI run log records each picture's cost, running total and average. The batch window adds the largest-token picture's description and a Most Expensive Picture row, and list rows show descriptions on one line (#507).
- A description file that can't be read when a workspace opens is logged rather than skipped silently (#507).
- File → Save in an already-saved workspace skipped every `chat:` item, so chats added there were lost on reopen. `_save_bundle` now writes changed chats through `_gui_chat_item_to_bundle`, as Save As does; a chat with no id is never written (#403, #504).
- Selecting a folder node left the last picture as `current_image_item`, so R, F2, M, F, Z and Enter acted on a picture out of sight. A folder now leaves nothing current and shows "Folder: name, N items"; `refresh_image_list` keeps a selected folder across rebuilds, never leaves a hidden or closed workspace's picture current, and the Chats node doesn't enable Process (#497, #501).
- The finished batch window rebuilt its summary from the last progress event, leaving out the batch's last picture; `on_worker_complete` passes it through `note_completed` for the current batch only (#475, #506).
- `idt describe` with Claude or OpenAI and no key failed per picture with the SDK's "Could not resolve authentication method"; `_make_provider` checks once, up front, with `idt chat`'s message. ImageDescriber's no-key message says where to add a key, and blames the SDK only when its import failed (#467, #477, #503).
- A dropped connection with no status code is `ErrorKind.CONNECTION` ("Couldn't connect to Claude. Check your internet connection."), still retried, rather than a "Server error" (#476, #503).
- Extract Video Frames opened at 5 s / threshold 30 whatever Configure saved, and dropped the start/end times, minimum scene length and max frames. It now opens with the saved settings and passes them all through; an empty max frames means no limit in scene mode (it was read as 50), and the shipped config sets 50 (#437, #503).
- The Prompt Editor failed every save with Ollama not running: the disabled "No models available" entry has no client data (#505).
- `idt describe --stdin` required a source argument; `source` is now optional with `--stdin`, and describe with neither says what to give (#500, #502).
- The text export's "Total Images" counted videos and chats, and chats were exported as pictures; both now count and list pictures only (#479, #504).
- ImageDescriber opens a workspace off the UI thread (`_run_with_progress`, now with `show_after`), with a progress count from `Workspace.items(progress=)` through `bundle_to_gui_workspace_dict(progress=)`. A cold open of a 12,906-item bundle in OneDrive took 95 s on the UI thread ("Not Responding"). A running folder scan is stopped first, the startup update check waits while a progress pump is running, and a hidden progress window is re-shown while its work runs (#492).
- Viewer mode sorted descriptions by file path (its comment said by time), so Home and End never moved. It now sorts by when each description was made, oldest first, with chat turns grouped after the pictures, and selects the newest picture description on load. The picture previews (Viewer and Editor, and Editor's preview container) are `shared.wx_common.NoFocusPanel`, so Tab no longer stops on an empty "panel"; `SetCanFocus(False)` didn't prevent it. Restoring the selection on a live update now refreshes the details too (#491).
- ImageDescriber: changing one picture relabels its entry (`refresh_image_label`) instead of rebuilding the image list (`refresh_image_list`), which took about 10 s per rebuild on a 12,906-item workspace with a screen reader and ran when a single picture started, finished or failed, on progress, and at every batch start. The rebuild is kept when a picture must appear or disappear under the View filter or a search, and at batch start only when the batch includes pictures the list doesn't show yet. Add Manual Description now updates the list (#429, #490).
- The location line sent before the prompt is reworded (`metadata_preamble` in `idt_core/pipeline.py`). "Capture metadata (not visible in the image)" made Claude Haiku 5.5 remark that it couldn't confirm the location in 30% of a 4,386-photo run; measured on 24 of those photos, the new line took it from 11 to 0 and output 27% shorter. ImageDescriber, which prefixes the place itself, uses a version that doesn't ask the model to name it (#488).
- Pictures sent to Claude are fitted to its 8,000-pixel side limit as well as its byte limit, in ImageDescriber (whose Claude path sent files as read), `idt describe` and Claude chat attachments. Pictures past Pillow's 179 MP guard are measured too; BMP/TIFF go as JPEG; transparency becomes white. ImageDescriber's re-compression of a JPEG over 3.75 MB now keeps it upright for every provider (#487).
- Editor mode: Save Description, Copy Description, Copy Image + Description, Edit Description and Delete Description always used the image's latest description, while the editor shows the first when an image opens. On an image with two or more descriptions, Save overwrote the newest with the edited text of the one shown, and the newest was lost. They now act on the description the editor shows (#482, #484).
- Editor mode: Save stored the details block shown under a description (Provider, Model, Prompt, Created...) in the description's text, so it reached exports and embedded metadata and doubled on the next save. Save now removes the block when it is unchanged; if the block itself was edited, Save refuses with a message rather than guess. A video's details, shown when it has no description, are no longer saved as its description (#449, #484).
- Delete Description names the description it will delete ("Delete description 2 of 3, by Claude Haiku 5.5?", with how it begins) instead of "the most recent", and after Edit or Delete the editor stays on that position (#484).
- Viewer mode: the Descriptions menu acted on the image selected in Editor mode, which is hidden there. Copy Description said "No description to copy" while one was on screen, and Edit, Delete, Add Manual Description, Ask Followup Question, Process (P), Rename (R, F2), Auto Rename (Z) and Play Video would act on the hidden image. Copy Description, Copy Image Path, Copy Image and Copy Image + Description now use the Viewer's selection (a video's first frame for Copy Image; a chat entry says it has no image path). The others say they are done in Editor mode, how to switch and which image to select, or, for a workflow folder, to import it with File, Import Workflow (to Workspace) (#480, #481).
- `idt describe` on a workspace ImageDescriber described with Claude stopped with "Unknown provider: 'claude'": ImageDescriber saves Claude as `claude`, the command line knew only `anthropic`. Every provider name now goes through one translation, and an unknown one stops the run with a clear message (#455).
- `--provider anthropic` or `--provider openai` without `--model` sent the Ollama default (or the workspace's last Ollama model), and every picture got a 404. One resolver replaces five copies in describe, stdin mode, download, video and watch: a saved model is used only with its own provider or when IDT knows it as one of that provider's; otherwise the provider's default. The run's header names the model (#455).
- An unknown `--prompt` was accepted, the default prompt's text sent and the typo saved. Prompt names now match regardless of case; an unknown `--prompt` exits 2 with the list of prompts; an unknown name inherited from a workspace or the config warns and uses the default. Configure offered "Simple", which matched no prompt; it offers "simple" (#455).
- `idt guideme`'s API key check used its own lookup, so a key saved in Configure was reported as not set, with "No" as the default answer. It uses the same lookup as `idt describe` (#455).
- On Windows, video frames were lost without a word when the workspace path had non-ASCII characters (`C:\Users\José`): `cv2.imwrite` returns False on such a path and nothing checked. Frames are now encoded in memory and written by Python, in the command line and ImageDescriber; a frame that can't be written raises an error, and `idt describe` reports the video on stderr, even with `--quiet`, and counts it as failed (#454).
- `idt download --describe --embed` crashed with `NameError` after doing the work (#454).
- `idt show <picture>` couldn't find pictures in subfolders of the described folder. The search now tries every ancestor folder's workspace and matches on the original's full path, so a same-named picture elsewhere, or an unrelated workspace with the same name, isn't used (#454).
- ImageDescriber showed "Prompt: custom" for every description the command line made with a named prompt, since the command line stores the prompt text. A description is now "custom" only when its name is `custom` or empty, or its text isn't the named style's text. Known limitation: after a built-in style is edited in Configure, earlier descriptions made with it show "custom" (#454).
- Refresh AI Models and the Configure launch error showed a double-escaped `\n` as text, read as "backslash n" by screen readers. A test scans ImageDescriber and IDT Chat sources for the pattern (#457).
- The end-of-batch failure message named "Process > Describe All Undescribed", which doesn't exist; it names Process > Process Undescribed Images (Entire Workspace) (#457).
- On an installed Windows copy, nothing saved in Configure reached processing or the CLI: config_loader read `{app}\scripts` (and the installer's `IDT_CONFIG_DIR`) before the user config dir Configure writes. The user's saved settings now come first, with any missing top-level section filled from the shipped defaults; every save goes to the user dir; the installer no longer sets `IDT_CONFIG_DIR`; a stale saved default model of `moondream` gives way once to the current default; `IDT_USER_CONFIG_DIR` overrides the user dir (#407, #432). Found by the NVDA bug bash.
- `idt describe` stripped the default model's tag (`moondream:1.8b` → `moondream`, a 404); only `:latest` is dropped now (#411, #432).
- From an end-to-end check of the installed build, with real OpenAI and Claude calls (#440, #441):
  - Ollama Thinking On was sent to models that can't think, failing every picture; it is now sent only where the model reports the capability, logged once otherwise, and the chat windows say so. Claude models that refuse adaptive thinking (Haiku 4.5) get a thinking budget instead, remembered per model.
  - `idt describe` ignored a key saved in Configure (credential store); the Claude and OpenAI providers now resolve a missing key through `idt_core.keys`.
  - Enter on a Configure settings list now opens Change Setting (the dialog took Enter first); setting editors and the dialogs' number fields give screen readers their name and range through `wx.Accessible`, since a Windows edit takes its name from the label before it.
  - Settings files are read with `utf-8-sig`. A file that can't be read is left untouched: the one-time settings check had written its marker over such a file, deleting its settings and keys.
  - ImageDescriber opens a `.idtw` given on its command line; `idt describe --showgui` with a workspace explains how to resume.
- About showed "Version: 1.0.0" in built copies: VERSION is bundled in `_MEIPASS`, which wasn't searched (#415). An offline update check showed the raw exception; it now says to check the connection, and gives GitHub's reset time when rate-limited (#416, #435).
- The Extract Video Frames and Download dialogs' spin boxes clamped out-of-range numbers silently; they are now text fields checked on OK, sharing `shared/number_entry.py` with Configure, with one range per setting (interval 0.5–60 s, scene threshold 1–100) (#406, #436).
- Closing ImageDescriber or IDT Chat on Windows left a "Warning" box, "Failed to remove temporary directory", and another `%TEMP%\_MEI…` folder each time. The Windows apps are now PyInstaller folder builds (each `.exe` with its own `-lib` folder) instead of one-file exes, so nothing is unpacked to Temp (#404). The standalone Windows downloads are now `.zip` files.
- Saving a workspace wrote every item, so two new descriptions in a 12,911-picture library meant a 12,911-item save. A save now writes only items changed since the workspace was opened or last saved (#402).
- The Process dialog took 8 to 21 seconds to open: requests to Ollama at `localhost` waited 2 seconds each for Windows to give up on IPv6. IDT now uses `127.0.0.1`, also for a `localhost` address in settings (#402).
- The default provider choices offered Apple Intelligence on Windows and Windows AI on a Mac (#402).
- Outside the Generation tab, the Configure dialog saved a bad number as something else without a word: "abc" as 0.0 or as unlimited, and a spin box's 150 as its maximum. Every number is now checked on OK, with a message naming the range, and the three whole-number settings are text boxes rather than spin boxes, which clamped on losing focus. Number fields' names include their range and read without underscores (#405).
- In the Configure dialog on Windows, Left and Right moved two tabs per press, so half the tabs were unreachable after the first pass; Up and Down did nothing. Each setting's explanation, and the help on the API Keys and Workspace tabs, is now in a read-only box reachable by Tab (#401).
- `idt describe --provider openai` sent `max_tokens`, which OpenAI's reasoning models reject (the default model was then `gpt-5.2`). It now sends `max_completion_tokens`. Confirmed live: the old request fails with a 400 on `gpt-5.2`, and the new one describes with `gpt-4o-mini`, `gpt-5-nano`, `gpt-5-mini` and `gpt-5.2`, with thinking off and with a temperature (dropped for reasoning models).
- ImageDescriber capped most OpenAI models at 300 tokens and Claude at 1,024, cutting detailed descriptions short. Both are now 4,096, and what counts as an OpenAI reasoning model no longer depends on a list of name prefixes.
- Claude Opus 5.5 descriptions failed through the Claude API: both the command line and ImageDescriber read the first part of Claude's reply as text, and Opus 5.5 always sends a reasoning block first, with no text. They now join the text parts. Checked live with Haiku 5.5, Sonnet 5.5, Opus 5.5 and Haiku 4.5, including thinking on and off.
- An empty answer from OpenAI or Claude is now an error, not a saved blank that counted the picture as described. Refusals and content-filter declines mark that picture and the run carries on.
- The command line's Claude path shrinks images over the API's size limit, as Claude Code already did.
- ImageDescriber made up to 16 attempts per failing image; it is now at most 8, and dropped connections are still retried.
- Chat no longer sends `temperature` to OpenAI reasoning models.
- The five temperature, max tokens, top k, top p and repeat penalty entries are gone from the Configure dialog, along with `model_settings` and `prompt_model_settings` in the shipped config. Nothing has read them since the legacy scripts were removed in June, so changing them did nothing. Values already in a user's config file are left alone and ignored.

- Screen reader fixes from the 4.9.0 triage:
  - the HTML report's `alt` was the whole description, printed again below it; it's now "<name>, described below", and HEIC pictures use their converted JPEG (#465, part; Markdown still shows literally);
  - an empty Descriptions list read "unknown" twice; it shows "No descriptions yet", and the list no longer hands the screen reader the previous picture's descriptions (#423, #504);
  - descriptions are tidied of leading blank lines and trailing space when made and when loaded (`tidy_description_text`), so the editor doesn't start on "blank" (#424, #504);
  - the image tree binds `EVT_TREE_ITEM_MENU`, so the Applications key and Shift+F10 open a folder's menu (#498, #504);
  - the batch window title reads "45%, 9 of 20 images described — …" while describing (#412, #506);
  - the "─" separator rows are gone from the batch window and Workspace Statistics (#427, #506);
  - at batch end the image list is rebuilt before focus, so its item is read once (#414, #506);
  - Configure reads settings by plain names ("Default provider: Ollama"), in the list and in Change Setting, and is titled "Configure" once (#422 part, #505);
  - the Prompt Editor's combo boxes are named with `set_screen_reader_name`, its title has no file name, and the `--provider` note is gone; so is the Model description box's missing name in Processing Options and the follow-up dialog (#417, #418, #505);
  - Chat Settings opens on Provider, and `chat_window_title()` stops "Chat: Chat - …" (#421 part, #506);
  - the Save Workspace dialogs say "workspace" and no longer read "less than name greater than" (#426 part, #504).
- Costs under a dollar are shown in cents in the batch window and Test Key ("0.096 cents", "62 cents"), dollars and cents from $1 (#495).
- Claude and Claude Code chat attachments: pictures over 5 MB are scaled to fit rather than refused, and a picture that can't be read is refused with a reason (#494).

### 🔧 Other

- The Prompt Editor's API Key field is removed: it wrote a top-level `api_key` nothing read. A key saved there is left in the file. For OpenAI and Claude, a read-only note says to use Add Key in Configure (#499, #505).
- Configure's Default prompt style lists every prompt in the settings file, custom ones included (#469 part, #505).
- IDT's links, updater and user guide point at TheIdeaPlace/Image-Description-Toolkit (#381). Installed copies keep updating through GitHub's redirect.
- Range checks on command-line numbers, as argparse types so they exit 2 before anything runs: `describe --limit` 1 or more (`--limit 0` is an error, not "no limit"), `video --interval` and `describe --video-interval` 0.5 to 60, `video --scene` 1 to 100, `chat --max-tokens` and `watch --interval` more than 0 (0 used to poll in a tight loop), `download --min-size` as WIDTHxHEIGHT (a malformed value used to be ignored). `idt guideme` asks again for a limit below 1. The video ranges are shared with ImageDescriber's dialogs (#454).
- `idt --version` works as well as `idt version` (#455).
- Documentation checked against the code from the 4.9.0 bug bash: the user guide's API key setup (Configure first, then the full lookup order), the `idt describe`, `models`, `chat`, `config`, `show`, `status`, `export`, `combine` and `embed` references, what metadata and geocoding send, HEIC support, workspace reference mode, the installer and standalone downloads, and the real Process menu names; `CONFIGURATION_GUIDE.md` rewritten for the user config dir; `--help` text corrected to match (#456).

### Known limitations
- The end of a batch and ImageDescriber chat replies aren't announced on their own (#409, #410); the fix, which ships NVDA's controller DLL, is held for 4.9.1 (#438).
- A Claude API key that isn't assigned to a workspace still needs an `anthropic-workspace-id` header IDT can't send. Use a key assigned to a workspace, the default for new keys.

## [4.8.1] - 2026-10-09

### 🐛 Bug Fixes

**The command line stops a run when every image is failing the same way**
- `idt describe`, `idt guideme` and the other describing commands now stop when ten different pictures or videos in a row fail with the same error, as ImageDescriber already does. Before, they carried on through every remaining image. When Windows AI stopped responding partway through a large batch, each picture waited three minutes to time out, with over 10,000 still to go.
- They stop at once for a problem nothing else will get past, such as the Windows AI helper not being installed. They also stop when the provider declines 25 images in a row, which usually means it is declining the prompt itself. A few declined pictures don't count toward the ten.
- A video's frames count as one picture toward the ten, in the command line and in ImageDescriber, and once 3 frames of a video in a row fail the same way, the rest of that video is skipped. Windows AI failed on every frame of one iPhone screen recording while describing everything around it, and those frames stopped the run at the same place on every run. Skipped frames stay undescribed. The command line counts them at the end of the run and says how to try them again; ImageDescriber marks them as failed, Process > Process Undescribed Images (Entire Workspace) tries them again, and resuming a batch that stopped because the provider stopped working tries them too. A stuck provider still stops the run, after at most about 30 pictures.
- The command line remembers which pictures a provider, model and prompt declined ("too much text", a content filter; not a file it couldn't read) and leaves them out of later runs, saying how many. Asking the same way again gets the same refusal, and those pictures, still undescribed, came first in every rerun. Another model (for Windows AI, which takes no prompt, another `--model`), prompt style or provider asks again, and so does `--redescribe`, which describes every picture again. A video whose frames are declined is skipped after 3 of them, in the command line and in ImageDescriber; next time the command line leaves the whole video out. The 25-refusals stop counts different pictures or videos. ImageDescriber's saves keep these marks.
- In the command line, pictures that failed before are tried again, but after every picture not yet tried, and one failing again exactly as before doesn't count toward the ten: a rerun stopped at picture 72 when ten earlier failures failed again, though Windows AI was working. A timeout always counts, and 30 pictures in a row failing again with none described still stop the run.
- The last line says "Stopped." instead of "Done." and counts the images not tried. Below it, IDT says why it stopped and gives the exact command to carry on. The window title says the run stopped early, and the reason is written to the run log.
- `idt watch` stops only the batch that was failing and keeps watching. It says how to describe the images that batch didn't reach.

**Describing a folder again no longer extracts its videos' frames again**
- `idt describe` and `idt video` read every video again on each run, even when its frames were already in the workspace. For a large library on a network share, that was up to three hours of extraction before any picture was described. Now a video is skipped when all its frames are still there and were made with the same options. Its line then says "(already extracted)".
- A video is extracted again if it was stopped partway, if any of its frames were deleted, if reading it ended early (a network share dropping out, for example), or if you ask for different options, such as `idt video --interval 1` after `--interval 5`.
- When reading ends early, the video's line says it will be read again next time. Some files always end early, such as a clip trimmed without re-encoding. If a second read stops at the same place, that is taken as the real end, and the video is skipped after that.
- Videos in workspaces made before this version, or by ImageDescriber, are extracted once more. After that they're skipped.

## [4.8.0] - 2026-10-06

### ✨ New

**Windows AI: describe images on a Copilot+ PC, on the PC itself (#360)**
- A new provider, Windows AI (`--provider Windows-AI`), uses Windows' own on-device model. It runs on the PC's NPU: no API key, no account, no internet connection and no cost, and pictures never leave the PC. It needs a Copilot+ PC with Windows 11 24H2 or later.
- Its models are the four kinds of description Windows offers: accessible (the default, written for people who are blind or have low vision), detailed, brief and diagram. It takes no prompt, so the prompt style isn't used and descriptions record the prompt as "none".
- It works in `idt describe` and the other describing commands, `idt guideme`, and ImageDescriber. It isn't offered for chat, follow-up questions or auto-rename, which all need a prompt.
- Windows declines some pictures: ones that are mostly text (OCR suits those better), and ones its content filter stops. Each is marked as failed and the batch carries on, as for Apple Intelligence's refusals.
- When Windows' model fails on a picture with an internal error, IDT tries it again at smaller sizes. Whether it fails depends on the picture's size, so most of these are then described.
- The installer sets it up when **Set up Windows AI** is ticked (the default on Windows 11 24H2 and later) and the PC has an NPU, adding the Windows App Runtime from Microsoft if the PC doesn't have it. Uninstalling IDT removes it.

### 🐛 Bug Fixes

- ImageDescriber's Processing Options dialog now opens on the model in your default settings. It read a setting the real settings don't have, so it always started on the first model in the list.
- Very large images sent to Claude Code that were still too big after resizing are now made smaller again instead of failing.
- Large phone photos that IDT makes smaller before sending are turned upright first. They could reach the model on their side.

## [4.7.0] - 2026-10-06

### ✨ Improvements

**A batch with videos describes while it extracts (#344)**
- A batch with many videos used to describe nothing until every video's frames were extracted: over half an hour for a large iPhone library. ImageDescriber now describes the photos straight away and adds each video's frames to the batch as soon as that video is extracted.
- The progress window shows the describing progress, whose total grows as videos finish, and a separate **Extracting Frames** line counting the videos. Its title changes once, when extraction finishes, not on every update.
- **Stop** stops describing and extraction together. Fully extracted videos keep their frames; a video stopped partway is extracted again next time.
- If the batch stops before it finishes (the provider refused the request, for example a sign-out, or ImageDescriber was quit or closed unexpectedly), resuming it carries on the same way: it describes what was left while extracting the videos it never reached.
- **Pause** pauses describing; extraction carries on.
- While videos are still being extracted, the progress bar shows activity rather than a percentage (the total is still growing, so a percentage went backwards), and there's no time-remaining estimate until it can be right.

### 🐛 Bug Fixes

**Quitting during frame extraction keeps the videos already extracted (#345)**
- Quitting ImageDescriber while a batch was extracting video frames lost every video already finished, and the next run extracted them all again: over 20 minutes for a large library on a network share. Each video is now saved as soon as its frames are extracted, so only the video in progress is extracted again.
- If an image finishes describing while ImageDescriber is closing, the batch is still recorded as stopped, not "complete", so reopening the workspace offers to resume it (#352).

**Apple Intelligence declining a few photos no longer stops a batch (#352)**
- Apple's safety guardrails decline some ordinary photos (see #337). Each one is counted as a failure, but they no longer count toward the "ten identical failures in a row" rule, which stopped a whole batch after a run of similar photos as if Apple Intelligence had stopped working. After 25 refusals in a row, the batch stops and asks whether to carry on: that many usually means the prompt itself is being declined. The declined photos stay marked as failed (describing them again with a different prompt style often works), and carrying on continues with the photos not yet tried.

**Smaller fixes to describing while extracting (#352)**
- In the progress window, the line you're on stays selected when lines above it appear or disappear (for example, when extraction finishes). A screen reader could otherwise move you to a different line.
- If the videos give no frames at all, ImageDescriber says frames could not be extracted, not "All images already have descriptions."
- The resume question after an unexpected exit counts the images done and left correctly, and no longer says "0 images, and N videos".
- Resuming a paused batch while videos are still extracting no longer shows a percentage in the window title.
- If describing fails outright, frame extraction stops too, instead of carrying on for a batch that has ended.
- While describing waits for the next video's frames, the progress window says so, instead of showing the last image as the one being described.
- The progress window's statistics count failures as its summary does: the last image's failure is counted, and images a stopped batch will retry aren't. They read "Failed: 3" above a "4 failed" summary.
- Choosing Yes to resume after a batch stopped resumes it as soon as frame extraction has finished stopping, with the progress window saying so, instead of being refused because a batch was "still finishing".
- If a batch is paused when extraction finishes, the window title stops saying "extracting videos".
- When you cancel quitting partway through a batch, and its last image has already finished but a video is still being let go, its progress window stays open saying "Stopping" until the batch has stopped, instead of only the status bar saying so.
- A workspace that hasn't been saved yet no longer shows "step 1 of 2" with no step 2.
- If some videos give only frames that are already described and others give none, both are reported, not just "All images already have descriptions."
- A new batch no longer inherits queued images from an older stopped batch, which made its resume question overstate the count.
- A batch that fails to start doesn't leave itself behind to resume, and puts back an older stopped batch it was replacing.

**"Embed description after processing" follows each batch in ImageDescriber (#346)**
- The image being described when Stop was pressed is now embedded too, if its batch was set to embed.
- A resumed batch (after a sign-in halt, or when reopening a workspace) now embeds as the original batch did. Before this, resumed images were described but never embedded.
- Images processed straight after downloading from a web page, and video frames processed straight after extraction, now follow the **Embed description after processing** checkbox. Before this, they were never embedded.
- A single image, follow-up question or rename during a batch that embeds no longer embeds unless it was asked to.
- While a batch is stopping, the progress window keeps its "Stopping" line, and focus stays on that line, even when another status message appears alongside it.

## [4.6.1] - 2026-10-05

Maintenance release. The two providers added in 4.6.0 are unchanged; these are
fixes found while using them.

### ✨ New Features

**Play a video from ImageDescriber**
- Press **Enter** (or double-click) on a video in the image list, or choose **Process → Play Video**, to open it in the system's default video player.
- If the video file has moved or been deleted, ImageDescriber says so instead of doing nothing.

### 🐛 Bug Fixes

**A batch with many videos starts straight away on a Mac (#342)**
- On a Mac with videos on a network share, ImageDescriber froze for up to two minutes when a batch started, before its progress window appeared; VoiceOver reported that ImageDescriber had no windows. Choosing each video's frames folder read every source video over the network, on the window's own thread: 1,340 videos took about 100 seconds over macOS's SMB client. That work now happens during extraction, one video at a time, so the progress window and its "Extracting frames" stage appear immediately and Stop works throughout.
- The frames saved at the start of describing are now written with everything else in the "Saving workspace" stage, off the window's thread, instead of first on it.
- If frames can't be extracted from any of the videos, ImageDescriber now says so instead of "All images already have descriptions."

**Stopping and restarting a batch with videos in ImageDescriber**
- Stopping a batch, then choosing **Process → Describe All Undescribed**, could extract a video's frames a second time and then fail on frames with "file not found". Four separate faults combined to cause this, and all four are fixed.
- **Stop works at every stage.** While frames were being extracted or the workspace saved, there was no way to stop a batch: the progress window's Stop button was disabled and Stop All Processing ignored that stage, so the batch went on to describe. Stop is now available while frames are extracted, and Stop All Processing works at every stage. Stopping ends extraction at the next frame and keeps videos that were fully extracted. A video stopped partway through is extracted again next time.
- **One batch at a time.** Starting a second batch while one was still extracting began a second extraction of the same video, which deleted the frames the first was about to describe. Process, Extract Video Frames and the other batch commands now say a batch is already running instead. After Stop, they wait until the image in progress is finished.
- **Extracted frames are found after reopening a workspace.** Frames were recorded as copied into the workspace's `images` folder when they weren't, so after reopening every frame was "not found". New frames are recorded correctly, and workspaces saved with the old record still find their frames.
- **Videos with the same name no longer share frames.** Two videos called, for example, `IMG_0001.MOV` in different folders were extracted into the same folder, so one video's frames were deleted or replaced with the other's pictures and given the wrong descriptions. Each video now has its own frames folder, in ImageDescriber and in `idt describe` / `idt video`, laid out the same way by both.
- **The open workspace can't be replaced while a batch is using it.** Opening another workspace, starting a new one, loading a folder into a new one, or importing while a batch ran sent the batch's descriptions nowhere. ImageDescriber now says a batch is running instead.

**Failed images in a batch no longer open an error window each**
- Every image that failed during a batch opened its own error window, so a batch with many failures buried the screen in them, one after another. Failures are now counted in the progress window, with the latest error shown there, and the batch's end reports them once: how many failed, the first error, and that **Process → Describe All Undescribed** retries them.
- The save at the end of a batch, and when pausing, now shows its progress instead of freezing ImageDescriber, which on a large workspace could take minutes.

**A batch stops when the AI provider can't be used**
- When Claude Code's sign-in expired partway through a large batch, ImageDescriber kept going and failed every remaining image the same way: 533 images in 17 minutes, with thousands more queued.
- If the provider is signed out, rejects your API key, or isn't set up, the batch now stops at the first such failure. It shows the provider's own message and offers to resume: fix the problem (for Claude Code, run `claude auth login`), then choose **Yes** to carry on with the same images, provider and prompt. Choose **No** to resume later; reopening the workspace offers it. Other failures, such as a single unreadable image or a temporary server error, don't stop the batch.
- A batch also stops when 10 images in a row fail with exactly the same error, which catches a used-up Claude Code plan or Ollama not running. Ten genuinely problem images in a row with an identical error, such as ten too large for the provider, stop it the same way; choosing **Yes** resumes with them still queued.
- For Claude Code, a failed image triggers a check of `claude auth status`, so an expired sign-in is recognised even when Claude Code's message is unclear. Claude Code's own sign-in messages still count too. Apple Intelligence stops a batch only on setup problems it detects itself (wrong Mac, licence not accepted, model switched off), not on a server error that a retry recovers from.

**ImageDescriber saves each description as soon as it is written**
- During a batch, descriptions were kept only in memory until the whole batch finished. Nothing reached the workspace on disk unless you pressed Save, so a crash, power loss or forced quit partway through a long run lost every description since the last save.
- Each image's description is now written to the workspace as soon as that image finishes, on a background thread so the batch isn't slowed. The batch's progress is saved every 25 images or 30 seconds, and when you pause, so reopening the workspace after a crash offers to resume at the first image not yet described.
- The same applies to Process Image and follow-up questions: their results are on disk straight away, so answering **Don't Save** when closing no longer discards them.
- A manual Save or Save As during a batch can no longer overwrite, or leave out, a description that finished while it ran.
- Fixed while reviewing this change: when two folders held images with the same filename, saving one could write its description into the other's file, replacing that image's description.

**ImageDescriber on macOS fully shows a described image when you select it**
- On a Mac, selecting an image that had descriptions filled the description list but quietly skipped everything after it: the description editor and its details weren't updated. Building the Windows-only screen-reader helper for that list raised an error on macOS, and wx hid the error. The list now skips that helper on macOS, as the other controls already did.

**Apple Intelligence retries when its model manager drops a request (#334)**
- Apple's on-device model occasionally fails to load for a single request, reporting `ModelManagerServices.ModelManagerError error 1001` as an HTTP 500 — indistinguishable in shape from a safety refusal, which is permanent. This one is not: measured twice in a 90-image run, and both images described fine on a retry.
- Anything the provider did not specifically recognise was classified as permanent, so each of those images was lost to a failure that fixes itself. Model-manager failures are now marked retryable and retried, and the retry count went from one to two because an attempt against a local model costs seconds.
- Retryability is decided by the status code the provider sets, not by matching the wording of a user-facing message. Matching wording is how this class of bug returns.

**`idt describe --provider claude-code` warns about a foreign default model (#335)**
- `default_model` is a single global setting while `--provider` is chosen per run, so a machine whose default is an Ollama model sent that name to Claude Code, which refused every image with a message about model catalogs.
- It now warns once, before the run, naming the model, Claude Code's actual options, and where the value came from. The model is still sent: Claude Code accepts full model ids and new names as they ship, so substituting one could silently run a cheaper model than asked for.

**ImageDescriber starts after an in-app update on Windows (#338)**
- After updating from inside ImageDescriber, leaving **Launch ImageDescriber** checked on Setup's last page showed "Security validation failure: unexpected name of application's home directory!" and the app did not open. Starting it by hand worked.
- The updater launched Setup with the running app's PyInstaller bootloader variables (`_PYI_*`) still in its environment, and Setup passed them on to the new ImageDescriber, whose bootloader rejected them. The optional CLI console Setup can open inherited them too.
- The updater now drops those variables and sets `PYINSTALLER_RESET_ENVIRONMENT=1` for the launch. The fix is in the app being updated *from*, so the update to 4.6.1 itself can still show the message once; updates from 4.6.1 onward will not. Clean installs were never affected.


## [4.6.0] - 2026-09-25

### ✨ New Features

**Apple Intelligence — descriptions that never leave your Mac (issue #324)**
- New provider `apple`, shown as **Apple Intelligence**, runs Apple's on-device model on macOS 27. No API key, no account, no network, and no cost however many images you describe.
- Available in `idt describe`/`download`/`video`/`watch`, `idt chat`, `idt models`, `guideme`, ImageDescriber (describing, follow-up questions, chat, prompt editor, settings) and IDT Chat.
- Roughly 4–6 seconds per image once warm; the first image of a run also pays for starting the on-device model, and ImageDescriber says so in the progress dialog.
- Requires macOS 27 on Apple Silicon, Apple Intelligence switched on, and a one-time `sudo fm license` — machine-wide, needs an administrator, and cannot be done for you. IDT detects each of those and says which one is missing rather than failing opaquely. The provider is hidden entirely on machines that cannot run it.
- One model, `system`. Apple's Private Cloud Compute model is not offered: it refuses any process that is not Terminal, so it would be a picker entry that never works.
- Nothing new to install or bundle — it talks to the `fm` binary macOS already ships, so neither installer grows.
- Its context window is about 4,096 tokens, an order of magnitude under the cloud models. That is ample for describing images but chats reach the limit quickly, and IDT now says so plainly instead of retrying something that cannot succeed.

**Claude Code — Claude on your Pro or Max subscription (#325, #326)**
- New provider `claude-code` runs Claude through the Claude Code app, billed against your existing subscription instead of an API key. Sign in once with `claude auth login`.
- Same reach as above: CLI, ImageDescriber and IDT Chat. Choose `haiku`, `sonnet` or `opus`; the CLI resolves each to the current model of that tier, so the list cannot go stale.
- Measured cost per image is about what the same request costs through the API — roughly 1,850 input tokens for a phone photo — because each request sends the image inline with a short system prompt and no tools, rather than letting Claude Code open the file with its own tooling.
- Refuses to run unless it is signed in to a claude.ai subscription, so it can never quietly bill an API account.
- A measured figure for planning: 103 images used at most about 4% of a five-hour window on a Pro plan.

### 🐛 Bug Fixes

**IDT Chat: attaching more than one photo to a message returned a blank answer (#329)**
- Apple Intelligence answered a single image but came back empty with two or more. The images were sent at full size — 8 to 14 MB each for a phone photo — and the local server closed the connection rather than answering. The failure surfaced as an empty message with "Broken pipe" behind it.
- Chat attachments are now scaled to 1600px before sending, as the OpenAI chat path already did. Two photos that previously failed go from 22 MB to under 1 MB and answer normally.
- Describing images is unaffected and still sends them untouched: it sends one at a time, and the on-device server scales them itself.

**Apple Intelligence says when it has declined an image, instead of showing a server error (#329)**
- The on-device model refuses some pictures. That arrived as `HTTP 500` with a JSON body saying `"type":"server_error"`, which reads as a fault worth retrying. It is neither a fault nor worth retrying.
- It now reads: *Apple Intelligence declined to describe this image: its safety guardrails were triggered. Retrying the same request will not help, but a different prompt style often does.*
- Which style works varies by image, so none is named. `docs/apple-intelligence-safety-refusals.md` records what was measured, including that the shorter prompts — among them `aialttext` and `simple` — are the ones most often refused.

**A configured default model no longer reaches the wrong provider**
- `default_model` is global while `--provider` is chosen per run, so `idt describe --provider apple` on a machine whose default is an Ollama model sent that name to Apple Intelligence and failed on every image. A provider with one fixed model now falls back to its own default.

**Stop sending `temperature` to the Anthropic SDK (#298)**
- The anthropic SDK removed `temperature` in 1.0.0, so passing it raised a `TypeError` before the request was ever sent. `idt chat` now warns that the flag does not apply to Claude rather than dropping it silently.

### 🔧 Maintenance

- `anthropic` requirement raised to `>=1.0.0` (#299), plus dependency sweeps across every requirements file (#290, #293, #297, #320, #322, #323).
- Dependabot updates are grouped and auto-merged when every check passes (#321).

## [4.5.0] - 2026-08-19

### ✨ New Features

**`idt workflow --show-descriptions on` — live description output (issue #115)**
- New flag prints each AI-generated description to the terminal as it is produced.
- Passes through to the `image_describer` subprocess with clean per-image formatting (`--- filename.jpg ---` header).
- Default is `off` (existing behavior unchanged).

**`idt describe` — friendlier alias for `idt workflow`**
- `idt describe <folder>` is now a full alias for `idt workflow`. Every flag, `--help`, and the frozen executable path all work identically.
- Existing `idt workflow` scripts are unaffected.

**`idt redescribe` — top-level shorthand for re-describing with a new model**
- `idt redescribe <workflow_dir>` routes directly to `idt workflow --redescribe`. All workflow flags are supported.

**`idt guideme` — URL support at the image folder prompt**
- In Step 4, you can now enter a website URL instead of a local path. `guideme` downloads images from the page automatically and continues the workflow with the downloaded folder.
- Graceful fallbacks: clear error messages if 0 images are found, or if download dependencies are not installed.

**Downloaded images organized by domain and page title**
- Web downloads now land in a subfolder named `{domain} - {page title} - {timestamp}` inside `downloaded_images/`, making it easy to identify the source at a glance.

**`idt manage-models` — install, remove, and list AI models from the CLI**
- New command supports `list`, `install`, `remove`, `info`, and `recommend` subcommands for managing Ollama models without leaving the terminal.

### ♿ Accessibility

**IDT Chat: VoiceOver now reads the name of every text box, list and picker (macOS)**
- Tabbing to a field on macOS announced its contents but never its label. The labels existed — VoiceOver could find them by exploring — but nothing connected them to the control.
- Cause: wx has no working way to name a control for VoiceOver. `wx.Window.SetAccessible()` raises `NotImplementedError` on macOS (the whole `wx.Accessible` framework is Windows-only), and `SetName()` reaches no NSAccessibility attribute. Measured on wxPython 4.3.1 / wxWidgets 3.3.3: every `wx.TextCtrl`, `wx.ListBox` and `wx.Choice` reported `accessibilityLabel == nil` however it had been named.
- Fixed by setting the name on the native view through NSAccessibility (new `shared/mac_accessibility.py`, ctypes only — no new dependency). Scroll-backed controls are labelled on their `documentView`, which is the element VoiceOver actually lands on.
- Windows is untouched: it keeps `SetName` plus the existing `wx.Accessible` for text controls, and list items still report their own text.

**ImageDescriber: the same naming fix, and 31 accessibility calls that had never done anything**
- `dialogs_wx.set_accessible_name()` called `widget.SetAccessibleName()` behind a `hasattr` guard. **wxPython has no such method** — the guard was always False, so every one of its 31 call sites did nothing, on Windows as much as on macOS. The dialogs looked carefully labelled and were not. It now sets the wx name (which NVDA and Narrator read) and the NSAccessibility label. `set_accessible_description()` was dead for the same reason and now becomes the control's macOS accessibility help.
- Every dialog names its controls for VoiceOver as it is shown, through a single hook installed at startup rather than a call at the end of each of nineteen dialogs.
- Controls that carried no name at all are now named: the prompt editor's style, provider, API key, model and prompt-name fields; the Configure dialog's per-setting editor (named for the setting it edits); the viewer's description pane; the file-information and description panes in the image detail dialog.
- ImageDescriber's chat window gains a **Paste Image** button. Ctrl+V was never a route to it on macOS — the main window's Edit menu owns Cmd+V and Cocoa hands it to the focused text control before any key event reaches the dialog — so pasting a screenshot into a chat silently did nothing there.

**Cmd+A opened the Attach Files dialog instead of selecting text (both apps, macOS)**
- In IDT Chat, with focus in the message box, `Cmd+A` opened the file picker. `Cmd+T` ran Stop rather than Token Usage; `Cmd+R` removed an attachment rather than regenerating.
- Cause: wxOSX turns the `&` mnemonic in a control's label into a **Command key equivalent on the native NSButton**. `wxButtonCocoaImpl::SetAcceleratorFromLabel` takes the character after the `&`, lowercases it, and sets the modifier mask to Command. On Windows those ampersands are Alt mnemonics and harmless; on macOS `&Attach Files...` becomes ⌘A. And AppKit offers a key equivalent to the key window's view hierarchy **before** the main menu, so that button outranked a completely correct Edit menu.
- Affected IDT Chat's main window (`&Send`, `S&top`, `&Attach Files...`, `&Remove Attachment`) and its API keys dialog (`&Remove`, `&Save`), plus ImageDescriber's dialogs (`&Browse for Directory...`, `&Embed`, and checkboxes such as `&Search subdirectories recursively` — a `wx.CheckBox` is an NSButton too). ImageDescriber's main window carries no mnemonic labels and was unaffected.
- Fixed by `clear_command_key_equivalents()`, which walks a window and takes back any Command chord a control claimed. It runs for both frames at construction and for every dialog in both apps, and reports what it cleared rather than fixing it silently. Only Command chords are touched: a default button holds Return with no modifier and must keep it, or Enter stops activating it. Windows mnemonics are unchanged.

**Why no test caught that, and what does now**
- The existing tests asserted the menu *table* (`Ctrl+A` is bound to `wx.ID_SELECTALL`) and the handler *routing* (given a focused text control, the command calls `SelectAll`). Both were correct the whole time. The bug lived between them, in AppKit's ordering of window views against the menu bar — a layer nothing tested.
- New `pytest_tests/gui/` tests press chords through Cocoa's own matching: they build an `NSEvent` and offer it to the window and then the menu, in that order. Not `wx.UIActionSimulator`, which posts CGEvents that macOS discards unless the process is trusted for Accessibility — on a runner it would press nothing and pass.
- A headless guard runs on the Windows CI box too: any app whose control labels carry `&` must also reclaim the macOS chords.

**Alt+C opened the attachments list instead of the Chat menu (IDT Chat, Windows)**
- The Windows counterpart of the Cmd+A bug above, and the same shape: a control in the window outranked the menu bar. `Atta&chments` claimed Alt+C, so `&Chat` never opened. `&Conversations` claimed it as well, so the two also fought each other. `Conversation &history` took Alt+H from `&Help` the same way.
- Cause: wx runs a frame's child panel through `IsDialogMessage` before the frame handles `WM_SYSCHAR`, so a panel control answers Alt+letter first. On Windows the menu bar titles and every mnemonic in the window share one namespace, and the window wins.
- The three labels now read `Attachme&nts`, `Conversati&ons` and `Conversation h&istory` — Alt+N, Alt+O and Alt+I. F, E, C, V and H belong to the menu bar; `_build_ui` documents that.

**Nine Alt letters were claimed twice in ImageDescriber's menus**
- A repeated mnemonic inside an open menu is not a shortcut: the letter cycles the highlight between the candidates and waits for Enter. `&Cut` and `&Copy` both answered C, and `&Save Workspace` and `Workspace &Statistics` both answered S.
- The Process menu had four such pairs (C, U, V and R), Descriptions had D, View had I, Tools had I, and the AI Info submenu had O. Relabelled to `Cu&t`, `Workspace S&tatistics`, `Update &Image List`, `Chat &with AI Model`, `Describe Video with &AI`, `Re&name Item`, `Copy Image + Descrip&tion`, `&Find Images`, `AI I&nfo`, `Op&enAI Usage Dashboard` and `P&references`. Three dialogs had the same problem and were fixed with it.
- None of these are accelerator changes: every `Ctrl+` chord in both apps is unchanged.

**The shortcuts are written down, and the gap that hid all of this is closed**
- New `docs/KEYBOARD_SHORTCUTS.md`: every accelerator and every Alt mnemonic in both apps, on both platforms, with the chords the operating systems have already claimed and the rules a new shortcut has to clear.
- `test_menu_shortcuts.py` had covered accelerators and the macOS Command-equivalent trap, but nothing looked at what a `&` does on **Windows** — which is why a letter could be claimed twice, or taken from the menu bar, with every test passing.
- New `pytest_tests/unit/test_mnemonics.py` checks all four: no control takes a menu bar letter, no two controls in a window share one, no menu repeats one, and no dialog repeats one. Source-level, so it runs without a display; the mistake is one you cannot see on a Mac at all, since macOS has no Alt mnemonics.
- `pytest_tests/gui/test_alt_mnemonics_windows.py` builds the real frames and reads the labels off the live widgets, which is the only way to see one the app writes at runtime — the attachments label is rewritten by `_refresh_attachments`, so the mnemonic users actually met came from there and not from the constructor.
- A 22-agent review then checked all 184 shortcuts against the source and found two collisions both test layers had missed, each a shape a naive scan cannot see: `ApiKeysDialog` builds one `&Remove` button **per provider**, so one source string put three live buttons on Alt+R; and `ProcessingOptionsDialog` had the notebook tab `&General` and the checkbox `&Geocode…` on that same page, because a `&` in a page title reaches the native tab control. The button lost its mnemonic (three of them cannot share one) and the checkbox became `Ge&ocode`. `test_mnemonics.py` now counts widgets built in a loop as multiple claims and reads `AddPage` titles.

**ImageDescriber's single-key shortcuts are written down for the first time**
- `on_key_press` binds bare `P`, `R`, `M`, `C`, `F` and `Z`, plus `F2`, `Ctrl+S` and `Ctrl+V`, through `EVT_CHAR_HOOK` — so they run before any menu accelerator, and are suppressed only while a text field has focus. None of them appeared in any documentation.
- Three consequences are now recorded rather than discovered: `F2` and the bare letters are **not** platform-gated, so `F2` renames on macOS even though the menu accelerator is Windows-only; `Ctrl+V` outside a text field pastes a clipboard *image* rather than performing Edit > Paste; and each bare letter costs the workspace tree and description list the first-letter type-ahead navigation they would otherwise give — pressing `C` in the tree opens the chat window instead of jumping to the first item starting with C.
- No behaviour was changed here. The type-ahead cost in particular is a deliberate Qt6-parity choice, and whether to keep it is a product decision, not a bug fix.

**Three tests that read the developer's environment instead of pinning it**
- `test_streaming_does_not_announce_each_chunk` failed on any machine with read-aloud enabled and passed everywhere else. `ChatFrame` calls `SpeechSettings.load()`, so the test inherited whatever the person running it had configured — and `_finish_turn` skips the announcement when speech is on and `speaker.speak()` succeeds, precisely so a response is not read twice. The fixture pins the setting off now, and two new tests cover the other branch explicitly: speech-on suppresses the announcement, and a speech engine that fails still announces.
- The two `ai_providers` model-listing tests failed without the `anthropic` and `openai` SDKs installed, where the provider returns `[]` by design. That reads as a sorting regression rather than a missing dependency, so both now `importorskip` the SDK.

**IDT Chat: the standard Edit menu exists, so macOS text editing keys work at all**
- Cmd+A, Cmd+V, Cmd+X and Cmd+Z did nothing in any text field on macOS, including the API key box — which meant a key could not be pasted in. Cocoa routes `cut:`/`copy:`/`paste:`/`selectAll:`/`undo:` through Edit menu items, and the app had no Edit menu with them.
- Added Undo, Redo, Cut, Copy, Paste and Select All with the standard wx ids. Redo follows the platform: Cmd+Shift+Z on macOS, Ctrl+Y on Windows.

### 🔧 Chat shortcuts no longer take over platform standards

**IDT Chat: Ctrl+C is Copy again**
- `Ctrl+C` was bound application-wide to "copy the selected transcript message", so a selection could not be copied out of the message box or the detail pane on either platform. It is now the standard Copy, falling back to copying the highlighted transcript message when there is no text selection (which is the only useful reading of Copy on a list).
- "Copy Message" remains in the Edit menu without an accelerator; "Copy Whole Conversation" keeps `Ctrl+Shift+C`.

**IDT Chat: accelerators moved off reserved macOS chords**
- `Ctrl+M` → `Ctrl+Shift+M` (Change Model). Cmd+M minimises the window on macOS, and wx puts Minimize on the automatic Window menu.
- `Ctrl+Shift+W` → `Ctrl+Shift+K` (Use Web Search). Cmd+W and Cmd+Shift+W are the close-window family.
- `Ctrl+E` → `Ctrl+Shift+E` (Export Conversation). Cmd+E is "use selection for find"; Cmd+Shift+E is the Mac convention for Export.
- Help > Keyboard Shortcuts is `F1` on Windows and `Cmd+?` on macOS, where F1 is a hardware key. F1 still works on macOS for anyone whose keyboard sends it.
- Settings, About and Quit now use `wx.ID_PREFERENCES`, `wx.ID_ABOUT` and `wx.ID_EXIT`, which is what wires the macOS application menu to their handlers. They no longer spell out `Ctrl+,` and `Ctrl+Q` on macOS, where doing so put two menu items on one chord. Windows keeps both accelerators.
- macOS gains `Cmd+W` (Close Window), which the system offers whether an app implements it or not.
- Help > Keyboard Shortcuts now names the modifier for the platform you are on — "Cmd+N" on macOS instead of "Ctrl+N".

**ImageDescriber: Print, Find Previous and Quit given back to the platform**
- `Ctrl+P` → `Ctrl+Shift+P` (Edit Prompts). Ctrl+P / Cmd+P is Print on both platforms and is pressed reflexively; the app does not print.
- `Ctrl+Shift+G` → `Ctrl+Shift+H` (Export HTML Gallery). Cmd+Shift+G is Find Previous on macOS, and this app has a Find.
- Exit no longer spells out `Ctrl+Q` on macOS, where the application menu already supplies Cmd+Q for the same item — it had been bound twice. Windows keeps `Ctrl+Q`.
- **Undo and Redo added to the Edit menu.** They were absent, which on macOS meant Cmd+Z did nothing in any text field in the application. Redo is Cmd+Shift+Z on macOS, Ctrl+Y on Windows.
- Update Image List is `F5` on Windows and `Cmd+R` on macOS, where F5 is a hardware key. Rename Item gains `F2` on Windows, the standard rename key, which it never had.
- Added: `Ctrl+Shift+S` for Save Workspace As (a standard that was unbound), `Cmd+W` for Close Window on macOS, and a help key for the User Guide — `F1` on Windows, `Cmd+?` on macOS.

**ImageDescriber: cancelling "save your changes?" from File > Exit no longer breaks silently**
- File > Exit was bound straight to the `EVT_CLOSE` handler, which ends by calling `event.CanVeto()`. A menu item delivers a `wx.CommandEvent`, which has no such method, so choosing Exit and then cancelling the unsaved-changes prompt raised `AttributeError` inside the handler — swallowed by wx, as they always are, taking the "cancelled but cannot veto" fallback with it.
- Exit now goes through `Close()`, which posts a real close event.

### 🗑️ Removed

**Florence-2 / HuggingFace provider removed**
- Dropped the local Florence-2 vision provider from both the CLI (`--provider florence`) and the GUI (the `huggingface` provider). Ollama already covers the local, no-API-key use case, and Florence required a ~2 GB `torch` + `transformers` dependency that was never correctly bundled into the Windows executables (the `.spec` files declared `torch`/`transformers` as bare hidden imports without `collect_all`, so a built `idt.exe` failed at runtime with an import error the moment Florence was selected).
- Removed: `idt_core/providers/florence.py`, the GUI `HuggingFaceProvider`, provider wiring in the CLI/guide/config dialogs, the Florence hidden imports from `idt.spec` / `imagedescriber_wx.spec`, the Florence-only dependencies (`transformers`, `torch`, `torchvision`, `einops`, `timm`) from the top-level `requirements.txt`, and `docs/HUGGINGFACE_PROVIDER_GUIDE.md`.
- The macOS-only MLX provider and its `torch`/`transformers` dependencies are unaffected.

### 📚 Documentation

**The user guide now says how to read an embedded description back**
- Embedding shipped without telling anyone where the description ends up. **User Guide → Embedding Descriptions into Images** now covers it for both platforms.
- Windows: switch File Explorer to Details view, tab to the column headers, **Shift+F10**, and turn on **Comments** or **Title** — plus which column each format actually fills, since PNG has no EXIF and only appears under Title.
- macOS: **Cmd+I** for Get Info, Preview's Inspector, Spotlight, `mdls`, and Photos captions. Also states plainly that Finder's **Comments** column is a Spotlight note stored by Finder, *not* the embedded description, so switching it on shows nothing.
- `IMAGE_FORMAT_SUPPORT.md` corrected against measured behavior: it claimed Windows shows no PNG metadata at all (it shows it under Title), and described TIFF as lossless piexif insertion (it was the corrupting path fixed below).

### 🔧 Bug Fixes

**Embedding a description into a TIFF no longer destroys the file**
- `.tif` and `.tiff` were routed to the JPEG writer, which injected a JPEG APP1 segment over the `II*\0` byte-order magic. The result was not a TIFF missing its description — it was a file Pillow, File Explorer and Preview all refused to open. Nothing raised; the embed reported success.
- TIFF now gets its own writer, setting `ImageDescription` (270) and `XPComment` (40092) through Pillow, so the description reaches Explorer's **Title**, **Subject** and **Comments** columns.
- Format dispatch moved into one `_embed_by_format()` helper. An unrecognized extension is copied and left alone rather than being handed to a writer that guesses.
- `pytest_tests/unit/test_embedded_metadata_visibility.py` reads the embedded files back the way each OS does — EXIF UserComment, XMP `dc:description`, PNG chunks, TIFF tags, and on Windows the actual Explorer column values via the shell property system. Seven of its cases fail against the old code.

**`idt guideme` no longer shows MLX as a provider option on Windows (issue #111)**
- MLX (Apple Metal) is now only listed as a provider choice on macOS.
- On Windows and Linux, the provider list is `ollama / openai / claude / huggingface`.
- If MLX is somehow selected on an unsupported platform the existing runtime guard remains intact.

**HuggingFace `HAS_TRANSFORMERS` uninitialized name error (issue #113)**
- `HAS_TRANSFORMERS` was only ever assigned `True` (when imports succeeded) but never
  initialized to `False`. On systems without `transformers`/`torch` installed, calling
  `HuggingFaceProvider().is_available()` raised `NameError` instead of returning `False`.
- Fixed by initializing `HAS_TRANSFORMERS = False` at module level before the conditional import.
- `guideme` HuggingFace error message improved: explains Florence-2 runs fully offline and
  gives a single copy-paste install command.

**`idt redescribe` fails on URL-downloaded workflows**
- `--redescribe` now uses `descriptions/file_path_mapping.json` as the primary image source when deciding whether a workflow has processed images, fixing the "Source workflow has no processed images" error on URL-downloaded runs. Falls back to directory scanning for older workflows.

**`idt combinedescriptions` — accessibility, comparison, mood, and functional prompt styles unrecognized**
- These four prompt styles were defined in `image_describer_config.json` but absent from the recognition list in `combine_workflow_descriptions.py`, causing them to appear as `unknown` in the CSV output. All four are now recognized correctly.

**`combinedescriptions` model labels wrong when workflow name contains underscores**
- Model labels were derived by splitting the workflow directory name on underscores, which broke when the workflow name prefix was long (e.g. a downloaded URL title). Labels are now read from `workflow_metadata.json` (accurate provider + model fields) and only fall back to directory name parsing for legacy workflows without metadata.

### 🔬 Internal / Developer

**Ollama cloud model retry logic overhauled**
- Two-tier retry: outer empty-response retry (handles intermittent truncated responses from cloud models) wrapping an inner transport/server retry loop. `num_predict` is no longer forwarded to cloud-tagged models to avoid server-side output caps.

**CLI integration test suite — 60 new tests + CI workflow**
- New `pytest_tests/integration/test_idt_cli.py` covers command routing, help contract, aliases, per-command `--help`, and regression guards against removed commands.
- New `.github/workflows/cli-validation.yml` runs the suite on every push and PR to active branches.
- Total passing tests: 311.

---

## [4.1.0] - 2026-01-14

### ✨ Major Updates

**wxPython GUI Migration Complete**
- **Replaced PyQt6 with wxPython**: Cross-platform compatibility (Windows, macOS) improved
- **Enhanced accessibility**: Full WCAG 2.2 AA compliance with screen reader support
- **Improved VoiceOver/NVDA**: Better keyboard navigation and accessible widget implementations
- **Streamlined GUIs**: Simplified interface while maintaining all functionality

**Code Quality Improvements**
- **Eliminated code duplication**: ~190 lines of duplicate code consolidated into shared modules
- **Created 114+ unit tests**: Comprehensive test coverage with 100% pass rate
- **3 new shared utility modules**: `utility_functions.py`, `exif_utils.py`, `window_title_builder.py`
- **Improved frozen mode support**: PyInstaller compatibility validated across all applications

### 🔧 Critical Bug Fixes (31+ Issues)

**Frozen Mode Compatibility (24 CRITICAL)**
- Fixed hardcoded frozen mode checks throughout codebase
- Fixed config file path resolution in frozen executables
- Fixed JSON file loading in frozen mode
- Fixed resource path resolution for PyInstaller bundles
- Enhanced fallback patterns for dev/frozen modes

**Code Quality (7 HIGH)**
- Consolidated EXIF extraction (4 implementations → 1 shared module)
- Consolidated window title building (2 implementations → 1 shared module)
- Removed duplicate utility functions
- Fixed import patterns across all applications
- Improved error handling and logging

### 📦 Build System Enhancements

**Executable Quality**
- All 3 applications build successfully with zero errors
- PyInstaller spec files optimized and verified
- Shared modules properly bundled in all executables
- Configuration files correctly embedded

**Build Artifacts** (Updated v4.2.0)
- `idt.exe` - CLI dispatcher, fully functional
- `Viewer.exe` - Workflow results browser
- `ImageDescriber.exe` - Batch processing GUI with integrated prompt editor and configuration manager (formerly 5 apps, now 3)

### ✅ Testing & Validation

**Comprehensive Testing**
- All 114+ unit tests passing (100% pass rate)
- Code quality review - EXCELLENT across all metrics
- Build testing - All 3 executables compile successfully
- Integration testing - All imports validated
- Frozen mode testing - PyInstaller compatibility verified

**Zero Regressions**
- 100% backward compatibility maintained
- No breaking changes introduced
- All existing workflows continue to work
- All configuration files compatible

### 📚 Documentation Updates

**User Guides**
- Updated installation instructions
- Documented new accessibility features
- Enhanced configuration guide
- Added wxPython-specific notes

**Developer Documentation**
- Documented shared utility modules
- Added frozen mode guidelines
- Updated import patterns documentation
- Included testing methodology

### 🎯 Performance Optimizations

**Code Consolidation Benefits**
- Reduced memory footprint from duplicate code
- Improved maintainability with single source of truth
- Faster development and bug fixes
- Better error handling consistency

**Expected Improvements**
- Startup time: Consolidated code improves efficiency
- Memory usage: Reduced code size in executables
- Maintainability: Single implementations easier to maintain
- Reliability: Consistent behavior across all apps

### ⚙️ Internal Improvements

**Codebase Quality**
- Zero syntax errors in all files
- All imports properly validated
- Comprehensive error handling
- Professional code organization

**Build System**
- Automated build verification
- Consistent PyInstaller configuration
- Optimized spec files
- Streamlined build process

**Repository Management**
- Clean repository structure
- Organized documentation
- Archived deprecated files
- Current status clearly documented

---

## [3.6.0] - 2025-12-04

### 🎯 Major Features

**HuggingFace Provider with Florence-2 Models**
- **Local AI vision models**: Microsoft Florence-2-base and Florence-2-large models
- **Self-contained**: No need to install Ollama or external AI servers
- **Zero cost**: No API keys, no cloud costs
- **Privacy-focused**: All processing happens locally on your hardware
- **Three prompt styles**: Simple, Technical, and Narrative descriptions
- **CLI-only in GUI installer**: Available via command-line to keep installer size reasonable (~100MB vs ~2GB)
- **Comprehensive documentation**: See [HUGGINGFACE_PROVIDER_GUIDE.md](docs/HUGGINGFACE_PROVIDER_GUIDE.md)

**Note**: HuggingFace provider is **not available in ImageDescriber GUI** to avoid bundling 2GB of transformers/PyTorch dependencies. Use CLI commands instead:
```bash
idt describe image.jpg --provider huggingface --model microsoft/Florence-2-base
idt workflow --provider huggingface --model microsoft/Florence-2-base
```

**Redescribe Feature - Workflow Reuse**
- **Re-describe with different AI**: Test multiple models/prompts on identical images
- **Efficient image reuse**: Hardlinks, symlinks, or copy - reuses extracted frames and converted images
- **Model comparison**: Compare Ollama, OpenAI, Claude, and HuggingFace outputs side-by-side
- **Workflow metadata**: Tracks original settings and changes for traceability
- **Design documentation**: [redescribe-feature-design.md](docs/WorkTracking/redescribe-feature-design.md)
- **Example**: `idt workflow --redescribe wf_photos_ollama_llava --provider huggingface --model microsoft/Florence-2-base`

---

## [4.0.0] - 2025-11-18

### ⚠️ Note
This version introduced Florence-2 support under the "ONNX" provider name, which was renamed to "HuggingFace" in v3.6.0 for accuracy.

### 🎯 Major Features

**HuggingFace Provider with Florence-2 Models** (originally named "ONNX" in this version)
- **CPU-only AI vision models**: Microsoft Florence-2-base and Florence-2-large models
- **No GPU required**: Production-ready transformers library execution on any CPU
- **Three prompt styles**: Simple (8 words), Technical (40+ words), Narrative (70+ words)
- **Comprehensive documentation**: See [HUGGINGFACE_PROVIDER_GUIDE.md](docs/HUGGINGFACE_PROVIDER_GUIDE.md)
- **Performance benchmarking**: 8.63s to 145.16s per image depending on model/prompt
- **Production tested**: Validated on 1000+ image workflows

**Redescribe Feature - Workflow Reuse**
- **Re-describe with different AI**: Test multiple models/prompts on identical images
- **Efficient image reuse**: Hardlinks, symlinks, or copy - reuses extracted frames and converted images
- **Model comparison**: Compare Ollama, OpenAI, Claude, and HuggingFace outputs side-by-side
- **Workflow metadata**: Tracks original settings and changes for traceability
- **Design documentation**: [redescribe-feature-design.md](docs/WorkTracking/redescribe-feature-design.md)
- **Example**: `idt workflow --redescribe wf_photos_ollama_llava --provider huggingface --model microsoft/Florence-2-base`

### ��� Critical Bug Fixes

**File Discovery**
- **Fixed uppercase extension handling**: Now correctly finds .PNG, .HEIC, .MOV files (not just lowercase)
- **Impact**: Workflows were missing images with uppercase extensions
- **Root cause**: Windows filesystems can be case-sensitive in some contexts (WSL, network shares)

**Workflow Duplication Prevention**
- **Fixed massive duplication bug**: Workflows were creating 2817 descriptions instead of 1793 (1.6x duplication)
- **Root cause**: Describe step was scanning converted_images/ as a source directory
- **Solution**: Added safety check to skip workflow subdirectories, corrected input directory handling

**Path Resolution**
- **Fixed redescribe WinError 32**: Resolved path comparison failure with relative vs absolute paths
- **Impact**: Redescribe mode failed with "file in use" error
- **Solution**: Use Path().resolve() for absolute path comparison before workflow mode detection

### ���️ Build & Quality Improvements

**Build System**
- **PyInstaller cache cleaning**: All build scripts now clean cache to prevent stale code issues
- **Pre-build validation**: New tools/pre_build_validation.py validates code before building
- **Build reliability**: Significantly reduced "works in dev but not in executable" issues

**Testing**
- **Integration tests**: New test_workflow_file_types.py validates video/image/HEIC handling
- **Unit tests**: New test_workflow_redescribe.py (348 lines) for redescribe feature
- **Total new test coverage**: 529 lines across 3 new test files

**Code Quality**
- **Pre-commit hook**: tools/pre-commit-hook.sh for validation before commits
- **UTF-8 enforcement**: Consistent encoding across all build and validation scripts
- **Better error messages**: Enhanced logging throughout workflow orchestration

### ��� Documentation

**New Documentation**
- **ONNX Provider Guide**: 213-line comprehensive guide with examples and benchmarks
- **Redescribe Design Doc**: 626-line design document with implementation details
- **Florence-2 Analysis**: Performance and quality comparison across 6 model configurations
- **DirectML Experiments**: GPU acceleration research and findings

### ��� Other Improvements

**Workflow Enhancements**
- **Preserve frame subdirectories**: Video frame extraction maintains original structure
- **Enhanced metadata**: Save original (unsanitized) model names in workflow metadata
- **Resume improvements**: Better provider detection when resuming interrupted workflows
- **Guided workflow**: Enhanced Florence-2 model support in interactive mode

**Configuration**
- **Better config loading**: More robust path resolution for PyInstaller executables
- **Command logging**: --provider logged in original command for accurate resume

### ��� Dependencies

**New Dependencies**
- `optimum[onnxruntime]>=1.23.3` - ONNX model optimization
- `onnxruntime>=1.20.1` - ONNX Runtime for model execution
- `transformers>=4.47.1` - Hugging Face transformers for Florence-2
- `torch>=2.5.1` - PyTorch backend for model loading
- Plus 8 additional supporting packages

**Note**: Total installation size increases by ~2-3 GB with PyTorch and ONNX Runtime

### ⚠️ Breaking Changes

None - all changes are backward compatible

### ��� Performance

**Florence-2 Benchmarks** (per image, 5 test images):
- Florence-2-base + Simple: 8.63s (fastest)
- Florence-2-base + Technical: 26.09s (balanced)
- Florence-2-base + Narrative: 73.59s
- Florence-2-large + Simple: 23.81s
- Florence-2-large + Technical: 56.44s
- Florence-2-large + Narrative: 145.16s (highest quality)
- Moondream + Narrative: 17.29s (best quality-per-second)

**Key Finding**: Prompt complexity has 6-8x more impact on speed than model size (2-3x)

### ��� Testing Credits

Extensive testing and bug discovery by Kelly Ford across:
- 6 Florence-2 model configurations
- Case-insensitive file handling validation
- Large-scale duplication detection (1793 image workflow)
- Redescribe feature validation
- Cross-model quality comparison

---

# Changelog

All notable changes to the Image Description Toolkit will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.5.0] - 2025-11-11

### 🌐 New Features

**Web Image Download**
- **Download images from websites**: Process images directly from URLs without manual downloading
- **Simplified interface**: Just use `idt workflow example.com` to download and describe images from any website
- **Smart URL detection**: Automatically recognizes URLs and configures the correct workflow steps
- **BeautifulSoup4 HTML parsing**: Extracts images from `<img>` tags, `<picture>` elements, and direct links
- **Duplicate detection**: MD5 content hashing prevents downloading the same image multiple times
- **Progress tracking**: Real-time progress updates with formatted console output
- **Filtering options**: `--max-images` to limit download count
- **Safe filenames**: Automatically sanitizes filenames for cross-platform compatibility
- **Image validation**: Verifies downloaded files are valid images using PIL/Pillow
- **Rate limiting**: Respectful 0.5s delays between downloads to avoid overwhelming servers

### 📚 Documentation

**New Web Download Guide**
- **[WEB_DOWNLOAD_GUIDE.md](docs/WEB_DOWNLOAD_GUIDE.md)** - Complete guide to downloading images from websites
- Usage examples with various workflow configurations
- Technical details on supported formats and validation
- Troubleshooting section for common issues
- Limitations and legal considerations

**Enhanced User Guide**
- Added web download examples and use cases
- Simplified workflow syntax examples: `idt workflow mywebsite.com`
- Auto-detection behavior documentation

**Updated CLI Reference**
- Complete `--url` parameter documentation
- Web download workflow examples
- Integration with existing workflow steps

### 🔧 Bug Fixes

**Resume Mode**
- Fixed `UnboundLocalError` for `workflow_name_display` variable in `--resume` mode
- Corrected initialization in both code paths (metadata file and directory name fallback)
- Enhanced error handling for resume workflows

### 🛠️ Technical Details

**Dependencies**
- Added `beautifulsoup4>=4.9.0` for HTML parsing
- Updated PyInstaller spec with BeautifulSoup4 support (`collect_all`, hidden imports)
- Maintained backward compatibility with existing requirements

**Build System**
- Updated `final_working.spec` with BeautifulSoup4 data collection
- Tested with both Python development mode and PyInstaller frozen executable
- Verified resource path resolution in both modes

## [3.0.1] - 2025-10-21

### 🚀 Performance Improvements

**Major Ollama Cloud Optimizations**
- **75% faster retry recovery**: Reduced retry delays from [2s, 4s, 8s] to [0.5s, 1s, 2s]
- **90-second request timeout**: Prevents 2+ minute hangs, fail fast and retry sooner
- **Request throttling**: 3-second delays between Ollama requests to reduce server load
- **Better error handling**: Enhanced timeout detection and retry logic
- **Significant improvement**: 40-minute processing reduced to 15-20 minutes for large batches

### 🔧 Fixes

**Release Packaging**
- Fixed idt2.zip regression - now includes all 4 applications correctly
- Updated packaging scripts to include `imagedescriber_v3.0.1.zip`, `install_idt.bat`, and `README.md`
- All distribution packages now complete and tested

**Documentation**
- Comprehensive User Guide updates featuring GUI applications prominently
- Added dedicated sections for GUI ImageDescriber and Prompt Editor
- Updated application overview and use case guidance
- Enhanced troubleshooting for all four applications

### 📚 Documentation

**Enhanced User Guide**
- Featured GUI ImageDescriber and Prompt Editor as top-level applications
- Added comprehensive application comparison and use case guidance
- Updated installation instructions for all four tools
- Enhanced quick reference with application launchers

**Technical Documentation**
- Created detailed GitHub issue for Ollama performance analysis
- Documented root cause analysis of server 500 errors
- Added performance benchmarking data and optimization strategies

## [3.0.0] - 2025-10-20

### 🌟 Major Release - Complete Application Suite

**Four Standalone Applications**
- **CLI Toolkit (`idt.exe`)**: Advanced batch processing and automation
- **GUI ImageDescriber (`imagedescriber.exe`)**: Visual interface for individual images
- **Prompt Editor (`prompt_editor.exe`)**: Design and test custom prompts
- **Results Viewer (`viewer.exe`)**: Browse results and real-time monitoring

**Unified Distribution**
- Single master package (`idt2.zip`) containing all applications
- Automatic installer (`install_idt.bat`) for complete setup
- Cross-architecture support (AMD64 and ARM64 Windows)
- No Python installation required - all executables are standalone

**Enhanced CLI Features**
- Interactive wizard (`idt guideme`) for step-by-step setup
- Workflow naming and organization improvements
- Advanced analysis tools (`combinedescriptions`, `stats`, `contentreview`)
- Real-time results viewing integration
- Comprehensive batch file library for quick model testing

**GUI Applications**
- **ImageDescriber**: Drag-and-drop interface, real-time preview, visual provider setup
- **Prompt Editor**: A/B testing, prompt library management, live preview
- **Results Viewer**: Real-time monitoring, search/filter, accessibility optimized

**Provider Support**
- **Ollama**: Local models with automatic detection and installation helpers
- **OpenAI**: GPT-4o, GPT-4o-mini with cost optimization
- **Claude**: Full Anthropic model support with intelligent retry logic

**Analysis & Export**
- Chronological image sorting by EXIF date (not filename)
- Enhanced CSV/TSV export with metadata preservation
- Statistical analysis and performance benchmarking
- Content quality analysis and readability metrics

## [1.0.0] - 2025-09-02

### Initial Release

This is the first stable release of the Image Description Toolkit, featuring a complete AI-powered pipeline for generating descriptive text from images and videos using local language models via Ollama.

#### 🌟 Major Features

**Unified Workflow System**
- Complete pipeline from video → frames → images → descriptions → HTML reports
- Single command processing: `python workflow.py path/to/media`
- Automatic orchestration of all processing steps
- Timestamped output directories with organized results
- Professional logging with comprehensive statistics

**Comprehensive Model Testing System**
- `comprehensive_test.py` - Advanced model evaluation and comparison
- Automatic discovery of ALL installed Ollama models (including non-vision models)
- Tests every model with every prompt style through complete 4-step workflow
- Multiple report formats: interactive HTML, CSV data, performance statistics, failure analysis
- Data-driven model selection with detailed analytics

**AI-Powered Image Description**
- Support for multiple Ollama models: llava:7b, llama3.2-vision:11b, moondream, gemma2, etc.
- Multiple prompt styles: detailed, concise, artistic, technical, colorful, narrative
- Local processing with complete privacy (no cloud dependencies)
- EXIF data integration (camera settings, GPS, timestamps)
- Memory optimization for large image collections

**Video Frame Extraction**
- Support for MP4, MOV, AVI, MKV formats
- Time-based interval extraction (e.g., every 5 seconds)
- Configurable resolution and quality settings
- Organized frame numbering and folder structure

**Image Format Conversion**
- HEIC/HEIF to JPG conversion for iPhone/iOS photos
- Configurable compression settings
- EXIF metadata preservation
- Batch processing capabilities

**HTML Report Generation**
- Responsive, mobile-friendly web galleries
- Professional styling with clean, modern interface
- Interactive browsing and navigation features
- Side-by-side image and description display

**Qt6 Image Description Viewer**
- Interactive desktop application for viewing results
- Accessibility features and keyboard navigation
- Support for viewing descriptions alongside images
- Professional GUI for non-technical users

#### 🔧 Technical Features

**Configuration System**
- JSON-based configuration files for all components
- Flexible workflow step selection
- Customizable model and prompt settings
- Per-component configuration management

**Robust Error Handling**
- Continues processing despite individual file failures
- Comprehensive error logging and reporting
- Timeout protection for long-running operations
- Detailed failure analysis and troubleshooting information

**Performance Optimization**
- Smart memory management for large collections
- Batch processing optimizations
- Progress tracking with real-time statistics
- Background process support

**Quality Assurance**
- Comprehensive test suite with automated testing
- Model performance benchmarking
- Output validation and verification
- Cross-platform compatibility (Windows, macOS, Linux)

#### 📚 Documentation

**Complete Documentation Suite**
- Comprehensive README with quick start guide
- Detailed testing guide (`TESTING_GUIDE.md`)
- Individual component documentation in `docs/` directory
- Configuration examples and best practices
- Troubleshooting guides and FAQ

**Example Configurations**
- Pre-configured workflows for common use cases
- Model selection guidance based on performance testing
- Prompt optimization recommendations
- Performance tuning guidelines

#### 🧪 Testing & Validation

**Automated Testing Framework**
- Unit tests for all core components
- Integration tests for complete workflow
- Model compatibility testing
- Cross-platform validation

**Comprehensive Model Evaluation**
- Performance benchmarking across all available models
- Quality assessment with visual comparison reports
- Success rate analysis and failure investigation
- Data export for statistical analysis

#### 📦 Dependencies & Requirements

**Core Dependencies**
- Python 3.8+
- Ollama 0.3.0+ (required for AI functionality)
- PyQt6 6.4.0+ (for GUI viewer)
- Pillow 10.0.0+ with HEIF support
- OpenCV 4.8.0+ (for video processing)

**Optional Dependencies**
- tqdm for enhanced progress bars
- pytest for development testing
- numpy for numerical operations

#### 🚀 Getting Started

**Quick Installation**
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Ollama and pull a vision model
ollama pull llava:7b

# 3. Test your setup
cd tests && python run_tests.py

# 4. Find the best model for your images (recommended)
python comprehensive_test.py tests/test_files/images

# 5. Process your first media collection
python workflow.py path/to/your/media/files
```

#### 🎯 Use Cases

**Media Collection Processing**
- Family photo organization with automatic descriptions
- Digital asset management with searchable descriptions
- Content creation workflow automation
- Accessibility enhancement for visual content

**Development & Research**
- AI model comparison and evaluation
- Prompt engineering and optimization
- Performance benchmarking and analysis
- Custom workflow development

**Professional Applications**
- Content management systems integration
- Digital archives and libraries
- Media production workflows
- Accessibility compliance projects

#### 🔮 Future Roadmap

This 1.0 release establishes a solid foundation for future enhancements including:
- Additional AI model integrations
- Enhanced prompt engineering capabilities
- Advanced filtering and search features
- API development for integration projects
- Performance optimizations and scaling improvements

---

**Full Changelog**: https://github.com/TheIdeaPlace/Image-Description-Toolkit/commits/v1.0.0
