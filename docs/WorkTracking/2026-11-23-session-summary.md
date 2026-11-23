# Session summary: 11/23/2026

Reviewed Kelly's full iPhone library run (`iPhoneMacBookAir.idtw`, in OneDrive,
Apple Intelligence, narrative prompt) and fixed what it turned up.
First written on an old local branch from October, then rebuilt on main at 4.9.0
(branch `fix/onedrive-durability-refusal-fallback`) and merged.

## The run

- 6,027 photos and 5,541 frames from 1,342 videos. 11,559 described and 9 failed, all
  of them Apple guardrail refusals. It ran without stopping for 29.5 hours
  (11/22/2026 6:02A to 11/23/2026 11:29A), with no gap of more than 2 minutes.
- Averaged 8.9s per image (median 7.7s). About 450–530 images an hour overnight,
  falling to about 200 an hour on Saturday afternoon.
- About 150 descriptions call the image completely black. The ones spot-checked
  really are black: pocket shots, black screenshots, and the first frames of videos.

## Findings and fixes

1. **The manifest was rebuilt from scratch at the end of the run.** Its `created`
   time was 11/23/2026 11:29A, half a second after the last description, and the
   defaults were the built-in ones (Ollama `gemma4:31b-cloud`, detailed). Cause:
   `Workspace.open()` created a new bundle whenever `manifest.json` wasn't a file
   at that moment, even over a bundle full of descriptions. Why the file looked
   missing is unproven; OneDrive is the likely cause. Fix: `open()` now creates a
   bundle only when the folder has no content. Otherwise it retries for up to 5s,
   also covering a half-written manifest, and then raises `WorkspaceManifestError`.
   It never writes over the existing bundle.
   The sync that copies batch settings into the defaults (`_save_bundle`) was
   already correct and is unchanged.
2. **The run log stopped at hour 3 of 29.** `logs/run_20261122_060216.log` ends at
   9:01A, and its metadata changed at 2:58P while the app was still writing. The
   handle the app kept open was writing to a file OneDrive had replaced. Fix: a
   handler in `idt_core/logger.py` that opens, appends and closes the file for each
   record.
3. **The 9 refusals.** All of them were retried with 7 prompt styles. `technical` and
   `artistic` described all 9. `narrative` described 3 of the 9 on a retry, so even the
   same prompt is not stable. Fix: `describe_with_refusal_fallback` in
   `idt_core/pipeline.py`. A per-image refusal is retried with technical, then
   artistic, keeping the metadata context. The description records the style that
   actually wrote it, and the run log notes it. Custom prompts never fall back. The
   helper is used by both CLI pipelines and by ImageDescriber's `ProcessingWorker`.
   It fires only on a refusal marked `prompt_may_help`, which Apple's two content
   refusals in `idt_core/providers/apple.py` now set. Windows AI takes no prompt, and a
   file problem stays a file problem, so neither falls back. A refusal under every style
   is still a per-image failure, so the refusal streak and the "declined" memory from
   #376 still apply. Both run logs (the GUI batch and the CLI) note each fallback.
   The run-log fix covers both handlers in `open_run_log`, including the one main
   added that copies provider log messages into the run log.
4. **Workspace repaired** (after Kelly quit the app). The 9 failed items were
   described with ImageDescriber's own `ProcessingWorker` and saved through
   `gui_bridge._gui_desc_to_ws`. 8 went through: 2 with narrative, 6 with the technical
   fallback. `od_photo-22931` was refused under every built-in style when converted by
   IDT, but described from a `sips` JPEG of the same file, which keeps the Display P3
   color profile. Its description's metadata says so (`described_from`). So the image
   encoding can tip Apple's filter too; this was not pursued further. Result: 11,568
   described and 0 failed. The original sidecars are backed up under
   `/tmp/idtanalyze/sidecar_backup/`.
5. **Manifest repaired.** The defaults were set to apple/system/narrative and
   `created` to 11/22/2026 6:00A, the bundle folder's own creation time. The
   original is backed up at `/tmp/idtanalyze/manifest.backup.json`.

## Files changed

- `idt_core/workspace.py`: `WorkspaceManifestError`, `_has_bundle_content`,
  `_read_manifest_patiently`, and the change to `Workspace.open`
- `idt_core/logger.py`: `_AppendPerRecordHandler`
- `idt_core/pipeline.py`: the fallback helper, both `_process` methods, and the run log note
- `imagedescriber/workers_wx.py`: the worker uses the helper; the event, metadata and run log record the fallback
- Tests: `pytest_tests/unit/test_run_durability.py` and `test_refusal_fallback_gui.py`
- Docs: `CHANGELOG.md`, `CLAUDE.md`, `docs/apple-intelligence-safety-refusals.md`

## Tests

- On main at 4.9.0, full suite with wxPython (`imagedescriber/.venv`): 3374 passed,
  61 skipped. Root `.venv`: 2483 passed, 485 skipped. The GUI launch smoke test was
  deselected there because that venv has no wx.
- End to end against real Apple Intelligence: the CLI `WorkspacePipeline` with the
  narrative prompt described all 9 refused photos, 5 of them through the technical fallback.
- The root `.venv` has no wxPython, so its GUI launch smoke test fails there no matter what changed.

## Not tested

- The fallback inside a real ImageDescriber GUI batch. It is covered by unit tests
  on the real `ProcessingWorker`, not by a run of the app.
- The OneDrive mechanism itself. Both fixes were tested against simulated file
  replacement and a missing manifest, not against real OneDrive syncing.
- Opening the repaired workspace in the ImageDescriber app.
