# Session summary, 11/20/2026

## What happened

The v4.9.0 release went out at 4:17A. On the M5 Mac, Settings in ImageDescriber said
"Error loading .../Application Support/IDT/image_describer_config.json: [Errno 1]
Operation not permitted". The release and the `v4.9.0` tag were deleted.

## Cause

Not the settings file and not macOS privacy. The window that failed had been open
since 5:16A, running the 11/18 pre-release 4.9.0 build. The release was copied into
`/Applications/IDT` at 5:25A, underneath it, and Settings was opened in that same
window at 5:27A.

The macOS apps are one-file PyInstaller builds: modules not imported at startup are
read later out of the executable. Once it's replaced, the old process reads the new
file at the old offsets, and whatever opens next fails with an unrelated error.
Repeated on purpose (release build swapped in under a running build): "Error launching
Configure Settings: Error -3 while decompressing data: incorrect header check".
Every fresh launch, from Finder or Terminal, worked.

Ruled out along the way: file permissions and extended attributes, sandbox
entitlements (none), Privacy & Security (nothing from IDT listed), environment
variables, the working directory, a file written by another program.

## Changes (branch `fix/macos-settings-eperm-logging`)

- `idt_core/app_replaced.py` (new): `remember()` the executable at startup,
  `replaced()` if it was replaced, moved or deleted since, `notice()` text.
- `shared/wx_common.py`: `show_error`/`show_warning` lead with "quit and reopen" when
  replaced; `watch_for_replacement()` records the executable and shows the notice once
  for an exception no handler caught.
- `imagedescriber/imagedescriber_wx.py`, `chatapp/chat_app_wx.py`: call
  `watch_for_replacement()` at startup. Configure's launch failure is logged with the
  traceback.
- `imagedescriber/configure_dialog.py`: a settings file that can't be loaded is logged
  with the traceback, the message names the file that actually failed, and a macOS
  PermissionError points at Privacy & Security.
- **Cmd+, did nothing** in either app. wxWidgets 3.3 moves `wx.ID_PREFERENCES` to the
  application menu but gives it no key equivalent (read from the NSMenuItem with
  PyObjC: empty without the accelerator, "," with it). Both items now carry `Ctrl+,`.
  Cmd+Q is supplied by wx and still isn't repeated.
- `chatapp/chatapp.spec`, `imagedescriber/imagedescriber_wx.spec`: hidden imports for
  the new module (and `shared.wx_common`, `shared.number_entry` in IDT Chat).
- Tests: `test_app_replaced.py` (new), `test_menu_shortcuts.py` (Settings carries
  Ctrl+,). `docs/KEYBOARD_SHORTCUTS.md`, `CHANGELOG.md`, the 4.9.0 release notes.

## Tests

Full suite in `imagedescriber/.venv` (has wxPython): 3,350 passed, 61 skipped. In the
root `.venv`, one smoke test fails with and without these changes: it has no wxPython,
so ImageDescriber can't start. Spec completeness check: all three apps OK.

## Not tested

- The "quit and reopen" notice in a signed build: pending the CI build.
- Cmd+, in the built apps by keyboard (the fix was checked on the menu item, not by
  pressing the keys).
- Windows. The Windows builds are folders, not one-file exes, and Windows locks a
  running exe, so this failure shouldn't occur there.
