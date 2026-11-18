# Image Description Toolkit v4.9.0

**Image Description Toolkit (IDT) writes text descriptions of your images, using AI, in bulk.**

Point it at a folder of photos and it produces a description of each one. Descriptions
can be written for alt text, for cataloging, for making an archive searchable, or for
anyone who needs to know what is in a picture without seeing it.

It runs entirely on your own machine if you want it to. No account, no subscription,
no uploading your photos anywhere.

---

## Download

| File | Platform | What it is |
|---|---|---|
| **`ImageDescriptionToolkitSetup-4.9.0-windows.exe`** | Windows 10/11, 64-bit | **Start here.** Installs all three applications. |
| **`IDT-4.9.0-macos-arm64.dmg`** | macOS, Apple Silicon | **Start here.** Contains all three. |
| `idt-4.9.0-windows-x64.zip` | Windows | Just the command-line tool, no installer |
| `ImageDescriber-4.9.0-windows-x64.zip` | Windows | Just the image GUI, no installer |
| `IDTChat-4.9.0-windows-x64.zip` | Windows | Just the chat client, no installer |
| `idt-4.9.0-macos-arm64.tar.gz` | macOS | Just the command-line tool |
| `SHA256SUMS.txt` | — | Checksums, if you want to verify your download |

No Python, no dependencies. The Windows installer is signed; the macOS build is signed
and notarized by Apple.

The standalone zips are for people who want one tool and no installer. Each holds a
folder: unzip it and run the `.exe` inside, keeping the `-lib` folder next to it. Most
people want the installer, which puts all three on the Start menu.

---

## What changed in 4.9.0

IDT now controls how it asks each AI model for text: how long an answer may be, how much
the model thinks first, and, where a model allows it, temperature and similar settings.
You can leave all of it alone. Every setting starts on **Automatic**, which means IDT's
own choice for the provider and model you picked. The changes below fix problems that came
from IDT not doing this consistently, and add controls for people who want them.

### Claude's newest models, and Haiku 5.5 as the default

- **Claude Haiku 5.5, Sonnet 5.5, Opus 5.5 and Fable 5.2 are in the model lists,** even
  before IDT has asked Anthropic for the current list, and without a network connection.
- **Haiku 5.5 is the new default Claude model.** With the Detailed prompt it cost about
  $1 per 1,000 pictures, against about $13 for Sonnet 5.5, $30 for Opus 5.5 and $55 for
  Fable 5.2. Its descriptions held up well against the more expensive models. Choose
  another model in Configure, or with `--model`, when a picture needs more.
  If you've already chosen a Claude model, IDT keeps using it.
- **Long Claude chats stay affordable.** Claude models now accept far longer
  conversations, but every turn re-sends the whole conversation, so IDT still drops the
  oldest turns once a chat reaches about 160,000 tokens.
- **`idt stats` prices every Claude model correctly.** It showed no cost for the 5.x
  models and charged Opus 4.8 three times its real price.
- **`idt stats` now counts the input for pictures described in ImageDescriber.**
  ImageDescriber didn't save those token counts where `idt stats` reads them, so the
  cost it showed covered only the output. On one real workspace of 6,800 pictures it
  showed $10 where the true figure was $21. Workspaces you already have now report
  correctly, with nothing to redo.

### Descriptions with Ollama thinking models are faster and no longer come back blank

- **Thinking is off for descriptions by default.** Models that reason before they answer
  (the `qwen3-vl` thinking tags, for example) used to reason at length on every picture,
  and the reasoning was thrown away: 60 to 75 percent of what a thinking model produced,
  in measurements on a MacBook Pro M5 Pro. IDT now asks Ollama not to think when it
  describes a picture.
- **Some models think anyway.** None of the `qwen3-vl` thinking tags (2B, 8B and 32B were
  tried) stopped when asked. For those, use the model's `-instruct` tag, such as
  `qwen3-vl:8b-instruct` instead of `qwen3-vl:8b`. When a model keeps thinking after it
  was asked not to, IDT says so once in the run log and suggests the `-instruct` tag.
- **A description that is all reasoning is no longer saved as blank.** In one run,
  `qwen3-vl:2b` produced 13,000 characters of reasoning and no description. IDT now
  tries such a picture once more, and if it is empty again, reports it as a failure.
- **Reasoning never appears in a description.** `<think>` text is removed.
- **The run log records what happened.** Per picture, it notes hidden reasoning and
  descriptions that were cut off at the length limit, plus any setting a provider
  couldn't use.
- **Ollama model pickers in ImageDescriber** mark thinking models "(thinks, slower)",
  and the model description names the installed `-instruct` version when there is one.

### New: Generation settings

- **Tools → Configure Settings → Generation** in ImageDescriber is a new tab with
  per-provider settings. Each provider lists only what it can use:
  - Ollama: thinking, temperature, top p, top k, repeat penalty, output limit.
  - OpenAI: thinking, effort, temperature, top p, output limit.
  - Claude and Claude Code: thinking, effort, output limit.
  - Apple Intelligence and MLX: shown only on a Mac (Apple Intelligence: temperature,
    output limit; MLX: output limit).
- **The command line uses the same saved settings.** `idt describe`, `idt guideme` and
  the other describing commands take `--think`, `--no-think`, `--temperature` and
  `--max-tokens`, which override the saved settings for that run:

```
idt describe C:\Photos --provider ollama --model qwen3-vl:8b-instruct --max-tokens 800
```

- A setting a provider or model can't take is skipped, and the run log says so. If a
  model rejects an optional setting, IDT drops it and sends the request again, and
  remembers that for the model.
- **Thinking menus in both chat windows.** IDT Chat has **Chat → Thinking**, and
  ImageDescriber's chat window has **Session → Thinking** (in the Session button's menu),
  each with Automatic, On and Off. Before, a thinking model always thought in these
  windows, with no way to turn it off. The choice now also reaches Claude, OpenAI
  reasoning models and Claude Code, not only Ollama. Claude and OpenAI reasoning models
  can't switch reasoning off, so Off asks for the least they take: low effort for Claude
  and Claude Code, and for OpenAI `none` on GPT-5.1 and later, `minimal` on the original
  GPT-5 models, `low` on the o-series.

### Fixed

- **Settings changed in Configure now take effect on an installed Windows copy.** They
  were saved to your settings folder, but processing and the command line read the copy
  installed beside the app first, so nothing you changed in Configure was used, including
  everything on the new Generation tab. Your saved settings now come first; anything they
  don't cover comes from the installed defaults. If you saved settings in Configure in an
  earlier version, they take effect now. One exception: a saved default model of
  `moondream`, IDT's default before June 2026, gives way to the current default once. The
  Prompt Editor and File → Import Configuration save to the same place, and Export
  Configuration exports the settings in use.
- **Thinking On no longer breaks models that can't think.** Ollama's Thinking setting
  applies to every Ollama model, and with it On, a model that can't think (moondream, for
  one) failed on every picture. On is now sent only to models that can think; the run log
  says when it was left out, and the chat windows tell you when you choose it. With Claude
  Haiku 4.5, which doesn't take the newer kind of thinking, Thinking On now uses a thinking
  budget instead of being dropped.
- **`idt describe` now uses an API key saved in Configure.** It only found keys in the
  `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` environment variables, so OpenAI and Claude runs
  failed with "Missing credentials" for a key saved in Configure.
- **Enter on a Configure settings list opens Change Setting,** as the user guide says.
  Only Space did. And the field in Change Setting is read with the setting's name and its
  range, where it was read as just "Value:".
- **A settings file edited by hand and saved with a byte-order mark** (as Windows
  PowerShell 5 does) was ignored as a whole without a word. It's read now, and a settings
  file that can't be read is reported in the log and left as it is.
- **`ImageDescriber <folder>.idtw`** from a command line opens the workspace; it was
  loaded as a folder of pictures.
- **`idt describe` dropped the tag from the default model,** so `moondream:1.8b` became
  `moondream` and every image failed, and `qwen3-vl:8b-instruct` would have become the
  thinking model `qwen3-vl`. The tag is kept.
- **Closing ImageDescriber or IDT Chat on Windows no longer leaves a "Warning" box
  behind.** After the window closed, a box titled "Warning" said *Failed to remove
  temporary directory*, and each close left another `_MEI` folder in your Temp folder.
  Each Windows app now installs as its `.exe` plus a folder of its libraries, which also
  makes them start faster. Folders left in Temp by earlier versions can be deleted when no
  IDT app is running: they are the `_MEI…` folders in `%TEMP%`.
- **Saving a large workspace after a few new descriptions rewrote every picture.** With a
  12,911-picture library, adding two descriptions and pressing Save processed all 12,911.
  A save now writes only the pictures that changed since the workspace was opened or last
  saved, and a save with nothing changed finishes at once, with no progress window.
- **The Process dialog took several seconds to open** (8 to 21 seconds on a Surface
  Laptop). Every request to Ollama went to `localhost`, which Windows tries over IPv6 first;
  Ollama listens on IPv4, so each request waited 2 seconds. IDT now uses `127.0.0.1`, and
  an address you've set to `localhost` is changed the same way. The dialog opens in about
  half a second. If you set Ollama up to listen only on IPv6, set the address to
  `http://[::1]:11434`.
- **The Configure dialog now checks every number you type.** Outside the Generation tab,
  a mistyped number was saved as something else without a word: "abc" became 0 seconds
  for the frame interval, or unlimited for Max frames per video, and 150 for image quality
  became 100. Now a number that can't be used gets a message saying the range to enter,
  and nothing is saved until it can be. Each number field's range is also part of its
  name, so a screen reader reads it when you reach the field. The Extract Video Frames and
  Download dialogs work the same way now; their number boxes used to change an
  out-of-range number to the nearest limit without saying so. The frame interval is 0.5
  to 60 seconds and the scene threshold 1 to 100 in both places, and Download's Maximum
  images is left empty for no limit.
- **Help → About said "Version: 1.0.0".** It shows the real version.
- **Check for Updates without an internet connection read out a Python error.** It now
  says it couldn't reach GitHub and to check your connection. When GitHub is limiting
  checks from your network, it says when to try again.
- **The default provider list offered Apple Intelligence on Windows** (and Windows AI on a
  Mac). Each is now listed only where it can run.
- **`idt describe --provider openai` failed on every image with the default model.** It
  sent `max_tokens`, which `gpt-5.2` and OpenAI's other reasoning models reject ("Use
  'max_completion_tokens' instead"). It now sends `max_completion_tokens`. Checked live
  with `gpt-4o-mini`, `gpt-5-nano`, `gpt-5-mini` and `gpt-5.2`; with thinking off,
  `gpt-5-nano` dropped from 384 reasoning tokens to none and answered twice as fast.
- **ImageDescriber capped most OpenAI models at 300 tokens and Claude at 1,024,** which
  cut detailed descriptions short. Both caps are now 4,096 unless you set another in
  Generation settings, the same as the command line.
- **Claude Opus 5.5 descriptions failed through the Claude API.** Both the command line
  and ImageDescriber read the first part of Claude's reply as the description. Opus 5.5
  always thinks first, so that part is its (empty) reasoning, with no text. They now use
  the text parts. Checked live with Haiku 5.5, Sonnet 5.5, Opus 5.5 and Haiku 4.5.
- **An empty answer from OpenAI or Claude is now an error,** not a saved blank
  description that counted the picture as described. A refusal or content-filter
  decline marks that one picture and the run carries on.
- **The command line's Claude path now shrinks images over Claude's size limit,** as
  Claude Code already did. A large phone photo no longer gets rejected.
- **ImageDescriber made up to 16 attempts on an image that kept failing.** It is now at
  most 8; dropped connections are still retried.
- **Chat no longer sends a temperature to OpenAI reasoning models,** which only accept
  their default.
- **The old temperature, max tokens, top k, top p and repeat penalty entries are gone
  from the Configure dialog.** They changed settings that nothing has read since the
  command line was rewritten in June, so changing them did nothing. The new Generation
  tab replaces them. Values already in your config file are left alone and ignored.
- ImageDescriber now describes with Ollama through the same code the command line uses,
  so the two no longer behave differently. A request that waits out the full 30-minute
  limit isn't retried.

### Smaller changes

- IDT's links, updater and user guide now point at the TheIdeaPlace organization on
  GitHub. Installed copies keep finding updates.

### For screen reader users

- **Models are read by name.** ImageDescriber now says "Model: Claude Haiku 5.5" rather
  than the model's ID, `claude-haiku-5-5`, which screen readers read with its dashes. This
  covers:
  - a description's details;
  - the batch progress window;
  - Properties and Workspace Statistics;
  - the chat window;
  - the Viewer.

  An Ollama model keeps its tag, such as `moondream`, since that is its name. Exported
  files keep the ID, which is also what you type with `--model`.
- **Arrowing along the Configure dialog's tabs reaches every tab.** On Windows each
  press of Left or Right moved two tabs, so after the first pass only half the tabs
  could be reached. One press now moves one tab, and Up and Down move between tabs too.
  Enter on a tab goes to that tab's settings list.
- **Each setting's explanation can be reached with Tab.** In the Configure dialog, Tab
  from the settings list goes to a read-only **Explanation** box for the selected
  setting, which you can read line by line, then to **Change Setting**. Before, the
  explanation was only heard after opening Change Setting. The help paragraphs on the
  API Keys and Workspace tabs are read-only text boxes reachable by Tab as well.
- **Generation settings are a list with a single tab stop,** like the rest of the
  Configure dialog. A number you type that can't be used gets a message box saying what
  to enter, not help text, because JAWS doesn't read help text when a control gets
  focus.
- **The Thinking choices are radio items in a submenu,** in IDT Chat's Chat menu and in
  the Session menu of ImageDescriber's chat window, so which one is chosen is read with
  the item.
- **The Ollama pickers say a model is slow in its name** ("(thinks, slower)"), not only
  by a mark you would have to see.

## From 4.8.1: runs that stop when everything is failing

A maintenance release, mostly for the `idt` command-line tool, from runs over an
11,000-picture iPhone library on a network share with Windows AI. How a batch treats a
video whose frames all fail or are declined, and the 25-refusals stop, change in
ImageDescriber too; the rest is the command-line tool.

- **A run stops when every picture is failing the same way.** If 10 different pictures
  or videos in a row fail with exactly the same error, `idt describe`, `idt guideme` and the other
  describing commands now stop, as ImageDescriber already did. Before, they carried on
  through every picture that was left: when Windows AI stopped responding partway
  through a large batch, each picture waited three minutes to time out, with over
  10,000 still to go. A run also stops at once for a problem nothing else will get
  past, such as the Windows AI helper not being installed, and when the provider
  declines 25 different pictures or videos in a row, which usually means it is
  declining the prompt itself. A few declined pictures don't count toward the 10.
- **One video that fails doesn't stop a run.** Windows AI can fail on every frame of a
  video, such as an iPhone screen recording, while describing everything around it.
  Those frames used to stop a batch, at the same place every time it was run. Now,
  in the command-line tool and in ImageDescriber, a video's frames count as one toward
  the 10. Once 3 frames of a video in a row fail the same way, the rest of that video
  is skipped, and the batch carries on with the next picture. The skipped frames stay
  undescribed. The command-line tool counts them at the end of the run and says how to
  try them again. ImageDescriber marks them as failed, and **Describe All Undescribed**
  tries them again. If the batch stopped because the provider stopped working,
  resuming it tries those frames as well.
- **Declined pictures aren't asked about again.** When Windows AI declines a picture
  ("too much text", or its content filter), asking the same way again gets the same
  answer. Before, every run tried them all again, and since they were still
  undescribed they came first: a rerun over an iPhone library opened with a hundred of
  them. Now the command-line tool remembers which pictures a provider, model and
  prompt declined, leaves them out of later runs, and says how many it left out. A
  picture it couldn't read isn't a refusal, so that is tried again. To ask again, use
  another model (with Windows AI, which takes no prompt, another `--model`), another
  prompt style or provider, or `--redescribe`, which describes every picture again. A
  video whose frames are declined is skipped after 3 of them, as for failures, in the
  command-line tool and ImageDescriber, and next time the command-line tool leaves the
  whole video out.
- **Pictures that failed before are tried last, and failing again doesn't stop the
  run.** In the command-line tool, a picture Windows AI couldn't describe is tried
  again, but only after every picture not yet tried. One that fails again exactly as
  it did before doesn't count toward the 10 that stop a run: a rerun of the iPhone
  library stopped at picture 72 when ten such pictures failed again, though Windows AI
  was working. A timeout always counts, and 30 pictures in a row failing again with
  none described still stop the run, so a provider that gets stuck is caught either
  way.
- **It tells you why it stopped, and how to carry on.** The last line says
  **Stopped.** instead of **Done.** and counts the pictures not tried. Next comes the
  reason, then the exact command to carry on from where it stopped. The window title
  says the run stopped early, and the reason is written to the run log. `idt watch`
  stops only the batch that was failing and keeps watching.
- **Describing a folder again doesn't extract its videos' frames again.** `idt
  describe` and `idt video` read every video again on each run, even when its frames
  were already in the workspace. On a large library on a network share, that was up
  to three hours of extraction before a single picture was described. Now a video
  whose frames are all still there, made with the same options, is skipped, and its
  line says **(already extracted)**. A video is extracted again if it was stopped
  partway, if any of its frames were deleted, if reading it ended early (a network
  share dropping out, say), or if you ask for different options, such as `idt video
  --interval 1` after `--interval 5`. Videos in workspaces made before this version,
  or by ImageDescriber, are extracted once more and skipped from then on.

---

## New in 4.8: Windows AI

**On a Copilot+ PC, IDT can now describe your pictures with Windows' own model, on
the PC itself.** The new Windows AI provider runs on the PC's NPU: no API key, no
account, no internet connection and no cost, and your pictures never leave the PC.
It needs a Copilot+ PC with Windows 11 24H2 or later. On a Snapdragon X Elite a
description takes about two to four seconds.

**Setting it up.** The installer does it: leave **Set up Windows AI** ticked. On a
PC with an NPU it adds a small helper that lets IDT reach Windows' model, and the
Windows App Runtime from Microsoft if the PC doesn't already have it (about 100 MB,
downloaded once). Then `idt models --provider Windows-AI` lists its models, or
says what's missing.

**Its models are kinds of description.** Windows' model takes no prompt. It offers
four kinds of description instead, and those are its models: **accessible** (the
default, a long description written for people who are blind or have low vision),
**detailed**, **brief** and **diagram**. Because there's no prompt, the prompt
style isn't used: ImageDescriber's prompt controls say "not used by Windows AI",
and descriptions record the prompt as "none".

```bash
idt describe C:\Photos --provider Windows-AI
idt describe C:\Photos --provider Windows-AI --model brief
```

**Where it works.** `idt describe` and the other describing commands, `idt guideme`
and ImageDescriber. It isn't offered for chat, follow-up questions or auto-rename,
which all need a prompt.

**When it declines a picture.** Windows declines pictures that are mostly text
(OCR suits those better), and some its content filter stops. Each is marked as
failed and the batch carries on. Windows' model also fails on some pictures at
one size and not another, so IDT tries those again at smaller sizes, and most are
then described.

## From 4.7: videos and batches

**Videos no longer hold up the rest of a batch.** In ImageDescriber, a batch that
includes videos used to extract every video's frames before describing anything:
more than half an hour with a large phone library on a network share. Now the
photos start being described straight away, and each video's frames join the
batch as soon as that video is extracted.

- The progress window shows both at once: how many images have been described
  (the total grows as videos finish) and an **Extracting Frames** line counting
  the videos. While describing waits for the next video, it says so.
- **Stop** stops describing and extraction together. Videos already extracted
  keep their frames; a video stopped partway is extracted again next time.
- **Pause** pauses describing; extraction carries on in the background.
- While videos are still being extracted, the progress bar shows activity rather
  than a percentage, because the total is still growing. Its label says the total
  isn't known yet, and the time-remaining estimate waits until it can be right.

**Quitting partway through keeps what was done.**

- Quitting while a batch was extracting video frames used to lose every video
  already finished, so the next run extracted them all again. Each video is now
  saved as soon as its frames are extracted.
- A batch that stops because the provider refused it (a sign-out, say), or
  because the app was closed, can be resumed, and resuming picks up where it left
  off: it describes what was left while extracting the videos it hadn't reached.
  A batch you stop yourself isn't offered for resume; **Process → Describe All
  Undescribed** carries on from where it got to.

**Apple Intelligence declining a few photos no longer stops a batch.** Apple's
on-device model declines some ordinary photos. Each one is counted as a failure,
but a run of similar photos no longer looks like the provider has stopped working.
If 25 photos in a row are declined, the batch stops and asks whether to carry on,
because that many usually means the prompt itself is being declined. The declined
photos stay marked as failed; a different prompt style often describes them.

**"Embed description after processing" applies to each batch.** A resumed batch
embeds as the original did. Photos downloaded from a web page and video frames
processed straight after extraction now follow the checkbox; before, they were
never embedded.

**For screen reader users**

- In the progress window, the line you're reading stays selected when lines above
  it appear or disappear, for example when extraction finishes.
- Stopping a batch, or quitting and then cancelling, gives one "Batch processing
  stopped" message. If the batch has to wait for a video to be released first, the
  progress window says "Stopping" in its title, with focus on that line, until it
  has stopped.
- The window title doesn't show a misleading percentage while videos are still
  being extracted.

**Smaller fixes**

- The statistics in the progress window count failures the same way as its
  summary. They could read "Failed: 3" above "4 failed".
- Choosing **Yes** to resume a stopped batch works even while a video is still
  being released; the batch resumes as soon as it can, and the progress window
  says so meanwhile.
- If videos give no frames, ImageDescriber says frames couldn't be extracted
  instead of "All images already have descriptions."
- A new batch no longer inherits queued images from an older stopped batch.

---

## New in 4.6: descriptions that never leave your Mac

macOS 27 includes an AI model that runs on the machine itself, and IDT can now use
it. Pick **Apple Intelligence** as your provider and your photos are described on
your own Mac: no API key, no account, no internet connection, and no cost however
many images you run through it.

It is about four to six seconds an image once it warms up, and what comes back is
real alt text — objects, colours, what is in front of what, laid out left to right —
not a one-line caption.

**What you need**

- A Mac with Apple Silicon running macOS 27 or later.
- Apple Intelligence switched on in **System Settings → Apple Intelligence & Siri**,
  with its model downloaded.
- One command, once per machine, typed by an administrator:

```
sudo fm license
```

That last step is Apple's licence agreement for the on-device model. It applies to
everyone who uses the Mac, so it needs an administrator and IDT cannot do it for you.
Run `idt models --provider apple` afterwards and IDT will tell you whether this Mac is
ready — and if not, which of the three things above is missing. On a Mac that cannot
run it at all, the option is hidden rather than offered and then failing.

**What to expect from it.** It is a small model compared with Claude or GPT. Expect
shorter, plainer descriptions, less interpretation, and less certainty about small
text inside a picture. If you want the most detailed result, use a cloud provider.
If you want something free, fast and completely private, this is the one to reach
for. Every prompt style works with it — `detailed`, `accessibility`, `artistic` and
the rest each change the output the way they do everywhere else.

**It refuses some pictures.** The on-device model declines certain images outright —
IDT says so plainly, and the run carries on to the next one. Retrying the same request
will not help, but a different prompt style often will, and which one is not
predictable: on one photo of a museum taxidermy display, `narrative` and `detailed`
worked on one machine while `accessibility` and `artistic` worked on another. The
shorter styles are refused most often, `aialttext` and `simple` among them, which is
worth knowing if you are generating alt text. `docs/apple-intelligence-safety-refusals.md`
records everything that was measured, and ships a script that reproduces it.

One limit worth knowing: the on-device model holds about 4,096 tokens in total, an
order of magnitude less than the cloud models. That is ample for describing images,
but **chats** reach the limit quickly. When one does, IDT says so and asks you to
start a new conversation rather than silently retrying something that cannot work.

---

## New in 4.6: Claude on the subscription you already pay for

If you have Claude Pro or Max, IDT can now use that subscription instead of an API
key. Choose **Claude Code** as your provider, sign in once, and requests count
against your plan rather than charging an API account.

```
claude auth login
```

Pick `haiku`, `sonnet` or `opus`. Each is an alias the Claude Code app resolves to
the current model of that tier, so the list cannot go stale the way a hardcoded one
does.

**What it costs you.** Not money, but some of your plan's allowance. A measured run
of 103 images used at most about 4% of a five-hour window on a Pro plan. Each image
goes on its own with a short instruction and none of Claude Code's usual extras, so
it costs roughly what the same request would through the API. Describing images
draws on the same allowance as your ordinary Claude conversations, so a long coding
session can use more of it than a folder of photos will.

IDT refuses to use Claude Code if it is signed in any other way — with an API key,
say — because that would bill an API account, which is the opposite of the point.
The provider only appears once Claude Code is installed.

---

## The three applications

IDT is three programs that share everything — the same AI providers, the same
settings, the same files on disk. Use whichever suits the moment; you can start work
in one and finish in another.

**ImageDescriber** — a desktop app. Load a folder, pick a model and a description
style, and watch descriptions appear. Review and edit them, browse your images, ask
follow-up questions about a picture in a chat window, and export when you're done.

**IDT Chat** — a standalone chat client for Ollama, Claude, OpenAI, Claude Code and
Apple Intelligence, built for keyboard and screen reader use. Introduced in 4.5; the
two new providers reach it in this release.

**idt** — a command-line tool for doing the same thing to thousands of files without
supervision, or wiring IDT into a script.

---

## Getting started

### The desktop app

1. Install and launch **ImageDescriber**.
2. **File → Load Directory** (Ctrl+L) and choose a folder of images.
3. Pick a provider and a description style.
4. **Process → Process Undescribed Images (Entire Workspace)**. To do one folder
   at a time instead, use **Process → Process Undescribed in Selected Folder**.

That's the whole loop. If you have no AI provider set up yet, see below — start with
Ollama.

### The chat client

Launch **IDT Chat**, type a message, and press `Enter`. The first message asks which
provider and model you want. With Ollama running it needs no key and no setup.

### The command line

```
idt guideme
```

An interactive wizard that asks what you want, shows you the exact command it would
run, and offers to run it. Made to be read aloud — numbered choices, no spinners, no
ANSI escapes.

Once you know what you want:

```
idt describe ~/Pictures/Vacation/
```

---

## You need an AI provider

IDT does not include an AI model. Choose one:

| Provider | Cost | Runs where | Notes |
|---|---|---|---|
| **[Ollama](https://ollama.com)** | Free | Your machine | **Recommended to start.** Nothing leaves your computer. The Windows installer can set it up for you. |
| **Claude** (Anthropic) | Paid API | Cloud | Highest quality. Needs `ANTHROPIC_API_KEY`. |
| **OpenAI GPT** | Paid API | Cloud | Needs `OPENAI_API_KEY`. |
| **Apple Intelligence** | Free | Your Mac | **New in 4.6.** macOS 27 on Apple Silicon. Nothing leaves the machine. |
| **Claude Code** | Your Claude plan | Cloud | **New in 4.6.** Uses a Pro/Max subscription instead of an API key. |
| **Windows AI** | Free | Your PC | **New in 4.8.** A Copilot+ PC with Windows 11 24H2 or later. Nothing leaves the machine. Describes; can't chat. |
| **MLX** | Free | Your Mac | Apple Silicon only, and **ImageDescriber only** — see below. |

**Why MLX is in ImageDescriber but not IDT Chat.** MLX needs Apple's `mlx` and
`mlx-vlm` libraries, which are large: bundling them into IDT Chat would take it
from about 40 MB to around 350 MB. That is worth paying in ImageDescriber,
where describing a folder of photos locally is the whole point. It is worth
much less in a chat client, because Ollama now runs several models through MLX
on Apple Silicon itself — chatting with Ollama on a Mac already gets you the
Metal acceleration, without a second copy of the libraries. If you specifically
want to chat with an MLX model, ImageDescriber's own chat window offers it. IDT
Chat hides the option rather than listing one that would fail the moment you
picked it.

With Ollama you also need a vision model — `ollama pull minicpm-v4.6` gets you one.
8 GB of RAM is a realistic minimum for local models; cloud providers have no such
requirement.

---

## What it does

**Describes images in bulk.** JPEG, PNG, WebP, TIFF, HEIC/HEIF (iPhone photos), and
more. Point it at a folder and walk away.

**Describes video.** Extracts frames — at a fixed interval, or only where the scene
changes — and describes those.

**Description styles.** Several built in, from one-line alt text to detailed prose,
and you can write your own. The style is the prompt sent to the AI, and editing it is
a first-class feature rather than something buried in a config file.

**Tells the AI where and when the photo was taken.** If an image carries GPS
coordinates and a date, IDT can include them in the prompt, which measurably improves
descriptions. Optionally it will look up the city and state. Off by default; nothing
is sent anywhere unless you turn geocoding on.

**Writes descriptions into the image files.** `idt embed` copies your images and
writes the description into EXIF and XMP metadata, so it travels with the file and
shows up in Windows Explorer, Lightroom, Bridge, and Apple Photos. Your originals are
never modified.

**Downloads images from a web page** and describes them in one pass — useful for
generating alt text for a site.

**Exports** to HTML, CSV, or plain text.

**Chat about an image.** Ask follow-up questions about a specific picture in the
desktop app.

**Watches a folder** and describes new images as they land in it.

---

## Where your work is kept

Everything for a job lives in one folder you name, ending in `.idtw` — for example
`MyTrip.idtw`. It holds copies of your images, their descriptions, any chat sessions,
and anything generated along the way. Move it, back it up, or send it to someone else
and it all comes with you. Both applications read and write the same bundle.

**Your original photos are never moved or modified.**

---

## From 4.5: screen reader and keyboard fixes

Three classes of bug that a sighted spot-check would never surface.

**VoiceOver now reads the name of every field on macOS.** Tabbing to a text box, list
or picker announced its contents but never its label. The labels were there — VoiceOver
could find them by exploring — but nothing connected them to the control. The cause was
that wx has no working way to name a control for VoiceOver: `SetAccessible()` raises
`NotImplementedError` there, and `SetName()` reaches no NSAccessibility attribute. Names
are now set on the native view directly.

Worse, ImageDescriber's own `set_accessible_name()` helper called a wxPython method that
**does not exist**, behind a `hasattr` guard that was therefore always false. All 31 of
its call sites did nothing, on Windows as much as on macOS. The dialogs looked carefully
labelled and were not.

**Keyboard shortcuts no longer take over platform standards.** wx maps every `Ctrl`
accelerator to `Cmd` on macOS, so one shortcut has to clear two sets of conventions.
`Ctrl+M` for Change Model shadowed Minimise; `Ctrl+P` for Edit Prompts sat on Print;
`Ctrl+C` meant "copy the selected message" application-wide, which made `Cmd+C` useless
in every text box. IDT Chat also had no Edit menu at all — and on macOS that menu is
what makes `Cmd+A`, `Cmd+V` and `Cmd+Z` work in *any* text field, so pasting an API key
was impossible.

**A control could outrank the menu bar, on both platforms.** On macOS an `&` in a button
label becomes a Command key equivalent on the native button, and AppKit offers those
before the menu bar: `&Attach Files...` owned `Cmd+A` and opened a file picker instead of
selecting text. On Windows the same ampersands are the `Alt` keys, and a control answers
before the menu — so the attachments list had taken `Alt+C` away from the Chat menu, and
nine letters in ImageDescriber's menus were claimed twice and did nothing on the first
press.

Every accelerator and every `Alt` key in both applications is now written down, per
platform, and checked against the source by the test suite.

---

## From 4.5: embedded descriptions you can actually find, and a TIFF fix

Descriptions can be written into the image files themselves, so they travel with the
photo. The guide explained how to put them in and never said how to get them back out,
which made the whole feature hard to trust: you get a folder of copies and no way to
confirm anything happened.

**The user guide now says where to look**, on both platforms. On Windows: switch File
Explorer to Details view, tab to the column headers, press `Shift+F10`, and turn on
**Comments** or **Title** — then arrowing down the list reads each description along with
its file name. Which column works depends on the format, so the guide spells that out;
PNG has no EXIF at all and only appears under Title. On macOS: `Cmd+I` for Get Info,
Preview's Inspector, Spotlight, `mdls`, or Photos captions. It also warns that Finder's
**Comments** column is a note Finder keeps on the side and *not* the embedded
description — switching it on shows nothing, which looks exactly like a failed embed.

**Embedding into a TIFF used to destroy the file.** `.tif` and `.tiff` were handed to the
JPEG writer, which injected a JPEG segment over the TIFF byte-order magic. The result was
not a TIFF missing its description; it was a file Pillow, Explorer and Preview all refused
to open. Nothing raised an error — the embed reported success and handed back dead files.
TIFF now has its own writer, and multi-page TIFFs keep every page.

Every claim in the new instructions is checked by the test suite against the real thing:
the actual Explorer column values on Windows, and on macOS the ImageIO framework that Get
Info and Preview read through.

---

## Built to be usable without sight

The desktop app is built for screen reader users, not merely checked afterwards.
Controls are labelled, the window title reports progress (`72%, 36 of 50 images
described`) so you can check status without hunting, lists are single tab stops that
read as one coherent line instead of scattered columns, and the CLI wizard is written
to be listened to.

This is the point of the tool, not a feature of it.

The model pickers follow the same rule. When a refreshed list arrives while you are
choosing, IDT does not rebuild the control underneath you — it says so on the status
line and leaves your selection alone.

---

## It tells you when there's an update

IDT notices when a newer version is out.

**ImageDescriber** checks quietly at most once a day and says nothing unless there is
something to report. **Help → Check for Updates...** asks on demand, and **Help →
Automatically Check for Updates** turns the automatic check off. From a terminal,
`idt update` reports the same thing.

When an update exists you get **Download**, **Skip This Version**, or **Later**. On
Windows, Download closes the app and runs the installer, having first verified the
download against the release's published SHA-256. On macOS the disk image is saved to
your Downloads folder and shown in Finder; a disk image can't replace a running app,
so the final drag is yours.

`idt update` reports only — installing is the installer's job, and one installer
updates both applications. The check reads GitHub's public releases list and nothing
else — no account, no telemetry, nothing sent.

---

## Command reference

```
idt guideme     Interactive wizard — start here
idt describe    Describe a folder, a bundle, or paths piped from stdin
idt download    Fetch images from a web page (--describe to describe them)
idt video       Extract video frames and optionally describe them
idt embed       Write descriptions into image metadata (EXIF + XMP)
idt export      HTML, CSV, or text output
idt show        Print descriptions (--json to pipe elsewhere)
idt status      How far along a job is
idt stats       Token usage and cost estimates
idt combine     Merge descriptions across several jobs
idt watch       Monitor a folder and describe new arrivals
idt chat        Chat with a model from the terminal
idt models      What models are available (--refresh, --all)
idt prompts     What description styles exist
idt config      Set your defaults
idt update      Check for a newer release
idt version     Version information
```

`idt <command> --help` for options.

---

## Known limitations

- **In ImageDescriber, File → Save doesn't save chats in a workspace that was already
  saved** ([#403](https://github.com/TheIdeaPlace/Image-Description-Toolkit/issues/403)).
  A chat started or continued there is lost when the workspace is closed. **File → Save
  As** to a new name keeps them.
- **A Claude API key that isn't assigned to a workspace is refused by Anthropic** with a
  message asking for an `anthropic-workspace-id` header, which IDT has no setting for.
  Use a key assigned to a workspace (the Claude Console's default for new keys).
- **macOS builds are Apple Silicon only.** No Intel Mac build is published. Intel
  users can run from source.
- **Work done before v4.5 isn't converted automatically.** Older `wf_…` output
  folders still open in the desktop app: **File → Open Workflow Result (Viewer
  Mode)…** to read one as it is, or **File → Import Workflow (to Workspace)…** to
  bring its descriptions into a `.idtw` bundle.
- **`idt guideme` needs a terminal it can read from.** Run from a script or a pipe,
  it exits immediately with `Error: EOF when reading a line`. Use `idt describe` in
  scripts.
- **A brand-new model's cost and context window are unknown to IDT** until a later
  release records them. It is still usable; `idt stats` may show no cost estimate for
  it, and long conversations are trimmed conservatively.
- **Apple Intelligence declines some images.** Not a fault and not worth retrying;
  try a different prompt style. See the note above.
- **Apple Intelligence holds about 4,096 tokens.** Fine for describing images; short
  for chat. IDT tells you when a conversation has outgrown it.
- **Apple Intelligence needs a one-time `sudo fm license`** run by an administrator.
  It applies to everyone who uses that Mac, and no application can do it for you.
- **Windows AI needs a Copilot+ PC** (one with an NPU) and Windows 11 24H2 or later,
  and IDT installed with the installer. It takes no prompt and can't chat.
- **Windows AI declines some pictures**: mostly-text ones, and some its content
  filter stops. Not worth retrying with Windows AI; another provider (or OCR, for
  text) will do.
- **Windows AI can stop responding partway through a very long batch.** It happened
  twice, after hours of describing: every picture then failed, or waited three minutes
  and timed out. The model runs inside Windows, not in IDT, so IDT can't restart it.
  The run now stops after 10 different pictures or videos in a row fail, which is at
  most about 30 pictures, since only 3 frames of each video are tried. Restarting the
  PC cleared it, after which the run carried on from where it stopped.
- Local models are slower than cloud ones, sometimes much slower, depending on your
  hardware.

---

## Help

- **[User Guide](https://theideaplace.github.io/Image-Description-Toolkit/user-guide.html)** — the full manual
- **[Report an issue](https://github.com/TheIdeaPlace/Image-Description-Toolkit/issues)**
- In the desktop app: **Help → User Guide**

---

## Providers as of this release

Run `idt models` to see exactly what your own API keys give you. As of this release the
models each provider recommends for describing images:

| Provider | Recommended models |
|---|---|
| Claude | `claude-haiku-5-5` (the default), `claude-sonnet-5-5`, `claude-opus-5-5` |
| OpenAI | `gpt-5.2`, `gpt-5.1`, `gpt-5-mini`, `gpt-5-nano`, `o3` |
| Ollama | whatever you've pulled — `idt models --provider ollama` |
| Claude Code | `haiku`, `sonnet`, `opus` — aliases that always point at the current model of each tier |
| Apple Intelligence | `system` — the one on-device model; run `idt models --provider apple` to check this Mac is ready |
| Windows AI | `accessible`, `detailed`, `brief`, `diagram` — the kinds of description; run `idt models --provider Windows-AI` to check this PC is ready |
