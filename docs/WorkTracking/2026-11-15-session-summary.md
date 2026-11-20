# Session summary: issue #392, generation settings (11/14–11/15/2026)

## Outcome

Issue #392 fixed in three merged PRs, plus release prep for 4.9.0 (this PR).

| PR | What |
|---|---|
| #393 | `idt_core/generation.py` (`GenerationOptions`, per-provider user settings, CLI flags); Ollama: thinking off for descriptions, settings applied, empty all-reasoning answers retried then raised, `<think>` stripped, truncation and reasoning logged; ImageDescriber describes through idt_core's Ollama provider |
| #394 | OpenAI, Claude, Claude Code, Apple mappings; `note_dropped` / `send_with_fallback`; fixes: CLI OpenAI `max_tokens`, GUI 300-token cap, Claude `content[0]`, blank answers saved, refusals halting runs, CLI Claude image size, 16 attempts per image, OpenAI chat temperature |
| #395 | Configure → Generation tab (per-provider, Automatic everywhere), Chat → Thinking / Session → Thinking, chat thinking for Claude/OpenAI/Claude Code, "(thinks, slower)" picker flags with no network calls, legacy `model_settings` removed |

Then, from Kelly's testing on 11/15:

| PR | What |
|---|---|
| #401 | Configure dialog: Left/Right moved two tabs on Windows (the dialog moved the tab and passed the key to the native control too); Up/Down now move one; Enter reaches the settings list; explanations and help paragraphs are read-only TextCtrls reachable by Tab |
| #402 | Ollama at 127.0.0.1 (`localhost` cost 2 s per request on Windows; Process dialog 21 s → 0.5 s); saves write only changed items (fingerprint record per workspace); Apple/Windows AI offered only on their platform |
| #404 | Windows apps are PyInstaller folder builds (`<App>.exe` + `<app>-lib`): one-file GUIs showed "Failed to remove temporary directory" on close and left `%TEMP%\_MEI*` behind. Standalone downloads are zips. config_loader labels `_MEIPASS` files `bundled` before the exe-folder check (`_MEIPASS` is now inside it) |

Filed: #403 (File → Save never writes chats in an existing bundle; pre-existing).

## Decisions

- Legacy `model_settings` / `prompt_model_settings` stay unread (tuned for 2025 models; `num_predict: 500` truncates current ones). New settings: `"generation"` → provider → setting.
- Ollama descriptions default to thinking off; everything else automatic. Cloud providers send no effort unless asked (Claude Code measured 6–9 s/photo regardless).
- "Thinking off" where reasoning can't be switched off = the least effort the model takes (Claude low; OpenAI none on GPT-5.1+, minimal on original GPT-5, low on o-series, retried at low if rejected).
- Optional parameters a model rejects are dropped and resent, remembered per model (not for bad values).
- ImageDescriber's OpenAI/Claude classes keep their clients but build requests with the idt_core functions.

## Measurements (Surface Laptop 7, Snapdragon X Elite, 32 GB, Ollama 0.40.16, 100% CPU)

`coffee_desk.jpg`, narrative prompt: `qwen3-vl:2b` kept 3,000–13,000 characters of reasoning with `think: false`, and one run with no `think` returned an empty answer; `qwen3-vl:8b` kept thinking with `think: false`; `qwen3-vl:8b-instruct` no thinking, rejects `think: true` with a 400.

## Tests

Full suite 2,424 passed / 47 skipped on Windows; CI green on Windows and macOS for each PR. New: `test_generation_options.py`, `test_provider_options.py`, `test_generation_ui.py`. Live: Ollama (three models) and Claude Code through `idt describe`; a script built the real Configure dialog and IDT Chat window and drove the new controls. Three independent reviews (7, 8, 10 findings), all fixed.

## Not tested

- (Both APIs were tested live later, once Kelly added OpenAI credit: the old `max_tokens` request returns a 400 on `gpt-5.2`; `gpt-4o-mini`, `gpt-5-nano`, `gpt-5-mini` and `gpt-5.2` described with automatic, thinking off and temperature; `gpt-5-nano` reasoning went from 384 tokens to 0 with thinking off; `gpt-5.2` reasons 0 tokens by default, confirming "none" is its default; `o4-mini` is deprecated (404). Claude was tested live once Kelly replaced the key: Haiku 5.5, Sonnet 5.5, Opus 5.5 and Haiku 4.5, automatic / thinking off / on / temperature, all described; Opus 5.5 replies start with a thinking block, confirming the `content[0]` bug. The first key wasn't assigned to a workspace and Anthropic refused it without an `anthropic-workspace-id` header.)
- JAWS / NVDA listening (Kelly is testing), macOS UI.
- Folder builds: checked from CI's artifacts (all three close with no warning and no new `_MEI` folder); not checked with Smart App Control on, where the unsigned libraries in a zip extracted by Explorer might be blocked.
- `test_model_refresh.py::test_concurrent_refreshes_fetch_once` failed once under `-n 4` and passed alone; flaky, unrelated.
