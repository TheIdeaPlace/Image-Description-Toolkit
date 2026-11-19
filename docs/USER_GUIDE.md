# Image Description Toolkit — User Guide

**Version 4.9** · [Report an issue](https://github.com/TheIdeaPlace/Image-Description-Toolkit/issues)

---

## Overview

**Image Description Toolkit (IDT)** is a batch AI-powered tool for generating human-quality text descriptions of images and video frames. It supports accessibility workflows, alt-text authoring, image cataloging, and archival documentation.

IDT includes three standalone applications that share the same AI provider infrastructure:

| Application | What it is | Best for |
|---|---|---|
| **idt** | Command-line tool | Automation, scripting, batch pipelines, server use |
| **ImageDescriber** | Desktop GUI application | Interactive editing, reviewing, visual workflow |
| **IDT Chat** | Accessible chat client | Talking to any supported AI model, about anything |

`idt` and ImageDescriber produce the same workspace bundles (`.idtw`) — a `.idtw` bundle is a **folder** (directory), not a compressed archive. It contains image copies, description sidecars, logs, and reports. You can start a job in the CLI and review results in the GUI—or vice versa.

**IDT Chat is not about images.** It is a general-purpose chat client that happens to ship with an image toolkit, built for keyboard and screen reader use. See [Part 7](#part-7-idt-chat).

### Supported AI Providers

| Provider | CLI name | GUI name | Type | API Key | Available on |
|---|---|---|---|---|---|
| Ollama | `ollama` | `ollama` | Local (its cloud models run on ollama.com) | No | Windows, macOS |
| Anthropic Claude | `anthropic` | `claude` | Cloud | Yes | Windows, macOS |
| OpenAI GPT | `openai` | `openai` | Cloud | Yes | Windows, macOS |
| Claude Code (your Claude subscription) | `claude-code` | `claude-code` | Cloud | No — sign in to Claude Code | Windows, macOS |
| Apple Intelligence (on-device) | `apple` | `apple` | Local | No | macOS 27+, Apple Silicon |
| Windows AI (on-device) | `Windows-AI` | `Windows-AI` | Local | No | Windows 11 24H2+, Copilot+ PC |
| MLX (Apple Silicon) | — | `mlx` | Local | No | ImageDescriber only, macOS Apple Silicon |

---

## Part 1: Getting Started

### System Requirements

**Windows (both tools)**

- Windows 10 or 11 (64-bit)
- 4 GB RAM minimum; 8 GB recommended for local AI models
- Internet connection for cloud AI providers (Claude, GPT)
- Optional: NVIDIA GPU with CUDA for faster local models

**macOS (both tools)**

- Apple Silicon (M1/M2/M3) for the published build; Intel Macs need to build from source
- 8 GB RAM minimum; 16 GB recommended for local AI
- Internet connection for cloud AI providers

**For local Ollama models**

- Ollama installed: [https://ollama.com](https://ollama.com)
- At least one vision model pulled (e.g., `ollama pull minicpm-v4.6`)

**For HEIC/HEIF image support (iPhone photos)**

- Nothing to install with the Windows installer, the macOS disk image or the
  standalone downloads. They include `pillow-heif`, which brings its own decoder,
  so HEIC works out of the box.
- Running from source: `pip install -r requirements.txt` installs `pillow-heif`.

**For video support**

- FFmpeg installed (used for frame extraction and GPS metadata)

### Installation on Windows

**Option 1: The installer (recommended)**

1. Download `ImageDescriptionToolkitSetup-<version>-windows.exe` from the [releases page](https://github.com/TheIdeaPlace/Image-Description-Toolkit/releases).
2. Run it. Windows asks for administrator permission. It installs `idt`, ImageDescriber and IDT Chat in `C:\idt`, and adds them to the Start menu.
3. The installer offers some choices:
   - **Add to PATH**, so `idt` runs from any command prompt. Off by default.
   - **Desktop shortcuts**: one checkbox adds shortcuts for all three apps. Off by default.
   - Installing Ollama and the `minicpm-v4.6` model through winget. Off by default, and offered only when winget is available.
   - **Set up Windows AI**. Offered on Windows 11 24H2 or later (build 26100 and up), and on by default there. On a PC with an NPU it installs IDT's Windows AI helper, first downloading Microsoft's Windows App Runtime (about 100 MB) if the PC doesn't have it. On a PC without an NPU it does nothing. IDT works without it.
4. Start ImageDescriber or IDT Chat from the Start menu. For `idt`, use the Start menu's **Image Description Toolkit (CLI)**, which opens a command prompt in the install folder, or any command prompt if you added it to PATH.

**Option 2: The standalone zips**

If you want one tool without installing anything, download its zip from the releases page: `idt-<version>-windows-x64.zip`, `ImageDescriber-<version>-windows-x64.zip` or `IDTChat-<version>-windows-x64.zip`.

Each zip holds a folder. Inside it is the program, such as `ImageDescriber.exe`, and beside it a folder with the same name ending in `-lib`, such as `imagedescriber-lib`. The program needs that folder: keep the two together, and move or copy the whole folder, never the exe on its own.

1. Unzip it anywhere.
2. Run the exe inside the folder. To run `idt` from any command prompt, add the folder holding `idt.exe` to your `PATH`.

**Option 3: From source**

```bat
git clone https://github.com/TheIdeaPlace/Image-Description-Toolkit.git
cd Image-Description-Toolkit

:: Create virtual environment
python -m venv .winenv
call .winenv\Scripts\activate.bat

:: Install dependencies
pip install -r requirements.txt

:: Run CLI
python cli/main.py describe --help

:: Run GUI
python imagedescriber/imagedescriber_wx.py
```

### Installation on macOS

**Option 1: The disk image (recommended)**

1. Download `IDT-<version>-macos-arm64.dmg` from the [releases page](https://github.com/TheIdeaPlace/Image-Description-Toolkit/releases) and open it.
2. Drag the **IDT** folder to your Applications folder. It holds `ImageDescriber.app`, `IDTChat.app` and the `idt` command-line tool.
3. To run `idt` from any Terminal window, open the IDT folder and run `INSTALL_CLI_TO_PATH.sh`. It copies `idt` to `/usr/local/bin` and asks for your password.

**Option 2: The command-line tool alone**

Download `idt-<version>-macos-arm64.tar.gz`, unpack it, and copy `idt` to `/usr/local/bin`:

```bash
sudo cp idt /usr/local/bin/idt
sudo chmod +x /usr/local/bin/idt
```

**Option 3: From source**

```bash
git clone https://github.com/TheIdeaPlace/Image-Description-Toolkit.git
cd Image-Description-Toolkit

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run CLI
python cli/main.py describe --help

# Run GUI
python imagedescriber/imagedescriber_wx.py
```

### Setting Up API Keys

Claude (through the API) and OpenAI need an API key. Ollama, Claude Code, Apple Intelligence and Windows AI don't. API keys are never stored in your workspace bundles.

**Getting a key**

- Claude: sign up at [console.anthropic.com](https://console.anthropic.com) and create an API key.
- OpenAI: sign up at [platform.openai.com](https://platform.openai.com) and create an API key.

**Saving the key: the easy way**

In ImageDescriber, open **Tools → Configure Settings** (on a Mac, **ImageDescriber → Preferences**) and go to the **API Keys** tab. The list has one row per provider (OpenAI, Claude (Anthropic) and Ollama Web Search), each saying whether a key is set and where it comes from. Arrow to the provider, then choose the button after the list: it reads **Add Key** when that provider has no key and **Replace Key** when it has one. A box for that provider's key opens, titled for example "Add Claude (Anthropic) API Key" or "Replace Claude (Anthropic) API Key", with the cursor already in it; paste the key and press Enter, which chooses OK. The key is saved in Windows Credential Manager or the macOS Keychain. Both ImageDescriber and `idt` use it, so you only enter it once.

**Checking that a key works**

On the same tab, select the provider and choose **Test Key** (Alt+T). It sends one short request with that key and puts the answer in the **Test result** box, which gets the focus: first "Testing your Claude (Anthropic) key...", then, for example, "Your Claude key works. That test cost 0.00038 cents." If something is wrong, the first line says what in a few words (the key wasn't accepted, the account is out of credit, the Claude key isn't in a workspace, too many requests just now, no internet connection) and the lines after it say what to do, followed by the provider's own message. If you replace or delete the key while it is being tested, the box says so and the old key's answer is dropped. For Claude and OpenAI the test is paid for on your account, a small fraction of a cent (it uses each provider's cheapest model). For Ollama Web Search it is one web search, which ollama.com doesn't charge for on its own but counts toward your account's usage limits. Test Key is available only for a provider that has a key.

**Other ways to give IDT a key**

IDT looks in these places, in this order, and uses the first key it finds:

1. An environment variable: `ANTHROPIC_API_KEY` for Claude, `OPENAI_API_KEY` for OpenAI.
   - Windows, permanent: Control Panel → System → Environment Variables → New.
   - Windows, current Command Prompt only: `set ANTHROPIC_API_KEY=sk-ant-...`
   - macOS: add `export ANTHROPIC_API_KEY="sk-ant-..."` to `~/.zshrc`.
2. The key saved through **Configure → API Keys** (Windows Credential Manager or the macOS Keychain).
3. The `api_keys` section of your `image_describer_config.json` settings file. Older versions of ImageDescriber saved keys there, and it is still used on a system with no credential store.
4. A plain text key file, from older versions of IDT: `claude.txt` or `anthropic.txt` for Claude, `openai_api_key.txt` or `openai.txt` for OpenAI. IDT looks for it in the current folder and, for the installed programs, in the folder that holds `idt.exe` or `ImageDescriber.exe`. The file must contain only the key: no label, no second key, nothing else.

Because an environment variable comes first, an old or wrong key in `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` wins over the one saved in Configure. Configure warns you when this happens: after you save a key, it says an environment variable still provides a key for that provider and is used first, and that removing the environment variable lets IDT use the key you saved. The API Keys list also says where each key comes from, such as "set via environment variable".

**Ollama (no key required)**

1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull a vision-capable model:
   ```bash
   ollama pull minicpm-v4.6     # 1.6 GB, excellent on all hardware
   ollama pull llava             # 7 GB, higher quality
   ollama pull moondream:latest  # 1.8 GB, fastest
   ```
3. Ollama runs automatically as a background service once installed.

### Updating IDT

**Let IDT tell you (easiest)**

IDT checks for updates itself. Once a day at most, shortly after ImageDescriber
starts, it quietly asks GitHub whether a newer version exists. If there is nothing
new it says nothing; it only speaks up when there is an update. You can also ask at
any moment with **Help → Check for Updates...**, and turn the automatic check off
with **Help → Automatically Check for Updates** (the manual check still works when
it's off).

When an update is found you get three choices:

| Choice | What happens |
|---|---|
| Download | Fetches the new version (see below) |
| Skip This Version | You are never asked about that particular version again |
| Later | Ask again tomorrow |

- **Windows:** Download fetches the installer, closes ImageDescriber, and runs it.
  Windows asks for administrator permission, because IDT installs to the root of
  your system drive.
- **macOS:** Download saves the disk image to your Downloads folder and shows it in
  Finder. Quit ImageDescriber, then drag the disk image's **IDT** folder to
  Applications, replacing the old one.

**One update covers both tools.** The Windows installer and the macOS disk image each
contain `idt` *and* ImageDescriber, so updating from either one updates both.

From the command line, `idt update` reports your installed version, whether a newer
one exists, and where to get it. It does not install anything itself.

The check reads the public GitHub releases list and nothing else — no account, no
telemetry, no data sent.

**Installing an update by hand**

1. Download the latest installer (Windows) or disk image (macOS) from the [releases page](https://github.com/TheIdeaPlace/Image-Description-Toolkit/releases).
2. Run the installer, or open the disk image and drag its **IDT** folder to Applications, replacing the old one. If you use the standalone Windows downloads instead, unzip the new one and replace the whole old folder, not just the exe: each app's `.exe` needs the `-lib` folder that comes with it.
3. Your existing `.idtw` workspace bundles, your `~/.idt/config.json` command-line settings and your ImageDescriber settings (in `%APPDATA%\IDT` on Windows, `~/Library/Application Support/IDT` on macOS) are kept — no migration needed.

**From source**

```bash
git pull origin main
pip install -r requirements.txt   # pick up any new dependencies
```

If you installed via a virtual environment, activate it first (`.winenv\Scripts\activate.bat` on Windows, `source venv/bin/activate` on macOS).

### Uninstalling IDT

**Pre-built programs**

1. Remove the programs:
   - Windows installer: open **Settings → Apps → Installed apps**, find **Image Description Toolkit** and choose **Uninstall**. Or use **Uninstall Image Description Toolkit** in the Start menu's Image Description Toolkit folder.
   - Windows standalone zips: delete the folder you unzipped.
   - macOS: delete the **IDT** folder from Applications. If you ran `INSTALL_CLI_TO_PATH.sh`, also delete `/usr/local/bin/idt`.
2. To remove configuration and cache data, delete the `~/.idt/` directory:
   - **Windows:** `rmdir /s %USERPROFILE%\.idt`
   - **macOS/Linux:** `rm -rf ~/.idt`
3. To remove ImageDescriber's settings too, delete its settings folder: `%APPDATA%\IDT` on Windows, `~/Library/Application Support/IDT` on macOS. API keys saved through Configure are in Windows Credential Manager or the macOS Keychain, under "Image Description Toolkit"; remove them there, or with **Delete Key** in Configure before you uninstall.
4. Your `.idtw` workspace bundles are not removed — delete them manually if desired.

**From source**

1. Delete the cloned repository folder.
2. Remove the virtual environment folder (`.winenv` on Windows, `venv` on macOS).
3. Delete `~/.idt/` as above.

### Quick Start: Your First Description

**Using the CLI**

```bash
# Describe a folder of images with your default provider:
# Ollama (no API key needed) unless you chose another in Configure or with idt config
idt describe ~/Pictures/Vacation

# With Claude for highest quality
idt describe ~/Pictures/Vacation --provider anthropic --model claude-opus-5-5

# If you've never run idt before, the interactive wizard walks you through everything
idt guideme
```

**Using the GUI**

1. Launch `ImageDescriber` (double-click the app or run `ImageDescriber.exe`).
2. Choose **File → New Workspace** (or press `Ctrl+N`).
3. Choose **File → Load Directory** (`Ctrl+L`) and select your image folder.
4. Choose **Process → Process Undescribed Images (Entire Workspace)**.
5. Select your AI provider and model in the dialog, then click **OK**.
6. Watch the Batch Progress dialog as descriptions are generated.
7. When done, choose **File → Export Descriptions** or **File → Export HTML Gallery**.

---

## Part 2: The idt Command-Line Tool

### How idt Works

`idt` processes images in four automatic steps:

1. **Video extraction** — Any video files are converted to image frames (skippable with `--no-video`).
2. **HEIC conversion** — Apple HEIC/HEIF images are converted to JPEG in memory.
3. **AI description** — Each image is sent to the chosen AI provider.
4. **Output generation** — An HTML report is produced automatically (skippable with `--no-export`).

All results are stored in a workspace bundle (`.idtw` directory). Source images are **never modified**.

### Command Reference

#### idt describe — Generate Descriptions

The primary command. Processes every image in a folder (or workspace) and stores AI-generated descriptions.

```
idt describe <source> [options]
```

**Arguments**

| Argument | Description |
|---|---|
| `<source>` | Folder containing images, a `.idtw` workspace bundle, or `-` to read paths from stdin |

**Provider and Model Options**

- `--provider NAME`: the AI provider. One of `anthropic`, `apple`, `claude-code`, `ollama`, `openai` or `Windows-AI`; `claude` also means `anthropic`, and case doesn't matter.
- `--model NAME`: the model, for example `claude-haiku-5-5`, `gpt-6-luna` or `minicpm-v4.6`.
- `--ollama-host URL`: the Ollama server address. Default `http://127.0.0.1:11434`.

Without `--provider`, `idt describe` uses the first of these:

1. The provider the workspace was last described with, once it has descriptions.
2. A default provider set with `idt config --set default_provider=...`.
3. The default provider in ImageDescriber's Configure. If that is one only ImageDescriber can run, such as MLX, `idt` says so and uses Ollama.
4. Ollama.

Without `--model`, `idt describe` uses the workspace's last model or the configured default model, but only when that model belongs to the provider being used. Otherwise it uses the provider's own default: `claude-haiku-5-5` for Claude, `gpt-6-luna` for OpenAI. Configure's default model is treated as the Ollama model, so it is used only with Ollama. So `--provider anthropic` on its own is enough to switch to Claude.

**Prompt Options**

- `--prompt NAME`: a named prompt style; `idt prompts` lists them. Case doesn't matter. An unknown name stops the command before anything is created, with exit code 2 and the list of prompt names.
- `--prompt-text TEXT`: your own prompt text. It overrides `--prompt`.

Without either, `idt describe` uses the prompt the workspace last used, once it has descriptions. A new workspace uses the default prompt style: the one set with `idt config --set default_prompt_name=...`, else Configure's default prompt style (`narrative` as shipped).

**Generation Settings**

Leave these out and IDT uses sensible defaults for the provider and model you picked, plus anything saved in ImageDescriber's [Generation settings](#generation-settings). A setting the provider or model can't take is skipped, and the run log says so.

| Option | Default | Description |
|---|---|---|
| `--no-think` | — | Ask a reasoning model not to think. Ollama descriptions already don't, unless you change that; for Claude and OpenAI, which can't switch reasoning off, it means the least effort the model takes |
| `--think` | — | Let a reasoning model think before describing (slower). Without either flag, Ollama descriptions don't think and other providers use the model's own default |
| `--temperature F` | The model's own | How varied the wording is, 0 or more |
| `--max-tokens N` | Automatic | Cap on the length of each description, in tokens |

**Metadata and Location**

| Option | Default | Description |
|---|---|---|
| `--no-metadata` | Off | Don't read EXIF data (date, camera, GPS) from the images. `--geocode` then has nothing to work with |
| `--geocode` | Off | Turn GPS coordinates into a place name and add it to the prompt (requires internet; ~1 second per unique location). Without it, nothing from EXIF is added to the prompt |

**Processing Control**

| Option | Default | Description |
|---|---|---|
| `--limit N` | Unlimited | Stop after describing N images (useful for testing). N must be 1 or more; leave it out for no limit |
| `--redescribe` | Off | Re-describe already-described images (adds new description, keeps old ones) |
| `--workspace NAME\|PATH`, `-w` | `<folder name>.idtw` in the workspace root | The workspace bundle to create or use. A bare name goes under the workspace root; a path, or a name ending in `.idtw`, is used as it is (relative to the current folder) |
| `--copy-originals` / `--no-copy-originals` | Off for a new workspace | Copy the pictures into the workspace, or reference them where they are |
| `--no-video` | Off | Skip automatic video frame extraction |
| `--video-interval SECONDS` | 5.0 | Seconds between extracted video frames, 0.5 to 60 |
| `--show-descriptions` | Off | Print each description to the terminal as it's generated |
| `--quiet, -q` | Off | Minimal output; in stdin mode, prints the image's full path, a tab, then the description |
| `--stdin` | Off | Read image paths from stdin. A source argument is still required, so pass `-` as the source instead (`idt describe -`) |
| `--project DIR` | The folder that holds all the paths | In stdin mode, the folder the pictures are treated as belonging to, which names the workspace |
| `--showgui` | Off | Run the describe in ImageDescriber instead of the console: it opens on the folder, starts the batch and shows the progress. Closing ImageDescriber ends the command. Takes a folder of pictures, not a workspace |

**Output Control**

| Option | Default | Description |
|---|---|---|
| `--embed` | Off | Embed descriptions into image metadata copies after processing |
| `--no-export` | Off | Skip automatic HTML report generation |

**Examples**

```bash
# Describe all images in a folder using Claude
idt describe ~/Photos/Trip --provider anthropic --model claude-opus-5-5

# Resume an interrupted job (pass the workspace bundle)
idt describe ~/Photos/Trip.idtw

# Test with first 5 images only
idt describe ~/Photos/Trip --limit 5

# Use a custom prompt
idt describe ~/Photos/Trip --prompt-text "Describe this image for someone who cannot see it."

# Include GPS location in every description
idt describe ~/Photos/Trip --geocode

# Process, then embed descriptions into image copies automatically
idt describe ~/Photos/Trip --embed

# Suppress HTML export (faster for scripting)
idt describe ~/Photos/Trip --no-export --quiet
```

**Exit codes**

A script can tell from the exit code how the run went:

| Code | Meaning |
|---|---|
| `0` | Every picture tried was described, or there was nothing to describe |
| `1` | Nothing was described and at least one picture failed, or the run couldn't start (a missing API key, the provider not reachable) |
| `2` | An option was wrong, such as `--limit 0`; it's refused with a message before anything runs |
| `3` | Some pictures were described and some failed |

Pictures left out on purpose, such as ones a provider declined before or originals no longer on disk, count as neither. A video in the folder whose frames can't be extracted counts as a failure. In stdin mode, a path that doesn't exist counts as a failure. `idt download --describe`, `idt video` and `idt watch` use the same codes; see [Piping and Scripting with idt](#piping-and-scripting-with-idt).

---

#### idt guideme — Interactive Setup Wizard

A screen-reader-friendly step-by-step wizard for first-time users. Guides you through selecting a provider, choosing images, and running your first description job.

```
idt guideme
```

The wizard uses numbered choices throughout, no ANSI codes, and supports pressing `b` to go back one step. When the job completes it offers to open the HTML report.

`idt guideme` takes no options. It uses your saved [Generation settings](#generation-settings); to override them for one run, use `idt describe` with `--think`, `--no-think`, `--temperature` or `--max-tokens`.

---

#### idt download — Download Web Images

Download images from a web page and optionally describe them in one step.

```
idt download <url> [directory] [options]
```

**Arguments**

| Argument | Description |
|---|---|
| `<url>` | Web page URL to scrape for images |
| `[directory]` | Workspace name or path (default: derived from the URL's domain, under the workspace root — see `idt config`) |

**Options**

| Option | Default | Description |
|---|---|---|
| `--max N` | Unlimited | Maximum number of images to download |
| `--min-size WxH` | None | Skip images smaller than this (e.g., `200x200`) |
| `--timeout SECONDS` | 30 | HTTP request timeout |
| `--describe` | Off | Automatically describe downloaded images |
| `--embed` | Off | Embed descriptions after describing (requires `--describe`) |
| `--preserve-alt-text` / `--no-preserve-alt-text` | From config (`preserve_alt_text`, on by default) | Save existing HTML alt text as its own description (model `Website Alt Text`), in addition to any AI-generated one |
| `--redescribe` / `--no-redescribe` | On | With `--describe`, generate an AI description even for images whose alt text was preserved as a description. Turn off to keep alt-text-only images and skip the AI call for them. |
| `--provider`, `--model`, `--prompt`, `--prompt-text` | — | AI options (same as `idt describe`) |
| `--quiet, -q` | Off | Minimal output |

**Where images land:** `idt download` uses the same `.idtw` workspace model as `idt describe` (see [Workspaces (.idtw)](#workspaces-idtw) below) — it never writes into an old-style `.idt` sibling folder. Downloaded images are copied into `<workspace>.idtw/derived/downloads/<page title>-<timestamp>/` and registered as workspace items, so `idt describe`, `idt status`, `idt show`, and the ImageDescriber GUI can all see them. With `[directory]` omitted, the workspace is named after the URL's domain (e.g. `nytimes.com.idtw`) and created under the workspace root (`~/Documents/idt` by default). Running `idt download` against the same site again reuses that same workspace — each run just adds a new timestamped batch — so history accumulates per site instead of scattering across one-off folders. Pass `[directory]` (a bare name or a full path) to target a different or explicitly named workspace, exactly like `idt describe --workspace`. A name with no folder in it goes under the workspace root, and so does one written as `./name`; to put the workspace anywhere else, give a full path.

The command captures the original HTML `alt` attribute from each `<img>` tag alongside the downloaded image. By default (`preserve_alt_text` config, on) that alt text is stored two ways: as prompt context, and (when non-trivial — at least 3 characters and containing a space, to filter out bare filenames) as its own description entry, so it shows up in the workspace history alongside the AI-generated description for comparison.

**Examples**

```bash
# Download all images from a page into my-images.idtw under the workspace root
idt download https://example.com/gallery my-images

# Download and immediately describe, limit to 20 images
idt download https://news-site.com --max 20 --describe --prompt aialttext

# Download, describe, and embed in one pass
idt download https://news-site.com --describe --embed --provider anthropic
```

---

#### idt video — Extract Video Frames

Extract frames from video files, with optional AI description of the frames.

```
idt video <source> [options]
```

**Arguments**

| Argument | Description |
|---|---|
| `<source>` | A video file or directory containing video files |

**Extraction Options** (choose one)

| Option | Default | Description |
|---|---|---|
| `--interval SECONDS` | 5.0 | Extract one frame every N seconds, 0.5 to 60 (good for continuous footage) |
| `--scene THRESHOLD` | — | Scene-change detection (1–100; lower = more sensitive; good for events) |
| `--max-frames N` | Unlimited | Maximum frames to extract per video |

**Description Options**

| Option | Default | Description |
|---|---|---|
| `--describe` | Off | Describe extracted frames |
| `--redescribe` | Off | Describe again frames that already have a description |
| `--provider`, `--model`, `--prompt`, `--prompt-text` | — | AI options, as for [`idt describe`](#idt-describe--generate-descriptions) |
| `--ollama-host URL` | `http://127.0.0.1:11434` | The Ollama server address |
| `--think`, `--no-think`, `--temperature F`, `--max-tokens N` | Automatic | Generation settings, as for `idt describe` |
| `--quiet, -q` | Off | Minimal output |

**Workspace Option**

| Option | Default | Description |
|---|---|---|
| `--workspace NAME\|PATH`, `-w` | Named after the folder you give, or for a single video the folder that holds it, in the workspace root | The workspace to extract into. A bare name goes under the workspace root; a path, or a name ending in `.idtw`, is used as it is (relative to the current folder) |

**Supported video formats:** `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.wmv`, `.mts`, `.m2ts`

**Examples**

```bash
# Extract a frame every 2 seconds from a concert video
idt video concert.mp4 --interval 2

# Extract scene changes only and describe them
idt video birthday.mp4 --scene 30 --describe --provider anthropic

# Extract frames from every video in a folder
idt video ~/Videos --interval 5 --describe
```

---

#### idt embed — Embed into Image Metadata

Copy described images and write AI descriptions into the image metadata so descriptions travel with the file.

```
idt embed <source> [options]
```

| Option | Description |
|---|---|
| `--force` | Re-embed even images already embedded |
| `--dry-run` | Show what would be embedded without writing files |
| `--quiet, -q` | Minimal output |

**Metadata written by file type**

- JPEG: EXIF `UserComment` and XMP `dc:description`.
- PNG: a `tEXt` chunk named "Description", and XMP `dc:description` in an `iTXt` chunk.
- WebP: EXIF `UserComment` only.
- TIFF: the `ImageDescription` tag and the `XPComment` tag.
- HEIC: converted to JPEG first, then the JPEG fields are written.

[Where the Description Is Stored](#where-the-description-is-stored) explains which of these Windows and macOS show.

Embedded copies are saved to `<workspace>/embedded/`. Original source files are **never modified**.

**Examples**

```bash
# Preview what would be embedded
idt embed ~/Photos/Trip --dry-run

# Embed all described images
idt embed ~/Photos/Trip

# Force re-embed even if already done
idt embed ~/Photos/Trip --force
```

---

#### idt export — Generate Reports

Generate an HTML, CSV, or plain-text report from a workspace.

```
idt export <source> [--format {html|csv|txt}] [--quiet]
```

| Format | Description |
|---|---|
| `html` (default) | Accessible HTML report with skip navigation, landmark regions, image thumbnails, and full descriptions. Works without JavaScript. |
| `csv` | Spreadsheet-compatible; one row per described image, holding its active description. Columns: image, subfolder, source\_path, description, model, provider, prompt\_name, created, input\_tokens, output\_tokens, description\_count |
| `txt` | Plain text, with every description of every described image |

The HTML report also shows every description of each image. Only the CSV is limited to the active one; `description_count` says how many the image has.

Reports are saved to `<workspace>.idtw/reports/`, as `descriptions.html`, `descriptions.csv` or `descriptions.txt`. Exporting again replaces the earlier file of that format.

---

#### idt show — Print Descriptions

Print descriptions to the terminal. Useful for piping to other tools.

```
idt show <target> [options]
```

| Option | Description |
|---|---|
| `--json` | Output JSONL (one JSON object per line) |
| `--quiet, -q` | Leave out the "No description found" and "No described images" messages. The descriptions themselves print exactly as without it, with their File, Model and Date lines |

**JSON output fields:** `file`, `source`, `described`, `description`, `model`, `provider`, `timestamp`, `metadata_context`, `metadata`, `alt_text`

**Examples**

```bash
# Show all descriptions in a folder
idt show ~/Photos/Trip

# Output as JSON for piping to jq or Python
idt show ~/Photos/Trip --json | jq '.description'

# Save every description, with its File, Model and Date lines, to a text file
idt show ~/Photos/Trip > descriptions.txt
```

For the description text alone, use `--json` and pick out the `description` field, as in the jq example above.

---

#### idt status — Check Progress

Show how many images have been described in a workspace or folder tree.

```
idt status <directory> [--all] [--json]
```

| Option | Description |
|---|---|
| `--all` | Scan all IDT workspaces under the given directory |
| `--json` | JSON output |

---

#### idt stats — Token Usage and Costs

Summarize token counts and estimated API costs across one or more workspaces.

```
idt stats <source> [--all] [--json]
```

The output shows how many images are described, then a row for each provider and model. Each row gives the number of descriptions, the input and output tokens, and an estimated cost in US dollars, with a total.

- **Every description is counted, including whole-video descriptions.** A picture described twice, say once with Haiku 5.5 and again with Haiku 4.5, appears in both rows, because both were paid for. The progress line counts each picture once.
- **Not counted:**
  - chats, which are kept separately;
  - a web page's alt text saved by `idt download`, which isn't AI output and cost nothing.
- **Costs use the providers' list prices** for Claude and OpenAI models as of this release. They're an estimate; your provider's billing page is the final word.
- **A row without a price says why:**
  - "no charge" for models that run on your computer: Ollama, Windows AI, Apple Intelligence and MLX.
  - "Ollama plan" for Ollama cloud models.
  - "your plan" for Claude Code.
  - "no price" for a model IDT has no price for.
  - "no token data" when none of that model's descriptions recorded token counts.
- **Some descriptions have no token counts:**
  - Windows AI never reports them;
  - descriptions made in ImageDescriber before 4.9 didn't save the input count;
  - descriptions imported from old workflow folders have none.

  When some of a model's descriptions lack counts, its cost reads "at least $…", followed by how many had none, and so does the total.

---

#### idt combine — Merge Multiple Projects

Walk a directory tree, find all IDT workspaces, and merge their descriptions into a single CSV or TSV file.

```
idt combine <directory> [options]
```

| Option | Default | Description |
|---|---|---|
| `--output FILE` | stdout | Output file path |
| `--format {csv\|tsv}` | `csv` | Output format |
| `--sort {date\|file\|timestamp}` | `timestamp` | Sort order |

Each described image gives one row, with its active description. The columns are file, source\_path, workspace, description, model, provider, prompt\_name, timestamp, metadata\_context, input\_tokens, output\_tokens and alt\_text.

What the sorts do:

- `timestamp` sorts by when each description was made.
- `file` sorts by file name.
- `date` does not use the photo's EXIF date. It sorts by the `metadata_context` text, which is the place name `--geocode` added, and by when the description was made for rows without one. So it groups rows by place, alphabetically, rather than by when the photos were taken.

A description can run over several lines, and those line breaks stay inside its field. Programs that read CSV properly, such as Excel or Python's `csv` module, handle that. Line-based tools such as `sort` or `cut` see each line separately.

---

#### idt watch — Continuous Monitoring

Describe undescribed images in a folder, then keep polling for new files.

```
idt watch <directory> [options]
```

| Option | Default | Description |
|---|---|---|
| `--interval SECONDS` | 30 | Polling interval, 1 or more |
| `--workspace NAME\|PATH`, `-w` | Named after the folder, in the workspace root | The workspace to describe into. A bare name goes under the workspace root; a path, or a name ending in `.idtw`, is used as it is (relative to the current folder) |
| `--provider`, `--model`, `--prompt`, `--prompt-text` | — | AI options, as for [`idt describe`](#idt-describe--generate-descriptions) |
| `--ollama-host URL` | `http://127.0.0.1:11434` | The Ollama server address |
| `--think`, `--no-think`, `--temperature F`, `--max-tokens N` | Automatic | Generation settings, as for `idt describe` |
| `--no-metadata` | Off | Don't read EXIF data (date, camera, GPS) from the images |
| `--geocode` | Off | Turn GPS coordinates into a place name and add it to the prompt (requires internet) |
| `--quiet, -q` | Off | Tab-separated output for piping |

Press `Ctrl+C` to stop. Useful for monitoring a downloads folder or a folder receiving uploads.

---

#### idt models — List Available Models

Show which models are available from each provider.

```
idt models [--provider NAME] [--ollama-host URL] [--json] [--refresh] [--all]
```

**Options**

| Option | Description |
|---|---|
| `--provider` | One of `anthropic`, `apple`, `claude-code`, `ollama`, `openai` or `Windows-AI`. Omit it to check them all |
| `--ollama-host URL` | Ollama service address. Default `http://127.0.0.1:11434` |
| `--json` | Machine-readable output |
| `--refresh` | Ignore the cached list and ask the APIs right now |
| `--all` | Include every model the API reports, skipping the filter that hides non-chat OpenAI models (speech, images, embeddings) |

Every provider is asked what *your account* can actually use, rather than showing a list built into the app:

- **Ollama** — queries the running Ollama service.
- **Claude and OpenAI** — query the provider's model list using your API key. The result is cached for 24 hours, so the command is instant after the first run and keeps working with no network. Without an API key you get the built-in list instead.

Models the app has no details for still appear, marked `new — details unknown`. That is deliberate: a model released today shows up today, rather than waiting for the next version of IDT. Token budgeting falls back to a conservative default for those until IDT records the real figures.

Models your account cannot use simply do not appear. Previously they stayed on the list and failed only when you tried to use them.

**Examples**

```bash
idt models
```

```bash
idt models --provider openai --refresh
```

Descriptions and costs come from IDT's own records. When a model is too new for IDT to know about, the row says so rather than guessing.

---

#### idt chat — Talk to a Model

Multi-turn conversation from the terminal. Unrelated to images: this is a general-purpose chat command that happens to share the toolkit's provider setup.

```
idt chat [--provider NAME] [--model ID] [--system TEXT] [--message TEXT]
         [--resume ID] [--list] [--no-save] [--max-tokens N]
         [--temperature F] [--think | --no-think] [--show-thinking] [--quiet]
```

**Options**

| Option | Description |
|---|---|
| `--provider` | Which provider to talk to. See the list below |
| `--model` | Model id. Defaults to the provider's default |
| `--system TEXT` | System prompt for the conversation |
| `--attach PATH` | Attach a file to the first message. Repeat for several. HEIC is converted to JPEG |
| `--message`, `-m` | Send one message and exit instead of going interactive |
| `--resume ID` | Continue a saved conversation |
| `--list` | List saved conversations and exit |
| `--no-save` | Do not write the conversation to disk |
| `--max-tokens N` | Cap the reply length |
| `--temperature F` | Sampling temperature. Skipped for Claude and for OpenAI's reasoning models, which don't take it |
| `--think`, `--no-think` | Turn a reasoning model's thinking on or off. Without either, the model decides. For Claude and OpenAI, off means the least effort the model takes |
| `--show-thinking` | Print the model's thinking to stderr as it arrives. Only Ollama models send their thinking, so with other providers it prints nothing extra |
| `--web-search` | Let the model search the web. Ollama only, and needs a free ollama.com API key in `OLLAMA_API_KEY` |
| `--quiet`, `-q` | Suppress status notes on stderr |

**Providers for `--provider`**

- `ollama`, `claude` (or `anthropic`), `claude-code`, `openai` or `apple`.
- The default is `ollama`, even when `idt config` names another default provider.
- A resumed conversation keeps its own provider unless you give `--provider`.
- Windows AI can't chat.

**Examples**

```bash
idt chat
```

```bash
idt chat --provider claude --system "Answer in one sentence." --message "What is HEIC?"
```

```bash
idt chat --provider ollama --model llava --attach photo.jpg --message "What is in this picture?"
```

```bash
idt chat --list
```

```bash
idt chat --resume chat_a1b2c3d4e5f6
```

Responses stream as they arrive. `Ctrl+C` stops a reply and keeps what arrived; `Ctrl+D` or `/quit` exits. Inside an interactive session, `/system TEXT` sets the system prompt and `/tokens` reports usage.

Conversations are saved to `~/.idt/chats/` in the same format the GUI uses, so they can be opened in [IDT Chat](#part-7-idt-chat).

Ollama needs no API key. Claude and OpenAI read `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, or a key configured in ImageDescriber.

---

#### idt prompts — List Prompt Styles

Print all available prompt names and descriptions.

```
idt prompts [--json]
```

---

#### idt config — User Configuration

View or update default settings.

```
idt config [--set KEY=VALUE]
```

**Valid keys**

| Key | Description |
|---|---|
| `default_provider` | AI provider: `anthropic` (or `claude`), `apple`, `claude-code`, `ollama`, `openai` or `Windows-AI`. Any other name is refused |
| `default_model` | Model name for the provider |
| `default_prompt_name` | Default prompt style. It must be one `idt prompts` lists; case doesn't matter |
| `workspace_root` | Root folder for workspaces (default: `~/Documents/idt`) |
| `preserve_alt_text` | Whether `idt download` saves a web page's alt text as its own description: `true` (the default) or `false` |

`idt config` with no options shows every value. There is no `--get`. After each of the default provider, model and prompt, it says where the value comes from: "(set with idt config)", "(from Configure)" or "(default)". The default model also says "used with Ollama" when it is Configure's model.

**Examples**

```bash
# Show current settings
idt config

# Set Claude as default
idt config --set default_provider=anthropic
idt config --set default_model=claude-haiku-5-5

# Change workspace root
idt config --set workspace_root=~/MyDescriptions
```

Configuration is stored in `~/.idt/config.json` (on Windows, `%USERPROFILE%\.idt\config.json`).

**How this relates to ImageDescriber's settings.** `idt config` has its own settings file, separate from the one ImageDescriber's **Tools → Configure Settings** saves (on a Mac, **ImageDescriber → Preferences**). See the [Configuration Guide](CONFIGURATION_GUIDE.md).

- The file holds only the defaults you set with `idt config --set`. Every default you haven't set follows Configure: its default provider, its default prompt style, and its default model (used with Ollama).
- A default set with `idt config --set` wins over Configure's for the command line. The file lists those defaults under `user_set`. To go back to following Configure, delete the setting and its name in `user_set` from `~/.idt/config.json`.
- A file from before 4.9 has no `user_set`. If its default provider, model and prompt are all values IDT used to ship, IDT treats them as left over and follows Configure. If any of them differs, all three are kept as your choices.
- The workspace root is shared: Configure's **Workspace** tab and `idt config --set workspace_root=...` change the same setting.
- Generation settings (thinking, temperature and so on) and API keys are shared too.
- Prompt styles saved in ImageDescriber's Prompt Editor reach the command line. Custom prompts added to `~/.idt/config.json` work only in `idt`.

---

#### idt version — Display Version

```
idt version
```

Prints the application version, Python version, and executable path. `idt --version` prints just the version. Neither touches
the network — use `idt update` to check for a newer release.

#### idt update — Check for a Newer Release

```
idt update
```

Asks GitHub whether a newer release exists and prints where to get it:

```
Installed: idt 4.5.0
Available: idt 4.5.1

Download:  https://github.com/TheIdeaPlace/Image-Description-Toolkit/releases/download/v4.5.1/ImageDescriptionToolkitSetup-4.5.1-windows.exe
Installing it updates both idt and ImageDescriber.
```

This command is notify-only — it downloads and installs nothing. Run the installer
yourself, or use ImageDescriber's **Help → Check for Updates...**, which can download
and launch it for you. Either way, one installer updates both tools.

If the check fails (no internet, GitHub unreachable) it says so rather than claiming
you are up to date.

---

### Workspaces (.idtw)

A workspace is a folder ending in `.idtw` that holds all job state: description sidecars, logs, reports and, if you ask for them, copies of the images. You never need to edit workspace files directly—both tools manage them automatically.

`idt describe` creates it in the workspace root, `Documents\idt` (`~/Documents/idt` on a Mac), named after the folder you described: describing `C:\Photos\Trip` gives `Documents\idt\Trip.idtw`.

**Copies or references.** By default a workspace references your pictures where they are and doesn't copy them. Pass `--copy-originals` to `idt describe` to copy them into the workspace's `images/` folder instead. Either way your originals are never changed.

**Structure**

```
MyTrip.idtw/
  manifest.json          Job metadata, defaults, CLI command history
  images/                Copies of source images, only with --copy-originals
  descriptions/          JSON sidecars — one per image
  derived/
    converted/           HEIC → JPEG conversions
    frames/              Extracted video frames
  logs/                  Processing logs
  embedded/              Images with embedded metadata (created by idt embed)
  reports/               HTML, CSV, and TXT exports
```

**Resuming an interrupted job**

Pass the `.idtw` bundle path to `idt describe` to continue where you left off:

```bash
idt describe MyTrip.idtw
```

Only undescribed images are processed. Existing descriptions are preserved.

**Sharing workspaces**

A workspace made with `--copy-originals` is self-contained: zip it and share it, and the recipient can open it in ImageDescriber, read its HTML report with the pictures, or run `idt show` on it, without your original folder.

A workspace made the default way holds only the descriptions. The recipient can still read them, with `idt show` or in the HTML report, but the pictures stay on your computer, so the report's images and ImageDescriber's previews won't appear for them.

---

### Metadata and Geocoding

By default, `idt describe` reads EXIF metadata from each image: capture date and time, GPS coordinates, camera make and model, and lens model. IDT shows these to you, and keeps them with each description. While describing, the progress line shows them in brackets, for example `[Munich, Germany  Sep 12, 2024  iPhone 14 Pro]`.

**What the AI is told.** Only the place, and only with `--geocode`. Then the prompt starts with a line like this:

```
Where this photo was taken, from the file's metadata: Munich, Germany
This comes from the file, not the picture, so the picture needn't show it. Use it where it helps, such as to name the place, and don't comment on it or say whether the picture confirms it.

[your prompt text]
```

The date and camera are never sent: models tended to describe the camera instead of the picture, and to open every description by reciting the date. Without `--geocode` there is no place name, so nothing from EXIF is added to the prompt.

**Geocoding** (opt-in with `--geocode`) reverses GPS coordinates to a human-readable place name using OpenStreetMap Nominatim. It requires an internet connection and adds approximately one second per unique location. Results are cached in `~/.idt/geocode_cache.json`.

To disable all metadata extraction: `--no-metadata`.

---

### Environment Variables

| Variable | Used by | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | idt, GUI | Anthropic Claude API key |
| `OPENAI_API_KEY` | idt, GUI | OpenAI API key |
| `IDT_USER_CONFIG_DIR` | idt, GUI | Use this folder for your settings instead of the usual one (`%APPDATA%\IDT` on Windows, `~/Library/Application Support/IDT` on macOS). Configure and the Prompt Editor save there, and it's read first. |
| `IDT_CONFIG_DIR` | idt, GUI | A folder of default settings, used for anything your own settings don't set |

---

## Part 3: The ImageDescriber GUI

### Application Overview

ImageDescriber is a wxPython desktop application for interactively managing image descriptions. It shares the same workspace format as the CLI, so you can freely mix both tools.

The application has two modes:

- **Editor Mode** — Create workspaces, add images, process descriptions, and export results.
- **Viewer Mode** — Read-only list of every description in the open workspace (or in an older, pre-4.5 workflow folder). See [Viewer Mode](#viewer-mode).

### Menu Reference

#### File Menu

| Item | Shortcut | Description |
|---|---|---|
| New Workspace | Ctrl+N | Create a new empty workspace |
| Open Workspace (.idtw)... | Ctrl+O | Open a saved workspace bundle |
| Save Workspace | Ctrl+S | Save the current workspace |
| Save Workspace As... | Ctrl+Shift+S | Save with a new name |
| Load Directory | Ctrl+L | Add images from a folder |
| Refresh Folder from Disk... | Ctrl+Shift+R | Rescan a folder for new or missing files. Available when a folder is selected in the image list |
| Load Images From URL... | Ctrl+U | Download and import images from a web page |
| Import Workflow (to Workspace)... | — | Bring the descriptions from an older (before version 4.5) `wf_…` workflow folder into the workspace |
| Export Descriptions... | — | Save descriptions as text or HTML |
| Embed Descriptions into Images... | — | Write descriptions into image metadata |
| Export HTML Gallery... | Ctrl+Shift+H | Create an interactive HTML image gallery |
| Workspace Statistics... | Ctrl+I | Show statistics: counts, tokens, costs, providers |
| Open Workflow Result (Viewer Mode)... | — | Read an older (before version 4.5) `wf_…` workflow folder in Viewer Mode. Not for `.idtw` workspaces: open those with Open Workspace |
| Close Window | Cmd+W | macOS only |
| Exit | Ctrl+Q | Close the application (Cmd+Q on macOS) |

#### Edit Menu

| Item | Shortcut | Description |
|---|---|---|
| Undo | Ctrl+Z | Undo the last change in the focused text field |
| Redo | Ctrl+Y (Cmd+Shift+Z on macOS) | Redo what Undo took back |
| Cut | Ctrl+X | Cut text from focused field |
| Copy | Ctrl+C | Copy selected text |
| Paste | Ctrl+V | Paste text or an image from clipboard |
| Select All | Ctrl+A | Select all text in focused field |

#### Process Menu

| Item | Description |
|---|---|
| Process Current Image (P) | Describe the selected image. With a folder selected, describes that folder's images that have no description; with a video selected, opens Extract Video Frames |
| Process Undescribed in Selected Folder | Batch-process the images with no description in the folder selected in the image list |
| Redescribe All in Selected Folder | Re-process every image in the selected folder (adds new descriptions) |
| Process Undescribed Images (Entire Workspace) | Batch-process only images that have no description, in the whole workspace |
| Redescribe All Images (Entire Workspace) | Re-process all images (adds new descriptions alongside existing ones) |
| Show Batch Progress | Show the Batch Progress dialog again. Available while a batch runs |
| Stop All Processing (Ctrl+.) | Stop the batch, and any other background work such as a folder scan. Available while something is running |
| Update Image List (F5; Cmd+R on macOS) | Refresh the image list |
| Refresh AI Models | Reload available models from all providers |
| Chat with AI Model (Ctrl+T, or C) | Open the interactive chat window |
| Convert HEIC Files... | Convert HEIC/HEIF images to JPEG |
| Extract Video Frames... | Extract frames from video files |
| Describe Video with AI... | Generate an AI description for a video |
| Play Video | Play the selected video in your system's default player (or press Enter on the video) |
| Rename Item (F2, or R) | Give the selected image, video or chat a new display name |

#### Descriptions Menu

| Item | Description |
|---|---|
| Add Manual Description (M) | Type a description by hand |
| Ask Followup Question (F) | Ask the AI a follow-up question about the selected image |
| Edit Description... | Edit the description shown in the editor |
| Delete Description | Delete the description shown in the editor, after asking |
| Copy Description | Copy the description shown in the editor to the clipboard |
| Copy Image Path | Copy the file path to clipboard |
| Copy Image | Copy the image to the clipboard |
| Copy Image + Description | Copy both the image and the description shown in the editor |
| Show All Descriptions... | A summary of the workspace in one read-only box: each described image, with the model, prompt style and first 100 characters of each of its descriptions |

**Which description these act on.** Edit, Delete and the Copy items use the description the editor is showing: the one you selected in the description list, not always the newest. Delete's question names it and quotes its start, for example "Delete description 2 of 3, by Claude Haiku 5.5?" followed by "It begins:" and the first words. After you edit or delete, the editor stays on that place in the list. In Viewer mode, the Copy items use the description selected in the Viewer instead.

**The usage line.** Each description ImageDescriber writes ends with a line such as `[Token Usage: 4,196 total (3,000 prompt + 1,196 completion) | Time: 8.12s]`, or just `[Time: 8.12s]` when the provider reports no token counts. It's saved with the description, and you read it wherever ImageDescriber shows a description in full: the description list, the editor and Viewer mode. It's left out everywhere the description goes outside ImageDescriber: the copy commands, every export and report, the HTML gallery, descriptions embedded into images, and `idt show`, `idt export` and `idt combine`. A location at the start of a description, such as "Madison, Wisconsin - ", is part of the description and is kept everywhere.

#### View Menu

| Item | Description |
|---|---|
| **Application Mode** → Editor Mode | Switch to the workspace editor |
| **Application Mode** → Viewer Mode | Switch to the read-only viewer |
| Filter: All Items | Show all images, videos, and chats (Ctrl+Shift+A) |
| Filter: Described Only | Show only images with at least one description (Ctrl+Shift+D) |
| Filter: Undescribed Only | Show only images lacking a description (Ctrl+Shift+U) |
| Filter: Videos Only | Show video files and their extracted frames |
| Filter: Chats Only | Show saved chat sessions |
| Show Image Previews | Toggle the image thumbnail panel |
| Find Images... (Ctrl+F) | Show or hide the search bar |

The five Filter items sit directly in the View menu, not in a submenu, and only one is on at a time.

#### Tools Menu

| Item | Shortcut | Description |
|---|---|---|
| Edit Prompts... | Ctrl+Shift+P | Create, edit, and manage AI prompt templates |
| Configure Settings... | Ctrl+Shift+C | Open the settings dialog. On a Mac it is **ImageDescriber → Preferences...** (Cmd+,) |
| Install Ollama... | — | Instructions for installing the local Ollama server |
| Install FFmpeg (for video GPS)... | — | Instructions for installing FFmpeg |
| Export Configuration... | — | Save settings to a file |
| Import Configuration... | — | Load settings from a file |
| **AI Info** → Ollama Models... | — | View installed Ollama models |
| **AI Info** → OpenAI Usage Dashboard... | — | Open OpenAI usage tracking |
| **AI Info** → Claude Usage Dashboard... | — | Open Anthropic usage tracking |
| **AI Info** → MLX Community Models... | — | Browse HuggingFace MLX models |

#### Help Menu

| Item | Description |
|---|---|
| User Guide... (F1; Cmd+? on macOS) | Open this guide |
| Report an Issue... | Go to the GitHub issue tracker |
| Check for Updates... | Ask GitHub right now whether a newer version exists |
| Automatically Check for Updates | Toggle the once-a-day check at startup (on by default) |
| About | Show version information |

---

### The Main Window Layout

The main window has the image list on the left and the descriptions on the right. Its controls, in the order you reach them with Tab, which is also the order a screen reader meets them:

1. **Images in workspace**: the image list, on the left. (When the search bar is showing, its search box ("Filter images by text") and Clear search button come first.)
2. **Description list for current image**: the descriptions of the selected image, on the right.
3. **Image description editor**: the text of the selected description, below the list.
4. The **Generate Description** and **Save Description** buttons, below the editor.

The image preview is never a Tab stop. Shift+Tab moves back through the same order.

**Left panel: Image list**

A hierarchical tree showing all items in the workspace:

- Folder nodes (expandable) — represent subfolder groups from your source directory
- Video nodes (expandable) — videos with their extracted frames as child items
- Image items — individual files, with short status codes in front of the name
- Chat nodes — saved conversation sessions

**Status codes.** An image's state is a short code in front of its name, for example `d1 Polidor.jpg`, `d2P Arena.jpg` or `X beach.jpg`. The codes are short on purpose: moving through a long list, you hear an item's state in a syllable or two and then its name, rather than a longer word on every item. An image with no code has no description yet.

| Code | Meaning |
|---|---|
| `d1`, `d2`, … | Has that many descriptions |
| `P` | Being described now |
| `.` | Waiting its turn in a batch |
| `!` | In a paused batch |
| `X` | Describing it failed. **Process → Process Undescribed Images, Entire Workspace** tries it again |
| `E12`, … | A video, with that many frames extracted |
| `[!]` | The file is no longer on disk (its descriptions are kept) |

Codes run together in this order: missing, descriptions, state, frames. So `[!]d2 old.jpg` is a missing file with two descriptions, and `d1X` has one description and failed when described again.

Use **View → Find Images** (`Ctrl+F`) to show a search bar that filters by filename, description text, or metadata content. Supports `and` / `or` operators: for example, `house and garage or backyard`.

**Right panel: Description area**

When an image is selected:

- **Image preview** — Thumbnail of the selected image (toggle with **View → Show Image Previews**).
- **Description list** — All descriptions for this image. Arrow to a description (or click it) to show it in the editor.
- **Generate Description button** — Opens the **Processing Options** dialog for the selected image, then describes it with what you choose there. Pressing `P` in the image list does the same. With a folder selected, it describes that folder's images that have no description yet.
- **Save Description button** — Saves edits made to the description text.

**Bottom right: Description editor**

The **Image description editor** shows the full text of the selected description, including its usage line (see [The usage line](#descriptions-menu)). You can edit it directly and save with the **Save Description** button.

Below the description, after a line of three dashes (`---`), the editor adds the description's details:

- **Provider**, **Model** (by name, such as "Claude Haiku 5.5"), **Prompt** (the prompt style) and **Created** (the date it was made).
- For an image downloaded from a web page, a **Download Source** section with its **URL** and the date it was **Downloaded**.
- When the picture's file has them, an **Image Info** section: **AI context** (what was added to the prompt, such as the place name), **Captured** (when the photo was taken), **Location**, **GPS** coordinates and **Camera**.

**Save Description saves only the description.** The details are there for you to read; they are left out when you save, so they never become part of the description. If you change the details text itself, Save refuses with: "The details shown with the description were changed, so ImageDescriber can't tell them from the description. Undo that change, or delete the details, then save." Undo the change (Ctrl+Z), or delete the whole details block, and save again.

**Status bar**

The bar at the bottom of the window shows:
- Left: Current action or status message.
- Right: A count, such as "250 images", or the filter in use after you choose one from the View menu.

While a batch runs, the window title shows how far it has got, for example `42%, 21 of 50 - ImageDescriber - MyTrip.idtw`.

---

### Working with Workspaces

**Creating a workspace**

1. **File → New Workspace** creates an empty workspace named "Untitled".
2. **File → Load Directory** adds a folder of images. Check **Add to existing workspace** to add a second folder without starting over.
3. **File → Save Workspace As...** saves the bundle as `MyTrip.idtw` in the location you choose.

**Opening an existing workspace**

- **File → Open Workspace (.idtw)...** (`Ctrl+O`) to browse for a bundle.
- From a command prompt or Terminal, start ImageDescriber with the bundle's path, for example `ImageDescriber.exe C:\Users\you\Documents\idt\MyTrip.idtw`.

A large workspace can take a while to open, especially from a OneDrive or network folder. If opening takes more than half a second, a progress window titled "Opening workspace — Batch Processing" appears and counts the items as they are read; it closes by itself when the workspace is open.

**Refreshing after changes on disk**

If you add new images to the source folder after loading:

- Select the folder in the image list, then choose **File → Refresh Folder from Disk...** (`Ctrl+Shift+R`). With a mouse, you can also right-click the folder and choose **Refresh Folder from Disk…**. It rescans the folder and adds new files. Images marked `[!]` (file deleted) are noted but their descriptions are kept.

**Workspace statistics**

**File → Workspace Statistics...** (`Ctrl+I`) shows:

- Image and description counts
- Content metrics and description length distribution
- AI provider and model breakdown
- Token usage and estimated cost
- Location information summary
- Processing timeline

---

### Batch Processing

**Starting a batch job**

1. Choose **Process → Process Undescribed Images (Entire Workspace)** (or **Redescribe All Images (Entire Workspace)** to re-process everything).
2. The **Processing Options** dialog appears. It has two tabs, **General** and **AI Model**, and opens on the AI Model tab with the focus on **Provider**. Use Ctrl+Tab to move between the tabs.

   **AI Model tab**
   - **Provider** — Ollama, OpenAI and Claude, plus Claude Code, Apple Intelligence, Windows AI and MLX on a computer that can run them. A provider that can't run on this computer isn't listed.
   - **Model name** — Populated from the chosen provider. The box after it describes the selected model.
   - **Prompt style** — Choose a built-in style or one of your own.
   - **Custom prompt** — Optional. Text typed here replaces the prompt style; leave it blank to use the style.

   **General tab**
   - **Skip images that already have descriptions** — Off by default.
   - **Geocode GPS coordinates to city/state (requires internet)** — Turn a picture's GPS coordinates into a place name and add it to the prompt. The date and camera are never sent to the AI.
   - **Embed description into workspace after processing** — After each image is described, put a copy of it in the workspace's `embedded` folder with the description written into the copy's metadata. Your originals are never changed.
   - **Copy original images into the workspace** — On, the workspace keeps its own copy of every picture, so you can move it to another computer. Off, it refers to your pictures where they are.
3. Choose **OK** to start, or **Cancel** to close the dialog without describing. The **Batch Progress** dialog opens. (**Apply**, where it's shown, keeps the geocoding and copy-originals choices for the rest of this session without closing the dialog.)

To batch only one folder, select the folder in the image list and choose **Process → Process Undescribed in Selected Folder**, or **Process → Redescribe All in Selected Folder** to describe every image in it again. Pressing `P` with a folder selected also describes that folder's images that have no description yet.

**The Batch Progress dialog**

| Element | Description |
|---|---|
| Processing statistics and current image | A list you read with the arrow keys: items processed, failures, average time per image, estimated time remaining, the provider, model and prompt style, token use and cost (see below), the last image described with the start of its description, and the current image. The separator lines are skipped as you arrow |
| Progress bar | Visual percentage complete |
| Pause / Resume | Temporarily pause and resume the batch |
| Stop | Cancel the batch (descriptions generated so far are kept) |
| Close | Hide the dialog; processing continues in the background. **Process → Show Batch Progress** brings it back |

**Token use and cost.** Once descriptions start coming back, the list has a **Token Usage** section:

- **Estimated Cost So Far** — what the pictures described so far cost, at the provider's list prices.
- **Average Cost per Image**.
- **Projected Batch Cost** — about what the whole batch will cost: the cost so far plus the average for each picture still to go. Not shown while videos are still having their frames extracted, since the total isn't known yet.
- **Average Input Tokens**, **Average Output Tokens**, **Average Total Tokens** and **Total Tokens**.
- **Largest Token Use** — the most tokens one picture took, and which picture.

For a model that isn't charged per token, the cost line says why instead: "no charge (runs on your computer)", "covered by your Ollama plan", "covered by your Claude plan" (Claude Code), or "no price known for this model". The costs are estimates; your provider's bill is the real figure.

**Video files in a batch**

Videos in the folder are automatically extracted to frames before the AI step. The default extraction interval is every 5 seconds; you can change this in **Tools → Configure Settings**.

---

### Generation Settings

**Tools → Configure Settings → Generation** controls what IDT asks a model for besides the prompt. Every setting starts on **Automatic**, which uses IDT's default for the provider and model you pick, so most people never need this tab. The command line uses the same saved settings.

Each provider lists only the settings it can use:

| Provider | Settings |
|---|---|
| Ollama | Thinking, temperature, top p, top k, repeat penalty, output limit |
| OpenAI | Thinking, effort, temperature, top p, output limit |
| Claude | Thinking, effort, output limit |
| Claude Code | Thinking, effort, output limit |
| Apple Intelligence (Mac only) | Temperature, output limit |
| MLX (Mac only) | Output limit |

Things worth knowing:

- **Thinking models are slow for descriptions.** They reason before answering, and the reasoning is thrown away. For Ollama, Automatic turns thinking off for descriptions. Some models keep thinking anyway; every `qwen3-vl` thinking tag does. For those, pick the model's `-instruct` tag, such as `qwen3-vl:8b-instruct` instead of `qwen3-vl:8b`. The model list marks thinking models "(thinks, slower)".
- **Claude and OpenAI can't switch reasoning off.** Thinking Off asks for the least effort the model takes instead.
- **Too low an output limit cuts descriptions off.** The run log says when it happens, and when a model spent its whole allowance thinking.
- **The run log records what was skipped.** If a setting doesn't apply to a model, it isn't sent, and the log in the workspace's `logs` folder says so. It also records how much hidden reasoning each picture took, which explains a slow run.

To change a setting, select it and press Enter, or press **Change Setting**. Leave a number empty, or choose Automatic, to go back to the default.

On every tab of the Configure dialog, Tab from the settings list goes to an **Explanation** box for the selected setting. You can read it with the cursor, and it changes as you move through the list. Tab again for Change Setting.

### The Chat Window

Open with **Process → Chat with AI Model** (`Ctrl+T`). Choose a provider and model in the prompt dialog.

The chat window is a general-purpose, multi-turn conversation with the AI model of your choice. It is not limited to images — use it for anything, including:

- Asking follow-up questions about a description you generated
- Requesting alternative phrasing
- Exploring accessibility phrasing options
- Any other question you would ask a chat assistant

**Layout**

- **Conversation history** (ListBox) — All messages, navigable with arrow keys. Screen readers announce new messages automatically.
- **Message detail pane** — Full text of the selected message. Editable so you can select and copy from it; edits are not saved.
- **Input field** — Type your message. `Enter` sends; `Shift+Enter` starts a new line.
- **Attach Files** — Attach images or text files to the conversation. Shown only for providers that accept attachments; Claude and OpenAI also accept PDFs, and MLX takes images only. See [Attaching files](#attaching-files) for what each provider accepts. You can also paste an image from the clipboard with **Paste Image** (on Windows, `Ctrl+V` also works).
- **Change Model** — Switch provider or model mid-conversation. History is kept.
- **Token usage** — Shows how much of the model's context window the conversation is using.
- **Session → Thinking** — Automatic, On or Off. Off makes a reasoning model answer faster: a question about a photo on a large thinking model can otherwise take minutes. For Claude and OpenAI, Off means the least effort the model takes. The choice applies from your next message, and a new chat window starts with the last one you picked.

**Starting a chat does not attach the image you have selected.** Every chat begins empty. To ask about a specific image, attach it with **Attach Files** or paste it from the clipboard.

Chat sessions are saved with the workspace and appear as chat items in the item list. Press `Enter` on a saved chat to resume it — the full conversation history is restored, so the model retains context. Attachments from earlier turns are not re-attached when resuming.

**Known problem: chats in a workspace saved before.** In a workspace that has already been saved, **File → Save Workspace** doesn't save chats, so a chat started or continued there is lost when you close the workspace. To keep it, use **File → Save Workspace As...** (`Ctrl+Shift+S`) and save under a new name. The issue is tracked as [#403](https://github.com/TheIdeaPlace/Image-Description-Toolkit/issues/403).

---

### Viewer Mode

**View → Application Mode → Viewer Mode** switches the application to a read-only list of every description in the open workspace, one after another, so you can read through them without moving between images. **View → Application Mode → Editor Mode** switches back.

**The list.** The focus moves to the list, named "Viewer, all descriptions", as soon as you switch. Picture descriptions are in the order they were made, oldest first and newest last. Chat messages are kept together after them, so with no chats in the workspace, End takes you to the most recent description. The Viewer starts on the newest picture description, so the first thing you hear is the latest result.

**Tab order.** **Refresh**, **Live Monitoring**, the list, the **Description** box, **Copy Text**, **Copy Image**. The picture preview is never a Tab stop. Live Monitoring is dimmed, and so skipped, for a workspace (see below).

- **Description** — the full text of the selected description, read-only, with its usage line (see [The usage line](#descriptions-menu)) and a line naming the model and prompt style.
- **Copy Text** — copies the description and that model line, without the usage line.
- **Copy Image** — copies the picture.
- **Refresh** — reloads the list. The Viewer doesn't update by itself: to see descriptions added since you switched, such as from a batch that is still running, choose Refresh (or switch to Viewer Mode again).

The **Descriptions** menu's Copy items (Copy Description, Copy Image Path, Copy Image, Copy Image + Description) act on the description selected in the Viewer.

**Changes are made in Editor mode.** Viewer mode only reads. If you try something that changes the workspace, such as Process Current Image (`P`), Edit or Delete Description, Add Manual Description, Ask Followup Question, Rename Item or Play Video, ImageDescriber tells you where to do it instead, for example: "Editing a description is done in Editor mode. To switch, choose View, Application Mode, Editor Mode, then select beach.jpg."

**Older workflow folders.** **File → Open Workflow Result (Viewer Mode)...** opens a `wf_…` folder made by IDT before version 4.5 in the Viewer. It doesn't open a `.idtw` workspace; for those, use **File → Open Workspace** and then switch to Viewer Mode. For a workflow folder, **Live Monitoring** can be turned on: the Viewer then watches the folder's description file and refreshes when it changes. Changes to a workflow folder's descriptions aren't possible in the Viewer; ImageDescriber suggests importing it with **File → Import Workflow (to Workspace)...**, which brings its descriptions into the workspace.

---

### Export Options

**Export Descriptions (text or HTML)**

**File → Export Descriptions...** saves descriptions to:

- **Text file (.txt)** — Plain text with sections for each image: filename, capture date, and description.
- **HTML file (.html)** — Styled table with images and descriptions. Suitable for sharing in email or a web browser.

**Export HTML Gallery**

**File → Export HTML Gallery...** (`Ctrl+Shift+H`) produces an interactive gallery:

- Responsive design (works on desktop and mobile browsers)
- Thumbnails with full descriptions visible on click
- Search built in
- No server required; open directly in any browser
- Customizable title

**Embed Descriptions into Images**

**File → Embed Descriptions into Images...**

Options in the dialog:

| Option | Description |
|---|---|
| **Which description** → Latest | Embed the most recently generated description (recommended) |
| **Which description** → All Combined | Join all descriptions with a separator and embed the combined text |
| **Write mode** → Copy (recommended) | Create new image copies in the output folder; originals untouched |
| **Write mode** → In-place | Modify the original files directly (requires confirmation) |
| **Output folder** | Browse to choose where copies are saved |

Embedded copies mirror the subfolder structure of the source.

---

### Keyboard Shortcuts

See [Appendix D: Keyboard Shortcut Reference](#appendix-d-keyboard-shortcut-reference) for the full table.

**Tab order in the main window (Editor mode):**

Image list → Description list → Description editor → Generate Description → Save Description (Shift+Tab to move backward). When the search bar is showing, its search box ("Filter images by text") and Clear search button come before the image list. The image preview is never a Tab stop.

**Tab order in Viewer mode:**

Refresh → Live Monitoring (dimmed and skipped for a workspace) → the list of descriptions → Description → Copy Text → Copy Image.

All menu items, buttons, and interactive controls are reachable by keyboard. Arrow keys navigate the image list and description list.

**Single-letter keys.** In the image list and the description list (and the Viewer's list), these letters act at once, with no Ctrl or Alt. They don't apply while you're typing in a text box.

| Key | Does |
|---|---|
| `P` | Process the selected image (Process → Process Current Image) |
| `R` or `F2` | Rename the selected item |
| `M` | Add a manual description |
| `F` | Ask a follow-up question |
| `C` | Open the chat window |

Because of these, typing one of these letters in the image list doesn't jump to an item starting with it. In Viewer mode, all but `C` say they're done in Editor mode.

**Enter in the image list** plays a video in your system's default player, or reopens a saved chat.

---

## Part 4: AI Providers

> **Provider names differ between CLI and GUI.** Use this mapping table as a quick reference:
>
> | CLI name | GUI name | Notes |
> |---|---|---|
> | `anthropic` | `claude` | Same provider; Anthropic Claude models |
> | `ollama` | `ollama` | Same name in both |
> | `openai` | `openai` | Same name in both |
> | `claude-code` | `claude-code` | Same name in both; shown as "Claude Code" in pickers |
> | `apple` | `apple` | Same name in both; shown as "Apple Intelligence" in pickers |
> | `Windows-AI` | `Windows-AI` | Same name in both, in any case (`windows-ai` works too); shown as "Windows AI" in pickers |
> | — | `mlx` | GUI only; Apple Silicon local models |

### Ollama — Local (Windows and macOS)

Ollama runs AI models on your own machine. No internet connection is required after the model is downloaded. No data leaves your computer, except with Ollama's cloud models (see [Ollama's cloud models](#ollamas-cloud-models)).

**CLI and GUI provider name:** `ollama`

**Setup**

1. Install Ollama from [ollama.com](https://ollama.com).
2. Pull a vision-capable model:

   ```bash
   # Recommended: best quality across all hardware (1.6 GB)
   ollama pull minicpm-v4.6

   # Highest quality (requires CUDA GPU or Apple Silicon, 7+ GB)
   ollama pull llama3.2-vision

   # Smallest / fastest (CPU-only, 1.8 GB)
   ollama pull moondream:latest
   ```

3. Ollama starts automatically as a background service.

**Using a remote Ollama server (CLI)**

```bash
idt describe ~/Photos --provider ollama --model minicpm-v4.6 --ollama-host http://192.168.1.100:11434
```

ImageDescriber has no setting for another Ollama server: it always uses the Ollama on this computer (`http://127.0.0.1:11434`).

#### Ollama's cloud models

Ollama also offers cloud models, whose names end in `-cloud` (or `:cloud`). They run on ollama.com rather than on your computer, so your pictures are sent there, but you reach them through the Ollama on your computer like any other model. To use one, sign in to Ollama (`ollama signin`) and pull the model with `ollama pull`. It then appears in ImageDescriber's Ollama model list and in `idt models --provider ollama`, as long as Ollama reports that it can see images. There is no separate provider to choose. The Batch Progress dialog shows their cost as "covered by your Ollama plan".

**Recommended models**

| Model | Size | Notes |
|---|---|---|
| `minicpm-v4.6` | 1.6 GB | Excellent quality; works on all hardware including ARM Windows |
| `llava` | 4–7 GB | Solid accuracy; CPU or GPU |
| `llama3.2-vision` | 7+ GB | Higher quality; best on Apple Silicon or CUDA GPU |
| `moondream:latest` | 1.8 GB | Fastest; CPU-only capable |
| `qwen2-vl:7b` | 7 GB | Good balance of speed and quality |

---

### Anthropic Claude — Cloud (Windows and macOS)

Claude models produce the highest quality, most detailed descriptions. Requires an internet connection and an Anthropic API key.

**CLI provider name:** `anthropic` · **GUI provider name:** `claude`

**Setup:** In ImageDescriber, choose **Tools → Configure Settings** (on a Mac, **ImageDescriber → Preferences**), go to the **API Keys** tab, select **Claude (Anthropic)** and choose **Add Key**. Or set the `ANTHROPIC_API_KEY` environment variable. See [Setting Up API Keys](#setting-up-api-keys).

**Available models**

IDT asks Anthropic which models your account can use, so the list in every picker is the real one rather than a copy baked into the app. Run `idt models --provider anthropic` to see yours. A few of the common ones:

| Model | Characteristics |
|---|---|
| `claude-haiku-5-5` | The default. Fastest and cheapest, about $1 per 1,000 images with the Detailed prompt, and detailed enough for most pictures |
| `claude-sonnet-5-5` | More thorough, about $13 per 1,000 images |
| `claude-opus-5-5` | Richer descriptions, about $30 per 1,000 images |
| `claude-fable-5-2` | Anthropic's most capable model and the most precise reader of small detail; slowest and most expensive, about $55 per 1,000 images |

The prices are from a November 2026 test of the Detailed prompt; a longer prompt or bigger pictures cost more.

Your account may show more or fewer than these. A model Anthropic has released since your copy of IDT was built appears too, marked `new — details unknown`.

**CLI example**

```bash
idt describe ~/Photos --provider anthropic --model claude-opus-5-5 --prompt detailed
```

---

### OpenAI GPT — Cloud (Windows and macOS)

Requires an OpenAI API key. Good for workflows already integrated with OpenAI.

**CLI and GUI provider name:** `openai`

**Setup:** In ImageDescriber, choose **Tools → Configure Settings** (on a Mac, **ImageDescriber → Preferences**), go to the **API Keys** tab, select **OpenAI** and choose **Add Key**. Or set the `OPENAI_API_KEY` environment variable. See [Setting Up API Keys](#setting-up-api-keys).

**Available models**

As with Claude, IDT asks OpenAI what your account can use. Run `idt models --provider openai` to see yours — most accounts have far more than the handful listed here.

| Model | Characteristics |
|---|---|
| `gpt-6-luna` | The default. Fastest and cheapest ($0.10 per million input tokens, $0.50 per million output), and detailed enough for most pictures |
| `gpt-6.1-terra` | OpenAI's model for visual reasoning; more thorough, ten times the price of Luna |
| `gpt-6.2-sol` | OpenAI's everyday flagship ($2 in, $10 out per million tokens) |
| `gpt-6.2-astra` | OpenAI's most capable model; slowest and most expensive ($8 in, $40 out per million tokens) |

Prices are OpenAI's standard rates as of November 2026. Older models such as `gpt-5.2`, `gpt-5-mini`, `gpt-4o` and `o3` are still offered while OpenAI keeps them running; OpenAI has shut down `o1`, `o4-mini` and `gpt-4.1-nano`, so IDT no longer offers them, though workspaces described with them still show their names.

OpenAI's account list also contains speech, image-generation, embedding and moderation models, which cannot describe pictures or hold a conversation. IDT hides those so the picker stays usable with a keyboard and screen reader. If something you need is missing, `idt models --provider openai --all` shows the unfiltered list.

**CLI example**

```bash
idt describe ~/Photos --provider openai --model gpt-6-luna
```

---

### Claude Code — Your Claude Subscription (Windows and macOS)

If you pay for Claude Pro or Max, IDT can use that subscription instead of an API key. Requests go through the Claude Code app, so they count against your plan's usage limits and never charge an API account. It works everywhere the other providers do: `idt describe`, `idt chat`, ImageDescriber (describing and chat) and IDT Chat.

**CLI and GUI provider name:** `claude-code` (shown as **Claude Code** in pickers)

**Setup**

1. Install Claude Code from [claude.com/claude-code](https://claude.com/claude-code).
2. Sign in with your Claude account, not an Anthropic Console account:

   ```bash
   claude auth login
   ```

3. Check it: `idt models --provider claude-code` lists the models when you are signed in, and says what is wrong when you are not.

IDT refuses to use Claude Code when it is signed in any other way (for example with an API key), because that would bill an API account instead of your subscription. Claude Code only appears in the pickers when it is installed.

**Models**

| Model | Characteristics |
|---|---|
| `haiku` | Fastest; uses the least of your plan's usage. A good default for large folders |
| `sonnet` | More detail and better at reading text in images |
| `opus` | Most capable; uses your plan's usage fastest |

These names always mean the current model of each tier.

**How much of your plan it uses**

Very little. Each image is sent on its own, with a short instruction and none of Claude Code's usual extras, so it costs about what the same request would through the API: roughly 1,850 input tokens for a phone photo plus the length of the description.

A measured example, from 9/24/2026 on a Claude **Pro** plan:

| | |
|---|---|
| Folder | 103 iPhone photos, `haiku`, "narrative" prompt |
| Result | 103 described, no errors, in 22.5 minutes (about 13 seconds per image) |
| Tokens | about 1,830 in and 690 out per image |
| Plan usage | at most about 4% of the 5-hour limit, shared with other Claude use in the same window; the weekly limit did not visibly move |

That suggests a Pro plan can describe a couple of thousand photos with `haiku` in one 5-hour window. Max plans have larger limits. Your own numbers will vary with:

- **Model** — `sonnet` uses roughly twice as much per image as `haiku`, and `opus` roughly five times.
- **Prompt** — a prompt that asks for long, detailed descriptions produces more output, and output is the larger share of the cost.
- **Everything else you do with Claude** — describing images draws on the same allowance as your chats and Claude Code sessions. A long coding session can use more than a folder of photos.

To see the effect of a run, check your usage in Claude's settings before and after it. If a batch does reach a limit, IDT reports the limit message for the images it could not describe; run the batch again after the window resets to finish the rest. `idt describe` skips images that already have descriptions on its own; in ImageDescriber, turn on **Skip images that already have descriptions** in the processing options (it is off by default), or the finished images are described again.

**CLI examples**

```bash
idt describe ~/Photos --provider claude-code --model haiku
idt chat --provider claude-code --model sonnet
```

**Limits compared with the Claude API provider:** no PDF attachments in chat yet, no web search in chat, and `--temperature` is ignored. This is for your own use of your own subscription; it runs as whoever is signed in to Claude Code on the computer.

---

### Apple Intelligence — On This Mac (macOS 27 and later)

macOS 27 can describe images with Apple's own on-device model, and IDT uses it as a provider. Nothing is uploaded: the model runs on the Mac's Neural Engine, so it needs no API key, no account and no internet connection, and it costs nothing however many images you describe. It works everywhere the other providers do: `idt describe`, `idt chat`, ImageDescriber (describing and chat) and IDT Chat.

**CLI and GUI provider name:** `apple` (shown as **Apple Intelligence** in pickers)

**What you need**

- A Mac with Apple Silicon running macOS 27 or later. Intel Macs and older macOS cannot run it, and the option is hidden there rather than offered and failing.
- Apple Intelligence turned on in **System Settings → Apple Intelligence & Siri**, with its model downloaded.
- Apple's Foundation Models terms accepted once on the machine.

**Setup**

The terms are the only setup step, and IDT cannot do it for you: accepting them applies to everyone who uses the Mac, so it has to be run by an administrator. Open Terminal and run:

```bash
sudo fm license
```

Then check it:

```bash
idt models --provider apple
```

That lists the model when the Mac is ready, and says what is wrong when it is not — wrong macOS, Apple Intelligence switched off, or the terms not yet accepted. ImageDescriber and IDT Chat show the same information when you pick the provider.

**Models**

There is one: `system`, shown as **On-device (Apple Intelligence)**. Apple also offers a Private Cloud Compute model, but it is unavailable to apps launched outside Terminal, so IDT does not list it.

**What it is good at**

Speed and privacy. A description takes about four to six seconds per image on an M-series Mac, with no network round trip and no usage limit to watch. It reads scenes accurately — objects, colours, foreground and background, left-to-right placement — which is what alt text usually needs.

It is a small model compared with Claude or GPT, so expect shorter, plainer descriptions with less interpretation and less confidence on fine text inside an image. If you want the most detailed result, use a cloud provider; if you want something free, fast and completely private, this is the one to reach for.

**Context note.** The on-device model holds about 4,096 tokens in total — an order of magnitude less than the cloud models. That is plenty for describing images, but chats hit the limit quickly. When one does, IDT says so and asks you to start a new conversation rather than retrying something that cannot succeed.

**If it refuses an image.** Apple Intelligence declines some pictures outright — it says so, and the run carries on. Retrying the same request will not help, but a different prompt style often will. Which one is not predictable: on the same photo, one machine described it with `detailed` and another refused it. Try a few, and prefer the longer, more detailed styles. See [Apple Intelligence: when it refuses to describe an image](apple-intelligence-safety-refusals.md) for what triggers it and how to test it yourself.

**Speed note.** The first image of a run is slower than the rest, because IDT starts the on-device model then. ImageDescriber says so in the progress dialog. Later images in the same run reuse it.

**CLI examples**

```bash
idt describe ~/Photos --provider apple
idt chat --provider apple
```

**Limits compared with the cloud providers:** no PDF attachments in chat (the model takes images and text only), no web search in chat, only the one model, and a much smaller context window (about 4,096 tokens). Because everything runs locally, there is no rate limit and no bill.

---

### Windows AI — On This PC (Copilot+ PCs)

Windows 11 can describe images with Windows' own on-device model on a Copilot+ PC, and IDT uses it as a provider. The model runs on the PC's NPU: nothing is uploaded, and it needs no API key, no account and no internet connection, and costs nothing however many images you describe. It is for describing images, in `idt describe` and ImageDescriber; it can't chat.

**CLI and GUI provider name:** `Windows-AI`, in any case (shown as **Windows AI** in pickers)

**What you need**

- A Copilot+ PC (one with an NPU) running Windows 11 24H2 or later.
- Windows' AI features turned on (they are unless you or your organization turned them off).
- IDT installed with the installer, with **Set up Windows AI** ticked. It is ticked by default on Windows 11 24H2 and later.

**Setup**

The installer does it, on a PC with an NPU. It adds a small helper that lets IDT reach Windows' model, and the Windows App Runtime that the helper needs if your PC doesn't already have it (a download of about 100 MB from Microsoft). Then check it:

```bash
idt models --provider Windows-AI
```

That lists the models when the PC is ready, and says what is wrong when it is not: not a Copilot+ PC, Windows too old, or the AI features turned off. The first time, Windows may need to download its model; IDT says so and waits. That can take a few minutes, once.

**Models**

The model takes no prompt. Instead it offers four kinds of description, and these are its models:

- `accessible` (the default): a long description written for people who are blind or have low vision.
- `detailed`: a long description.
- `brief`: a sentence.
- `diagram`: for charts and diagrams.

Choose one with `--model` or in the model list. Because there is no prompt, the prompt style and custom prompt are not used: the CLI says so if you pass `--prompt`, ImageDescriber's prompt controls say "not used by Windows AI", and descriptions record the prompt as `none`. Photo details such as the date and place can't shape these descriptions either.

**What it is good at**

Photos, quickly and privately. A description takes about two to four seconds on a Snapdragon X Elite, and the accessible descriptions are detailed and accurate. It is less good with screenshots: it reads the text but guesses at the rest.

**If it declines an image.** Windows' content filter declines some pictures, and it declines pictures that are mostly text. It says so, and the run carries on. A different kind won't help; a different provider (or OCR, for text) will. Windows' model also fails on some pictures at one size and not another, so IDT tries those again at smaller sizes, and most are then described.

**CLI examples**

```bash
idt describe C:\Photos --provider Windows-AI
idt describe C:\Photos --provider Windows-AI --model brief
```

**Not available in:** chat (IDT Chat, `idt chat`, ImageDescriber's chat), follow-up questions and auto-rename. All of these send a prompt, and Windows AI takes none.

### MLX — Apple Silicon Local (ImageDescriber only, macOS)

MLX runs vision models directly on Apple Silicon (M1/M2/M3/M4) using Apple's Metal GPU via the `mlx-vlm` library. It is the fastest local option on Mac and produces quality comparable to small Ollama models. **MLX is only available in ImageDescriber.** It does not appear in the CLI, and IDT Chat does not offer it: that build deliberately omits the MLX libraries, which would take it from about 40 MB to around 350 MB. For chat that is a poor trade, because Ollama now runs several models through MLX on Apple Silicon itself — chatting with Ollama on a Mac already gets you the Metal acceleration. To chat with an MLX model directly, use ImageDescriber's own chat window. The picker hides the option rather than showing one that would fail when chosen.

**GUI provider name:** `mlx`

**Setup**

To enable it, install the `mlx-vlm` package into the same Python environment that runs ImageDescriber:

```bash
# Activate the GUI's virtual environment first, then:
pip install mlx-vlm
```

Models are downloaded automatically on first use from HuggingFace Hub and cached in `~/.cache/huggingface/hub/`.

**Available models (select in GUI; you can also type any HuggingFace MLX repo ID)**

| Model | Size | Notes |
|---|---|---|
| `mlx-community/Qwen3-VL-4B-Instruct-4bit` | ~3.1 GB | **Recommended default** — best quality/speed balance |
| `mlx-community/Qwen3-VL-8B-Instruct-4bit` | ~5.8 GB | Higher quality; 16 GB+ Mac recommended |
| `mlx-community/Qwen2-VL-2B-Instruct-4bit` | ~1.5 GB | Fastest Qwen option |
| `mlx-community/gemma-3-4b-it-qat-4bit` | ~2.5 GB | Strong English descriptions |
| `mlx-community/phi-3.5-vision-instruct-4bit` | ~2.5 GB | Good at text and fine detail |
| `mlx-community/SmolVLM-Instruct-4bit` | ~0.5 GB | Smallest; very fast, shorter descriptions |
| `mlx-community/Llama-3.2-11B-Vision-Instruct-4bit` | ~6.5 GB | High quality; 16 GB+ Mac recommended |

---

## Part 5: Prompts and Customization

### Built-In Prompt Styles

IDT ships with a library of prompt styles tuned for different use cases. List them with `idt prompts`.

| Name | Description |
|---|---|
| `narrative` | Flowing description with spatial organization (left-to-right, foreground/background) |
| `detailed` | Structured sections: SUBJECT, SETTING, COLORS, COMPOSITION, DETAILS |
| `concise` | Brief 2–3 sentence summary |
| `artistic` | Visual qualities with bullet points; accessible language |
| `technical` | Lighting, composition, and quality evaluation (no camera speculation) |
| `colorful` | Emphasizes specific color names (crimson, navy, ivory, etc.) |
| `simple` | One-sentence basic description |
| `accessibility` | Optimized for screen reader context; emphasizes spatial relationships |
| `comparison` | Uses analogies to familiar objects |
| `mood` | Emotional atmosphere and psychological tone |
| `functional` | Focuses on purpose, action, and utility |
| `aialttext` | Produces three website alt-text options at 25, 50, and 100 words |

**Sample outputs for the same image** (a photo of a golden retriever on a beach at sunset):

| Style | Sample output |
|---|---|
| `simple` | A golden retriever sits on a sandy beach at sunset. |
| `concise` | A golden retriever rests on a sandy beach, silhouetted against a warm orange sunset over calm ocean waters. |
| `detailed` | **SUBJECT:** A golden retriever sitting on sand. **SETTING:** Beach at sunset, ocean in background. **COLORS:** Golden fur, orange sky, blue-gray water, tan sand. **COMPOSITION:** Dog centered in foreground, horizon line in upper third. **DETAILS:** Dog faces the camera, tongue out, waves gently lapping at shoreline. |
| `narrative` | On the left, gentle waves roll onto a tan sandy beach. Centered in the foreground, a golden retriever sits facing the camera with its tongue out. Behind the dog, the ocean stretches to the horizon where a warm orange sunset fills the sky. |
| `aialttext` | **25 words:** Golden retriever sitting on sandy beach at sunset facing camera. **50 words:** A golden retriever with tongue out sits on a sandy beach in the foreground, silhouetted against a vibrant orange sunset over calm ocean waters. **100 words:** A golden retriever sits centered on a tan sandy beach, facing the camera with its tongue hanging out. Behind the dog, gentle waves lap at the shoreline. The ocean extends to the horizon where a warm orange and yellow sunset fills the sky. The lighting creates a silhouette effect on the dog's fur. |

---

### Creating Custom Prompts

**Via the CLI config file**

Add prompts to `~/.idt/config.json`:

```json
{
  "custom_prompts": {
    "museum_label": "Write a museum exhibit label for this artwork. Use 50–75 words. Begin with the most visually striking element.",
    "ecommerce": "Describe this product image for an e-commerce listing. Focus on visible features, materials, and condition. Avoid speculation about what is not visible."
  }
}
```

Then use them like any built-in style: `idt describe ~/Photos --prompt museum_label`

**Via the GUI Prompt Editor**

See [The Prompt Editor (GUI)](#the-prompt-editor-gui) below.

---

### The Prompt Editor (GUI)

**Tools → Edit Prompts...** (`Ctrl+Shift+P`) opens the prompt editor.

**Left panel:** List of all available prompts (built-in and custom).

**Right panel:** Editor showing:
- **Prompt name** — Editable; must be unique.
- **Prompt text** — Full text editor with character count.

**Buttons:**
- **Add New** — Create a new prompt from a blank template.
- **Duplicate** — Clone the selected prompt as a starting point.
- **Delete** — Remove a custom prompt (built-in prompts cannot be deleted, only overridden).

The **Default Settings** section at the bottom of the dialog lets you set the default provider, model, and prompt for all new batch jobs.

---

## Part 6: Advanced Features

### Video Frame Extraction

IDT extracts still frames from video files before describing them. The AI then describes each frame as an image.

**In the CLI:** Video extraction happens automatically when you run `idt describe` on a folder containing videos. Opt out with `--no-video`.

**In the GUI:** Videos appear in the image list as expandable nodes. Use **Process → Extract Video Frames...** to control extraction settings, or **Process → Describe Video with AI...** to run the full pipeline. To watch a video, select it and press **Enter** (or use **Process → Play Video**); it opens in your system's default video player.

When a batch includes videos (for example **Process → Process Undescribed Images (Entire Workspace)**), ImageDescriber describes the photos straight away and extracts the videos' frames at the same time. Each video's frames are added to the batch as soon as that video is done. The progress window shows both: an **Items Processed** line, whose total grows as videos finish, and an **Extracting Frames** line with the number of videos done. **Stop** stops both. Videos that were fully extracted keep their frames, and a video stopped partway is extracted again next time; quitting ImageDescriber partway keeps them too. If a batch stops before it finishes (the provider refused the request, for example because you were signed out, or ImageDescriber was quit or closed unexpectedly), opening the workspace again offers to resume it, and resuming extracts the videos it hadn't reached while describing the rest. While videos are still being extracted, the progress bar shows activity rather than a percentage, because the total is still growing.

**Extraction modes**

| Mode | CLI flag | Best for |
|---|---|---|
| Time interval | `--video-interval SECONDS` | Continuous footage (surveillance, timelapse) |
| Scene detection | `--scene THRESHOLD` | Events, films, talks (extracts on natural cuts) |

**Video GPS metadata:** If FFmpeg is installed, GPS coordinates recorded in the video file are copied into each extracted frame's EXIF data, enabling geocoding to work on video frames just as it does for photos. Install FFmpeg via **Tools → Install FFmpeg (for video GPS)...** in the GUI.

---

### Downloading Web Images

Use `idt download` or **File → Load Images From URL...** in the GUI to fetch images from a web page.

The tool:
1. Scrapes all `<img>` elements from the page.
2. Filters by minimum size if `--min-size` is specified.
3. Downloads images into a `.idtw` workspace (see [Workspaces (.idtw)](#workspaces-idtw)).
4. Records the original HTML `alt` attribute alongside each image.
5. Optionally describes and embeds in the same pass.

**Where images land:** Both the CLI and the GUI put downloads inside the workspace bundle, at `<workspace>.idtw/derived/downloads/<page title>-<timestamp>/`, never in a separate folder next to the workspace. In the CLI, `idt download <url> [directory]` resolves the workspace exactly like `idt describe --workspace` does: omit `[directory]` and it's named after the URL's domain under the workspace root (`~/Documents/idt` by default, see `idt config`); pass a name or path to target a specific workspace. Run `idt download <url> --describe` and check the printed `Location:` and `Workspace:` lines for the exact path. In the GUI, **File → Load Images From URL...** downloads into the current bundle's `derived/downloads/` folder (prompting you to save a workspace first if none is open yet).

**Common use case:** Generate accessibility-compliant alt text for images on an existing web page, then compare the AI-generated description with the existing alt text stored in the workspace.

---

### HEIC/HEIF Conversion

HEIC is the default format for photos taken on iPhones running iOS 11 and later. IDT handles HEIC transparently:

- In the CLI: HEIC files are converted to JPEG in memory before being sent to the AI. The conversion is cached in the workspace's `derived/converted/` folder.
- In the GUI: **Process → Convert HEIC Files...** converts a batch to JPEG. Originals are preserved.

HEIC works out of the box in the installed and standalone builds, which include `pillow-heif`. Running from source, `pip install -r requirements.txt` installs it.

---

### Geocoding — Location from GPS

When `--geocode` is used (CLI) or **Geocode GPS coordinates to city/state (requires internet)** is checked on the General tab of ImageDescriber's Processing Options dialog, IDT reverse-geocodes GPS coordinates from image EXIF data to human-readable place names using the OpenStreetMap Nominatim API.

The place name, and only the place name, is added to the start of the prompt:

```
Where this photo was taken, from the file's metadata: Paris, France
This comes from the file, not the picture, so the picture needn't show it. Use it where it helps, such as to name the place, and don't comment on it or say whether the picture confirms it.
```

ImageDescriber leaves out "such as to name the place", because it starts each description with the place itself ("Paris, France - …"); asked to name it, the model would say it twice. The date and camera are not sent to the AI. See [Metadata and Geocoding](#metadata-and-geocoding).

Geocoding results are cached in `~/.idt/geocode_cache.json` so each unique location is only looked up once.

**Privacy note:** GPS coordinates are sent to the Nominatim API (run by the OpenStreetMap Foundation) to resolve place names. If location privacy is a concern, use `--no-metadata` to disable all EXIF extraction.

---

### Embedding Descriptions into Images

After generating descriptions, you can write them directly into the image file metadata so the description travels with the file everywhere it goes—File Explorer, Finder, Lightroom, macOS Spotlight, iOS Photos, and any other app that reads EXIF or XMP metadata.

**CLI:** `idt embed <workspace>` or add `--embed` to the `describe` command to embed automatically after processing.

**GUI:** **File → Embed Descriptions into Images...**

Key points:
- Original files are **never modified** in copy mode (the default).
- Embedded copies are saved to `<workspace>/embedded/` and mirror the original subfolder structure.
- HEIC sources are converted to JPEG before embedding (HEIC is a read-only format for this purpose).
- In-place mode (modify originals) requires explicit confirmation and is not recommended unless you have backups.

#### Where the Description Is Stored

Different image formats have different metadata containers, so IDT writes to whichever fields that format actually supports:

| Format | Fields written |
|--------|----------------|
| JPEG | EXIF UserComment, XMP `dc:description` |
| PNG | tEXt `Description` chunk, XMP `dc:description` |
| WebP | EXIF UserComment |
| TIFF | ImageDescription tag, XPComment tag |

This matters for the next two sections: which field a format gets determines where the description shows up on your desktop. PNG files, for example, have no EXIF at all, so the Windows **Comments** column stays empty for them and you need the **Title** column instead.

#### Reading Embedded Descriptions on Windows

File Explorer can show the description as a column in Details view, which means you can read every description in a folder by arrowing down the list.

1. Open the folder holding the embedded copies (`<workspace>/embedded/`).
2. Switch to **Details** view (**Ctrl+Shift+6**, or the **View** menu).
3. Press **Tab** until focus reaches the column headers.
4. Press **Shift+F10** for the context menu of available columns.
5. Turn on **Comments** (JPEG, WebP and TIFF) or **Title** (JPEG, PNG and TIFF).

If the column you want is not on the short list, choose **More...** at the bottom of that menu and find it in the full list.

Once the column is on, arrow through the file list and the description is announced along with the file name. To read a single file's description instead, select it and press **Alt+Enter** for **Properties**, then move to the **Details** tab—the description appears under **Description → Title** and **Comments**.

You can also search on the embedded text: type it into the Explorer search box and Windows matches against these fields, so `sunset` finds every photo whose description mentions one.

**Choosing a column:**

| Your files are | Turn on |
|----------------|---------|
| JPEG (the usual case) | **Comments** or **Title**—both are filled |
| PNG | **Title** (PNG has no EXIF, so **Comments** stays blank) |
| WebP | **Comments**—requires the Microsoft WebP Image Extension (see below) |
| TIFF | **Comments** or **Title** |

**WebP needs a codec.** Explorer reads WebP metadata through the Microsoft WebP Image Extension. Windows 11 installs normally have it, but on Windows Server or a stripped-down build it may be missing—and without it Explorer shows *no* image columns for WebP at all, not just an empty Comments. If Dimensions is blank too, install the extension from the Microsoft Store.

#### Reading Embedded Descriptions on macOS

macOS has no Finder column for embedded descriptions—the **Comments** column in Finder's list view shows *Spotlight Comments*, which is a note stored separately by Finder, not the description inside the file. Turning it on will show nothing. Use one of these instead:

- **Finder Get Info** — select the file and press **Cmd+I**. The description appears in the **More Info** section. This is the quickest way to check a single file, and VoiceOver reads the field directly.
- **Preview** — open the image, then **Tools → Show Inspector** (**Cmd+I**). The **ⓘ** tab has **General**, **Exif** and **TIFF** panes showing the raw fields.
- **Spotlight search** — the description is indexed, so searching for a word from it finds the photo.
- **Terminal** — `mdls -name kMDItemDescription photo.jpg` prints the description for one file. To list a whole folder:

  ```bash
  for f in *.jpg; do echo "$f: $(mdls -raw -name kMDItemDescription "$f")"; done
  ```

- **Photos** — importing an embedded copy brings the description in as the photo's caption, where it is visible in the Info pane and searchable.

Unlike Windows, macOS needs no per-format advice here: Get Info and Preview read through ImageIO, which reports the description for JPEG, PNG, WebP and TIFF alike.

---

### Combining Multiple Workspaces

If you have descriptions spread across many workspace bundles—for example, one per event or per year—use `idt combine` to merge them into a single CSV for analysis, reporting, or import into another tool.

```bash
# Combine all workspaces under ~/Pictures into one CSV sorted by file name
idt combine ~/Pictures --output all-photos.csv --sort file
```

The CSV has one row per described image, with its active description: file name, source path, workspace, description text, model, provider, prompt name, timestamp, metadata context, token counts and alt text. See [idt combine](#idt-combine--merge-multiple-projects) for what each sort does.

---

### Piping and Scripting with idt

`idt describe` accepts image file paths from stdin when you pass `-` as the source:

```bash
# Describe images listed by another script
get_images.sh | idt describe - --provider anthropic --quiet
```

In `--quiet` mode, stdin mode prints, for each image, the image's full path, a tab, then the description. A description that runs over several lines keeps its line breaks, so check for that before splitting the output by line with `awk` or `cut`.

**Exit codes.** The describing commands (`idt describe`, including stdin mode, `idt download --describe`, `idt video` and `idt watch`) end with:

| Code | Meaning |
|---|---|
| `0` | Every picture tried was described, or there was nothing to describe |
| `1` | Nothing was described and at least one picture failed, or the run couldn't start |
| `2` | An option was wrong, such as `--limit 0`; nothing was run, and the message says what's wrong |
| `3` | Some pictures were described and some failed |

For `idt describe` and `idt video`, a video whose frames can't be extracted counts as a failure; for `idt video` without `--describe`, the codes count videos extracted rather than pictures described. For `idt watch`, they cover everything since it started, when you stop it with Ctrl+C.

```bash
# Stop a script when a run described nothing
idt describe ~/Photos/Trip --quiet --no-export
case $? in
  0) echo "All described" ;;
  3) echo "Some failed; run again to retry them" ;;
  2) echo "Check the options"; exit 2 ;;
  *) echo "Nothing described"; exit 1 ;;
esac
```

```bash
# Extract only descriptions into a text file
idt show ~/Photos --json | python -c "
import sys, json
for line in sys.stdin:
    obj = json.loads(line)
    if obj.get('described'):
        print(obj['description'])
" > descriptions.txt
```

---

## Part 7: IDT Chat

IDT Chat is a standalone chat client for Ollama, Claude, OpenAI, Claude Code (your Claude subscription) and, on a Mac with macOS 27, Apple Intelligence. It is not an image tool — attachments are supported, but the point is the conversation.

It exists because mainstream chat applications are poorly suited to screen reader use. The conversation is a list you arrow through, responses are announced once and completely rather than a token at a time, and every action has a keyboard shortcut.

### Starting a conversation

Launch **IDT Chat** from the Start menu (Windows) or from `Applications/IDT/IDTChat.app` (macOS).

The first time you send a message it asks for a provider and model. Two providers need no API key:

- **Ollama** works with no setup as long as Ollama is running.
- **apple** runs Apple Intelligence on the Mac itself. No API key, no account, no cost, and images never leave the machine; needs macOS 27 on Apple Silicon and a one-time `sudo fm license`. See [Apple Intelligence — On This Mac](#apple-intelligence--on-this-mac-macos-27-and-later).
- **Windows AI** isn't offered: it describes images but can't chat.
- **claude-code** uses your Claude Pro or Max subscription through the Claude Code app. Sign in once with `claude auth login`; the provider is only listed when Claude Code is installed. See [Claude Code — Your Claude Subscription](#claude-code--your-claude-subscription-windows-and-macos).

**claude** and **openai** need an API key — see [Setting Up API Keys](#setting-up-api-keys).

**MLX is not offered here, and that is deliberate.** ImageDescriber lists MLX on Apple Silicon and IDT Chat does not, which looks like an oversight and is not. MLX needs Apple's `mlx` and `mlx-vlm` libraries, which would take this app from about 40 MB to around 350 MB — worth paying in ImageDescriber, where describing a folder of photos locally is the whole point, and worth much less for chat, because Ollama now runs several models through MLX on Apple Silicon itself. Chatting with Ollama on a Mac already gets you the Metal acceleration. If you specifically want to chat with an MLX model, use the chat window inside ImageDescriber (**Process → Chat with AI Model**), which offers it. The picker hides MLX rather than listing an option that would fail the moment you chose it.

### The window

- **Conversations** (left) — every saved conversation. `Enter` opens one.
- **Conversation history** — the current exchange, one line per turn, each naming who spoke. Arrow keys move through it.
- **Selected message** — the full text of the highlighted turn. It is editable so you can select and copy from it; edits are not saved.
- **Your message** — `Enter` sends, `Shift+Enter` starts a new line.
- **Attachments** — files queued for the next message. The label states the count, so you can check it without moving focus.

### Attaching files

Use **Chat → Attach Files** (`Ctrl+Shift+A`), or paste an image straight from the clipboard with `Ctrl+Shift+V`. Select an attachment and press `Delete` to remove it.

Attachments are sent with your next message and then cleared — the model has seen them, so later turns do not re-upload them.

What each provider accepts:

| Provider | Accepts | Size limit |
|---|---|---|
| Ollama | JPEG, PNG, GIF, WebP, text files | None published for images |
| OpenAI | JPEG, PNG, GIF, WebP, **PDF**, text files | 32 MB per PDF |
| Claude | JPEG, PNG, GIF, WebP, **PDF**, text files | Larger pictures are scaled down to fit; 32 MB per PDF |
| Claude Code | JPEG, PNG, GIF, WebP, text files | Larger pictures are scaled down to fit |
| Apple Intelligence | JPEG, PNG, GIF, WebP, text files | None published for images |

**Text files** are `.txt`, `.log`, `.md`, `.csv`, `.html`, `.htm`, `.css`, `.js`, `.py`, `.json`, `.xml`, `.yaml` and `.yml`. Their text goes into your message, up to 1 MB per file. (In ImageDescriber's chat window, MLX takes images only.)

**HEIC and HEIF photos from an iPhone are converted to JPEG automatically** — no provider reads HEIC directly.

If you select several files and one cannot be sent, the rest are still attached and a dialog explains which failed and why. The **Attach Files** command is unavailable for providers that take no attachments; switching to such a provider clears anything queued and says so, rather than silently dropping it later.

### How responses are announced

Streaming text is *not* read aloud as it arrives — that would flood a screen reader. Text accumulates silently, then is announced once when complete. Choose how much is said under **View**:

| Setting | What is announced |
|---|---|
| Announce the full response | The whole reply |
| Announce a summary | The first sentence and the word count |
| Announce nothing | Nothing; the status bar still updates |

Use **View → Read Last Response** (`Ctrl+Shift+R`) to hear a reply again at any time.

### Keyboard shortcuts

On macOS every `Ctrl` below is `Cmd`. The complete list for both applications,
including the Windows `Alt` keys, is in
[KEYBOARD_SHORTCUTS.md](KEYBOARD_SHORTCUTS.md); **Help → Keyboard Shortcuts**
(`F1`, or `Cmd+?` on a Mac) shows it in the app, named for the platform you
are on.

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Shift+Enter` | New line in the message box |
| `Ctrl+Return` | Send from anywhere in the window |
| `Ctrl+N` | New chat |
| `Ctrl+Shift+M` | Change provider or model |
| `Ctrl+Shift+A` | Attach files |
| `Ctrl+Shift+V` | Paste an image from the clipboard |
| `Delete` | In the conversation list: delete that conversation (with confirmation). In the attachments list: remove that attachment |
| `Enter` | In the conversation list: open it. In the transcript: read the message again |
| `Ctrl+Shift+P` | Set the system prompt |
| `Ctrl+Shift+K` | Turn web search on or off (Ollama models with tool support) |
| `Ctrl+R` | Regenerate the last response |
| `Ctrl+.` | Stop the response in progress (and stop it being read aloud) |
| `Ctrl+Shift+R` | Read the last response again |
| `Ctrl+C` | Copy — the selection in a text box, or the selected message when the transcript has focus |
| `Ctrl+Shift+C` | Copy the whole conversation |
| `Ctrl+Shift+E` | Export the conversation |
| `Ctrl+T` | Token usage |
| `F1` | Shortcut list |

`Ctrl+Shift+M` rather than `Ctrl+M`, and `Ctrl+Shift+E` rather than `Ctrl+E`,
because wx maps every `Ctrl` accelerator to `Cmd` on macOS: `Cmd+M` minimises
the window and `Cmd+E` is "use selection for find". `Ctrl+C` is a normal Copy
so you can copy a selection out of the message box.

On Windows, `Alt` reaches the menus and the controls: `Alt+F` `Alt+E` `Alt+C`
`Alt+V` `Alt+H` for the five menus, and `Alt+O` conversations, `Alt+I`
transcript, `Alt+M` selected message, `Alt+Y` your message, `Alt+N`
attachments, `Alt+S` Send, `Alt+T` Stop, `Alt+A` Attach, `Alt+R` Remove.

### System prompts

**Chat → Set System Prompt** (`Ctrl+Shift+P`) sets standing instructions for the conversation — a persona, a required tone, a format to answer in. It is saved with the conversation and applies to every turn.

### Switching models mid-conversation

**Chat → Change Model** (`Ctrl+Shift+M`) switches provider or model without losing history. The new model receives everything said so far, and each turn records which model produced it, so the history shows who said what.

### Thinking

**Chat → Thinking** chooses whether a reasoning model thinks before it answers:

- **Automatic** (the default): the model decides.
- **On**: it thinks.
- **Off**: it answers straight away, which is much faster on a thinking model. Claude and OpenAI can't switch reasoning off, so for them Off means the least effort the model takes. On reaches Ollama, Claude and OpenAI; other providers decide for themselves.

While a model thinks, the status bar says "Model is thinking…". The choice applies from your next message and lasts until IDT Chat closes.

### Stopping a response

`Ctrl+.` or the **Stop** button ends a reply in progress. **The partial response is kept**, not discarded — you watched it arrive, so it stays in the transcript.

### Token usage

`Ctrl+T` shows two numbers, which are genuinely different:

- **Context window in use** — the most recent exchange, which is what occupies the model's context.
- **Billed this conversation** — the sum across every turn, which is what you pay for.

When a conversation outgrows the model's context window, the oldest turns are dropped and the app says so rather than doing it silently.

### Where conversations are stored

Conversations are saved automatically — there is no Save command — one JSON file per conversation:

| Platform | Location |
|---|---|
| Windows | `C:\Users\<you>\.idt\chats\` |
| macOS / Linux | `~/.idt/chats/` |

A conversation is written after **every turn**, so nothing is lost if the app closes unexpectedly. Files are named by conversation id, for example `chat_a1b2c3d4e5f6.json`.

They stay there until you delete them. **File → Delete Chat**, or selecting a conversation and pressing `Delete`, removes the file permanently after asking you to confirm. Nothing else prunes them: there is no age limit and no size cap.

The format is the same one ImageDescriber uses for chat items inside a `.idtw` bundle, so a conversation can be copied between them. Because they are plain JSON, you can also back them up, read them, or delete them with any file manager.

**Attachments are referenced, not copied.** A conversation records the path to a file you attached, not its contents. Moving or deleting the original means it cannot be re-sent, though the text of the conversation is unaffected.

### Chatting from the terminal

The same engine backs `idt chat`:

```bash
idt chat
```

```bash
idt chat --provider claude --system "Answer in one sentence." --message "What is HEIC?"
```

`idt chat --list` shows saved conversations and `idt chat --resume <id>` continues one. Responses stream to the terminal; `Ctrl+C` stops a reply and keeps what arrived.

---

## Part 8: Accessibility

### Screen Reader Compatibility

**ImageDescriber GUI**

| Screen reader | Platform | Support level |
|---|---|---|
| NVDA | Windows | Full (TreeCtrl with MSAA) |
| JAWS | Windows | Full (TreeCtrl with UIA) |
| VoiceOver | macOS | Full (custom NSOutlineView adapter) |
| Narrator | Windows | Tested and working |

The chat window and description list use `wx.ListBox` instead of tree controls, providing a single tab stop and reliable screen reader announcement of new content.

All interactive controls have accessible names set via `SetAccessibleName()`. Separator rows in lists are automatically skipped during keyboard navigation.

**idt CLI**

The CLI uses no ANSI color codes in interactive mode (`idt guideme`) and all output is plain text. Progress messages are written to stdout as plain lines. The `--quiet` flag reduces output to the minimum needed for piping.

---

### Keyboard Navigation

**All features in the GUI are reachable by keyboard.** No action requires a mouse.

**Image list:** Up and Down Arrow to move, Right Arrow to expand a folder or video, Left Arrow to collapse it. Enter plays a video or reopens a saved chat. Single letters such as `P` (process) and `R` (rename) act on the selected item; see [Keyboard Shortcuts](#keyboard-shortcuts).

**Tab order:** Image list → Description list → Description editor → Generate Description → Save Description. Shift+Tab moves backward. The image preview is never a Tab stop. In Viewer mode: Refresh → Live Monitoring (skipped for a workspace) → the list → Description → Copy Text → Copy Image.

**Menu bar:** Alt (Windows) or Ctrl+F2 (macOS) activates the menu bar. All menu items have keyboard equivalents shown in the menu.

---

### Accessible Output

**HTML reports** generated by `idt export --format html` and **File → Export HTML Gallery** include:

- Skip navigation link at the top of the page
- Proper HTML5 landmark regions (`<main>`, `<nav>`, `<header>`, `<footer>`)
- Correct heading hierarchy (single H1 per page)
- All images have `alt` attributes set to the AI-generated description
- Tables use `<caption>` and `<th scope>` attributes
- No color-only information
- Works without JavaScript
- Passes WCAG 2.2 Level AA

---

## Part 9: Troubleshooting

### Common Issues

**No models showing in the GUI**

- Ollama: Open a terminal and run `ollama list`. If nothing appears, open `http://127.0.0.1:11434` in a browser. If that fails, restart Ollama or reinstall it.
- OpenAI / Claude: Check that a key is saved under **Tools → Configure Settings → API Keys** (on a Mac, **ImageDescriber → Preferences → API Keys**), or that the `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` environment variable is set. On that tab, select the provider and choose **Test Key** (`Alt+T`): the **Test result** box says whether the key works and, if not, what's wrong and what to do. See [Setting Up API Keys](#setting-up-api-keys). Run `idt models` to see whether each provider answers.

**Processing completes but descriptions are blank or very short**

- Some models (especially small Ollama models on CPU) time out if the image is very large. Try resizing images to under 2048 × 2048 pixels before describing.
- Switch to a higher-quality model: `claude-opus-5-5` or `gpt-6.2-sol`.

**Video extraction fails**

- Check that `opencv-python` is installed: `pip install opencv-python`.
- For GPS from video: install FFmpeg via **Tools → Install FFmpeg (for video GPS)...** or from [ffmpeg.org](https://ffmpeg.org).

**HEIC images not recognized**

- Running from source: install `pillow-heif` (`pip install pillow-heif`).
- Using a packaged build: `pillow-heif` is already included, so a HEIC that isn't
  recognized is a bug worth reporting rather than a missing dependency.

**The GUI silently does nothing when I click a button**

- Run the application from the terminal to see error output:
  ```bat
  cd imagedescriber
  .winenv\Scripts\python imagedescriber_wx.py
  ```
  Reproduce the action. Any exception will appear in the terminal immediately.

**"Permission denied" errors on macOS**

- If you downloaded the app, macOS Gatekeeper may quarantine it. Open **System Settings → Privacy & Security** and allow the app to run, or right-click and choose **Open** the first time.

---

### Diagnostic Steps

1. Check the version: `idt version` — confirm you are running the expected version.
2. Check the log: look in `<workspace>/logs/*.log` for the last processing run.
3. Test with a single image and `--show-descriptions` to see the raw AI output:
   ```bash
   idt describe ~/Photos --limit 1 --show-descriptions
   ```
4. Test connectivity: `idt models` to verify providers respond.
5. Test config: `idt config` to see current defaults.

---

## Appendix A: Supported File Formats

### Image Formats

| Format | Extension(s) | Notes |
|---|---|---|
| JPEG | `.jpg`, `.jpeg` | Native; best supported |
| PNG | `.png` | Native |
| WebP | `.webp` | Native |
| GIF | `.gif` | Static frame only |
| TIFF | `.tiff`, `.tif` | Converted to JPEG before API |
| BMP | `.bmp` | Converted to JPEG before API |
| HEIC / HEIF | `.heic`, `.heif` | Converted to JPEG; `pillow-heif` is included in the builds |

### Video Formats

| Format | Extension(s) |
|---|---|
| MPEG-4 | `.mp4`, `.m4v` |
| QuickTime | `.mov` |
| AVI | `.avi` |
| Matroska | `.mkv` |
| Windows Media | `.wmv` |
| MPEG Transport Stream | `.mts`, `.m2ts` |

---

## Appendix B: Configuration File Reference

This is the command line's own settings file, the one `idt config` shows and changes. ImageDescriber's settings are in other files; see the [Configuration Guide](CONFIGURATION_GUIDE.md).

**Location:** `~/.idt/config.json`

The file holds only the defaults you set with `idt config --set`, named again under `user_set`. In this example only the provider and model were set, so the default prompt follows Configure:

```json
{
  "default_provider": "anthropic",
  "default_model": "claude-haiku-5-5",
  "user_set": ["default_model", "default_provider"],
  "default_model_provider": "anthropic",
  "custom_prompts": {
    "my_prompt": "Describe this image for a museum label. 50–75 words.",
    "product_shot": "E-commerce product description: visible features, materials, condition."
  },
  "copy_originals": false,
  "preserve_alt_text": true,
  "auto_check_updates": true,
  "workspace_root": "/home/yourname/Documents/idt"
}
```

| Key | Default | Description |
|---|---|---|
| `default_provider` | Configure's default provider (`ollama` as shipped) | AI provider used when none is specified. Present only when set with `idt config` |
| `default_model` | Configure's default model (`minicpm-v4.6` as shipped), used with Ollama | Model used when none is specified. Present only when set with `idt config` |
| `default_prompt_name` | Configure's default prompt style (`narrative` as shipped) | Prompt style for a new workspace. Present only when set with `idt config` |
| `user_set` | `[]` | Which of the three defaults above were set with `idt config` |
| `default_model_provider` | none | The provider `default_model` was set for. If the default provider later changes to a different one, that model isn't sent to it; the new provider's default model is used instead. Written by `idt config`; don't edit it by hand |
| `workspace_root` | `~/Documents/idt` | Root folder where new workspaces are created |
| `custom_prompts` | `{}` | Dictionary of name → prompt text for user-defined styles. Edit the file to add them; `idt config --set` can't |
| `preserve_alt_text` | `true` | Whether `idt download` saves a page's alt text as its own description |
| `copy_originals` | `false` | Whether new workspaces copy the pictures in. Edit the file to change it, or use `--copy-originals` per run |
| `auto_check_updates` | `true` | Whether ImageDescriber checks for a newer release at startup. **Help → Automatically Check for Updates** changes it |

---

## Appendix C: Workspace File Structure

```
MyTrip.idtw/                        Workspace bundle (a folder ending in .idtw)
  manifest.json                     Job metadata
  images/                           Copies of source images, only with --copy-originals
  descriptions/                     JSON description sidecars
    vacation-photo-001.jpg.json
    vacation-photo-002.jpg.json
  derived/
    converted/                      HEIC → JPEG conversions
    frames/                         Extracted video frames
  logs/                             Processing logs (one per run)
  embedded/                         Images with embedded metadata
  reports/
    descriptions.html
    descriptions.csv
    descriptions.txt
```

**`manifest.json` key fields**

```json
{
  "format": "idtw",
  "version": "1.0",
  "name": "MyTrip",
  "created": "2024-09-12T10:00:00+00:00",
  "modified": "2024-09-12T11:30:00+00:00",
  "sources": [{"path": "/Users/you/Photos/Trip", "added": "2024-09-12T10:00:00+00:00"}],
  "defaults": {
    "provider": "anthropic",
    "model": "claude-opus-5-5",
    "prompt_name": "detailed"
  },
  "geocode_enabled": true,
  "cli_commands": [
    {"command": "idt describe /Users/you/Photos/Trip --provider anthropic", "timestamp": "..."}
  ]
}
```

**Description sidecar format** (`descriptions/photo.jpg.json`)

```json
{
  "image": "photo.jpg",
  "source_path": "/Users/you/Photos/Trip/photo.jpg",
  "descriptions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "text": "A group of hikers resting on a mountain ridge...",
      "provider": "anthropic",
      "model": "claude-opus-5-5",
      "prompt_name": "detailed",
      "created": "2024-09-12T10:15:32+00:00",
      "input_tokens": 512,
      "output_tokens": 183,
      "metadata_context": "Zugspitze, Germany"
    }
  ],
  "active_description_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## Appendix D: Keyboard Shortcut Reference

The shortcuts you are most likely to reach for. For the complete set —
every menu item in both apps, every Alt mnemonic on Windows, and the
chords the operating systems have already claimed — see
[KEYBOARD_SHORTCUTS.md](KEYBOARD_SHORTCUTS.md).

### Global Shortcuts

| Action | Windows / Linux | macOS |
|---|---|---|
| New Workspace | Ctrl+N | Cmd+N |
| Open Workspace | Ctrl+O | Cmd+O |
| Save Workspace | Ctrl+S | Cmd+S |
| Save Workspace As | Ctrl+Shift+S | Cmd+Shift+S |
| Load Directory | Ctrl+L | Cmd+L |
| Refresh Folder from Disk | Ctrl+Shift+R | Cmd+Shift+R |
| Load from URL | Ctrl+U | Cmd+U |
| Export HTML Gallery | Ctrl+Shift+H | Cmd+Shift+H |
| Workspace Statistics | Ctrl+I | Cmd+I |
| Chat with AI Model | Ctrl+T | Cmd+T |
| Stop All Processing | Ctrl+. | Cmd+. |
| User Guide | F1 | Cmd+? |
| Exit / Quit | Ctrl+Q | Cmd+Q |

### Edit

| Action | Windows / Linux | macOS |
|---|---|---|
| Undo | Ctrl+Z | Cmd+Z |
| Redo | Ctrl+Y | Cmd+Shift+Z |
| Cut | Ctrl+X | Cmd+X |
| Copy | Ctrl+C | Cmd+C |
| Paste | Ctrl+V | Cmd+V |
| Select All | Ctrl+A | Cmd+A |

### View and Navigation

| Action | Shortcut |
|---|---|
| Update Image List | F5 (Cmd+R on macOS) |
| Filter: All Items | Ctrl+Shift+A |
| Filter: Described Only | Ctrl+Shift+D |
| Filter: Undescribed Only | Ctrl+Shift+U |
| Find Images (search bar) | Ctrl+F |
| Edit Prompts | Ctrl+Shift+P |
| Configure Settings | Ctrl+Shift+C (Cmd+, for Preferences on macOS) |

On macOS, the Ctrl+ shortcuts in this table are Cmd+.

### Image List Navigation

| Action | Key |
|---|---|
| Move up/down | Up and Down Arrow |
| Expand folder or video | Right Arrow |
| Collapse folder or video | Left Arrow |
| Play a video, or reopen a saved chat | Enter |
| Process the selected image (or a folder's undescribed images) | P |
| Rename the selected item | R or F2 |
| Add a manual description | M |
| Ask a follow-up question | F |
| Open the chat window | C |
| Paste an image from the clipboard into the workspace | Ctrl+V |

The single letters work in the image list and the description list, not while you're typing in a text box.

---

*Image Description Toolkit is an open-source project. Contributions, bug reports, and feedback are welcome at the [project repository](https://github.com/TheIdeaPlace/Image-Description-Toolkit).*
