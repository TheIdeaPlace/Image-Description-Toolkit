# Image Description Toolkit

AI-powered batch image description tool supporting multiple vision models: Ollama, OpenAI, Claude (through the API or through your Claude subscription), Apple Intelligence on a Mac and Windows AI on a Copilot+ PC.

## Quick Start

### Installation

Download from the [latest release](https://github.com/TheIdeaPlace/Image-Description-Toolkit/releases/latest). In these names, `<version>` is the release number, such as 4.9.0:

- **`ImageDescriptionToolkitSetup-<version>-windows.exe`**: the installer for Windows 10 and 11, 64-bit.
- **`IDT-<version>-macos-arm64.dmg`**: the disk image for macOS on Apple Silicon.

Either one gives you all the applications:
- **idt** - Command-line interface for batch processing and automation
- **ImageDescriber** - GUI with integrated viewer, prompt editor, and configuration manager
- **IDT Chat** - An accessible chat client for Ollama, Claude, OpenAI, Claude Code and Apple Intelligence. Not an image tool: it is a general-purpose chat application built for keyboard and screen reader use.

One install covers them all; you never update them separately.

Standalone builds are also published if you want a single tool without an installer:
`idt-<version>-windows-x64.zip`, `ImageDescriber-<version>-windows-x64.zip`,
`IDTChat-<version>-windows-x64.zip`, and `idt-<version>-macos-arm64.tar.gz`.
Each Windows zip holds a folder: unzip it and run the exe inside, keeping the
`-lib` folder beside it.
`SHA256SUMS.txt` lets you verify any download.

No Python required. The Windows installer is signed; the macOS build is signed and
notarized.

For what's new in 4.9.0, see the [4.9.0 release notes](docs/release-notes-v4.9.0.md).

### Quick Start

#### GUI (Easiest for Most Users)

1. **Install** Image Description Toolkit with the installer.
2. **Launch** ImageDescriber from the Start menu. It is installed in `C:\idt` by default.
3. **Choose** a folder of images with File → Load Directory.
4. **Describe** them with Process → Process Undescribed Images (Entire Workspace).
5. **Save the workspace** when asked. Before the first batch, ImageDescriber asks where to save a workspace bundle. Choose Yes, and a folder picker opens in `Documents\idt`; press Enter to accept it. Then a box asks for the workspace's name, filled in with your folder's name; press Enter to accept that too. The results go in `Documents\idt\<folder name>.idtw`.
6. **Confirm** the number of images to process, then choose your AI provider, model and prompt style in the dialog that opens, and start. Use Tools → Edit Prompts to customize description styles, and View → Application Mode → Viewer Mode to browse results.

#### Command Line (For Batch Processing)

1. **Open** "Image Description Toolkit (CLI)" from the Start menu. It opens a command prompt in the install folder. If you chose "Add to PATH" when installing, any command prompt works.
2. **Run** the interactive guide: `idt guideme`
3. **Answer** the prompts to choose a provider, model and folder, and to run the job.

Results are saved in a workspace bundle, `Documents\idt\<folder name>.idtw`, with an HTML report in its `reports` folder. You can open the same workspace in ImageDescriber.

### Advanced Usage

```bash
# Describe a folder of images
idt describe path/to/images

# Check whether a newer version is available
idt update
```

## Features

- **Three Applications**: ImageDescriber for a visual workflow, `idt` for automation, and IDT Chat for conversation
- **Multiple AI Providers**: Ollama (local), OpenAI, Claude (API key), Claude Code (your Claude Pro/Max subscription, no API key), Apple Intelligence (on-device on macOS 27, no API key), Windows AI (on-device on Copilot+ PCs, no API key)
- **Batch Processing**: Process directories of images automatically
- **Video Frame Extraction**: Extract and describe frames from videos
- **Integrated Viewer**: Browse and monitor results in real time (built into ImageDescriber)
- **Integrated Tools**: Prompt editor and configuration manager built into ImageDescriber
- **Shared Workspaces**: The command line and ImageDescriber read and write the same `.idtw` workspaces
- **Re-describe Feature**: Test different models and prompts on the same images
- **Reports and Costs**: Export to HTML, CSV or text, embed descriptions into image copies, and see token use and estimated cost with `idt stats`

## Documentation

### User Guides
- **[Release Notes (v4.9.0)](docs/release-notes-v4.9.0.md)** - What IDT is and what's in 4.9.0
- **[User Guide](docs/USER_GUIDE.md)** - Complete usage instructions, including the full CLI reference
- **[macOS Setup](MACOS_SETUP.md)** - macOS installation and usage

### Configuration & Setup
- **[Configuration Guide](docs/CONFIGURATION_GUIDE.md)** - Where settings are kept, the Configure dialog, and API keys

### Developer Documentation
- **[Build Guide (Windows)](BuildAndRelease/README.md)** - Windows build instructions
- **[Build Guide (macOS)](BuildAndRelease/MacBuilds/README_MACOS.md)** - macOS build instructions
- **[Changelog](CHANGELOG.md)** - Version history

## Requirements
- **Pre-built Executable**: No Python required - download installer from releases
- **AI Provider** (choose one or more):
  - [Ollama](https://ollama.com) (free, runs locally) - **Recommended for most users**
  - [OpenAI API](https://platform.openai.com/api-keys) (paid)
  - [Claude API](https://console.anthropic.com) (paid)
  - Claude Code, with a Claude Pro or Max subscription
  - Windows AI, on a Copilot+ PC
  - Apple Intelligence, on a Mac with macOS 27

### macOS
- **Apple Silicon** — the published build is arm64 only. Intel Macs need to build from source.
- **No Python required** for the pre-built app
- **Installation**: Download `IDT-<version>-macos-arm64.dmg` from releases, open it, and drag the **IDT** folder to Applications. It holds ImageDescriber, IDT Chat and the `idt` command-line tool
- **Build from Source**: See [macOS Build Guide](BuildAndRelease/MacBuilds/README_MACOS.md)
- **AI Providers**: Same as Windows (Ollama, OpenAI, Claude, Claude Code), plus Apple Intelligence on macOS 27 and MLX on Apple Silicon

### Development (All Platforms)
- **Python 3.10+** (for development only, not required for built executables)
- **AI Provider** (choose one or more):
  - Ollama (local, free)
  - OpenAI API key
  - Anthropic Claude API key

## Support

- **Issues**: [GitHub Issues](https://github.com/TheIdeaPlace/Image-Description-Toolkit/issues)
- **Documentation**: See `docs/` directory
- **Repository**: https://github.com/TheIdeaPlace/Image-Description-Toolkit

## License

MIT License - see [LICENSE](LICENSE) file for details.
