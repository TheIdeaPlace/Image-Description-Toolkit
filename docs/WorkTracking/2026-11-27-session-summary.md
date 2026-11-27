# Session summary: 11/26/2026 and 11/27/2026

Picking up from 11/23/2026 (OneDrive durability, Apple refusal fallback, #511). Two days of
4.9.1 work: the OpenAI shutdowns, the release plan's decisions, and a Windows VM for
NVDA checks.

## Merged

- **#514, OpenAI's 12/11/2026 shutdowns.** GPT-5, GPT-5 mini, GPT-5 nano and o3 moved to
  `RETIRED_MODELS` and `KEPT_FOR_OLD_WORKSPACES`. A 404 with one of them adds "OpenAI has shut
  down …; choose another OpenAI model, such as GPT-6 Luna." GPT-5 pro and o3-pro were never
  offered. The live model list already drops models OpenAI stops listing.
- **#516, release plan 4.9.0 → 5.0.** All recommendations taken except decision 1: the NVDA
  DLL isn't shipped for now, so #409 ships alone. #509 is closed.
- **#515, Dependabot.** Holds the Windows App SDK at 1.x until 5.0. #442 and #512 closed.
- **#519, #493.** After Ctrl+O, focus lands on the image tree. Checked in the VM: with the fix,
  NVDA says "Images:, tree view, pics16, collapsed". Without it, NVDA said nothing.
- **#520, #428.** The Gallery dialog opens on the style choice, with each description in its
  style's screen reader name. The VM check found the first version still read the description
  twice on opening: NVDA reads a dialog's StaticText as dialog text. The line is now drawn on a
  `NoFocusPanel`; re-checked, the dialog opens with just "Export HTML Gallery, dialog" and the
  focused style. Arrowing between styles couldn't be checked: Parallels' key events don't send
  arrow keys.

## Issues and milestones

- 28 issues closed with the plan's evidence. #23 stays open, in 4.12: its flag is still in
  `ai_providers.py`, so the plan's claim that it was gone was wrong.
- Milestones 4.9.1 (due 12/10/2026), 4.9.2, 4.10, 4.11, 4.12, 5.0 (due 12/31/2026) and Later;
  every open issue is in one.
- #410 and #439 left 4.9.1; they wait on the NVDA DLL.
- **#422 moved to 4.12.** Reproduced in the VM: Ctrl+Tab in Configure reads a tab's first
  setting twice, 7–10 ms apart, item only, on most presses. The cause isn't confirmed, so per
  the plan it doesn't hold the release. The evidence and a next step are on the issue.

## Open, for Kelly

- **#517 (#409), batch completion announced.** Rebuilt from #438 without the DLL. Checked in the
  VM: NVDA says "Batch Complete — Review stats then close, dialog … 16/16 images", and Escape
  returns focus to the tree. Waits for Kelly's own ear test.
- **#521 (#465), Markdown in HTML exports.** `idt_core/markdown_html.py`. The exported HTML was
  checked in the VM and is right. Edge renders blank pages in the VM, so the NVDA browse-mode
  check wasn't done.

## The Windows VM

Kelly's Parallels "Windows 11 ARM". Snapshots: 00 baseline, 01 NVDA, 02 Ollama + moondream +
SharpKeys (backtick → Caps Lock; active after the 11/27/2026 restart). Claude drives it with
`prlctl`; the helper scripts are in `~/Parallels/idt-vm-scripts/` on the Mac. The main lesson:
nothing started in the background gets the Windows foreground. Parallels must be the front app
on the Mac, plus a real Alt+Tab sent with `prlctl send-key-event`.

## Tests

Full suite with wxPython on each branch: 3394 to 3424 passed, nothing failing. One flaky timing test (`test_a_slow_open_shows_it_and_closes_it`)
failed once while the Mac was busy, then passed 3 of 3.

## Not tested

- Any of this under JAWS.
- #465 by ear in a browser.
- The backtick → Caps Lock remap by a real key press.
