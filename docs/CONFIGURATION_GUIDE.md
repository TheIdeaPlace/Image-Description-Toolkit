# Configuring IDT

**Version:** 4.9.0
**Last Updated:** 11/18/2026

This guide explains where Image Description Toolkit (IDT) keeps its settings, how to change them, and how to give it API keys. It covers the `idt` command line, ImageDescriber and IDT Chat.

Most people never need to open a settings file. ImageDescriber's **Tools → Configure Settings** dialog (on a Mac, **Preferences**) changes everything described here, and `idt config` changes the command line's few settings of its own.

---

## Contents

1. [The short version](#the-short-version)
2. [Where settings are kept](#where-settings-are-kept)
3. [How IDT chooses which file to read](#how-idt-chooses-which-file-to-read)
4. [The Configure dialog](#the-configure-dialog)
5. [The command line's own settings](#the-command-lines-own-settings)
6. [API keys](#api-keys)
7. [Export and Import Configuration](#export-and-import-configuration)
8. [Editing the files by hand](#editing-the-files-by-hand)
9. [Environment variables](#environment-variables)
10. [Troubleshooting](#troubleshooting)

---

## The short version

- Your settings are saved in your own settings folder:
  - Windows: `%APPDATA%\IDT` (for example `C:\Users\you\AppData\Roaming\IDT`)
  - macOS: `~/Library/Application Support/IDT`
  - Linux: `~/.config/IDT`
- The defaults that ship with IDT sit beside the programs, and are only used for anything you haven't changed. On Windows the installer puts them in `C:\idt\scripts`. Don't edit those: every upgrade replaces them.
- Configure, the Prompt Editor and Import Configuration all save to your settings folder. What you save there is what ImageDescriber and the command line use.
- API keys saved in Configure go to Windows Credential Manager or the macOS Keychain, not into a file.
- The command line follows Configure's default provider, model and prompt style. It also has a small settings file of its own, `~/.idt/config.json`, which holds only the defaults you set with `idt config --set` (those win for the command line), plus the workspace folder and a few other values. `idt config` shows and changes it.

---

## Where settings are kept

### Your settings folder

IDT saves your settings in three JSON files in your settings folder:

- **`image_describer_config.json`** holds most settings: the default provider, model and prompt style for ImageDescriber, the prompt styles themselves, the Generation settings, and the Processing, Metadata and Output Format settings. Both ImageDescriber and the command line read it.
- **`video_frame_extractor_config.json`** holds ImageDescriber's video frame extraction defaults: interval or scene mode, the interval, the scene threshold and the frame limit. The command line doesn't read it; `idt video` and `idt describe` take `--interval`, `--scene` and `--video-interval` instead.
- **`workflow_config.json`** holds the Workflow Settings tab. Nothing in IDT reads it any more: it belonged to the old `idt workflow` command, which 4.5 replaced with `idt describe`.

The files don't exist until something is saved. The first time you open Configure, it copies the shipped defaults into your settings folder.

The settings folder is:

- Windows: `%APPDATA%\IDT`
- macOS: `~/Library/Application Support/IDT`
- Linux: `~/.config/IDT`, or `$XDG_CONFIG_HOME/IDT` when that is set

The environment variable `IDT_USER_CONFIG_DIR` replaces this folder with one you choose.

### The shipped defaults

Each copy of IDT carries the default versions of the same three files:

- The Windows installer: `C:\idt\scripts` (the `scripts` folder in the install folder).
- The standalone Windows zips and the macOS app: inside the program's own files.
- Running from source: the repository's `scripts` folder.

These are read only for settings your own files don't have. They are replaced on every upgrade, so a change made there doesn't last.

### The command line's file

`~/.idt/config.json` (on Windows, `%USERPROFILE%\.idt\config.json`) holds any default provider, model or prompt you set with `idt config --set`, the workspace folder, and a few other values. See [The command line's own settings](#the-command-lines-own-settings).

The same `~/.idt` folder also holds saved `idt chat` conversations (`chats`), the cached model lists (`models`) and the geocoding cache (`geocode_cache.json`).

---

## How IDT chooses which file to read

For each of the three files, IDT reads the first one it finds:

1. Your settings folder (or `IDT_USER_CONFIG_DIR`).
2. The folder named by `IDT_CONFIG_DIR`, when that variable is set.
3. The shipped defaults beside the program.

Then, if your file is missing a whole section that the defaults have, IDT takes that section from the defaults. This is how a setting added in a newer version (such as `generation` in 4.9) reaches someone whose file is older.

It works on whole sections only. Inside a section you already have, nothing is filled in. So a prompt style you deleted in the Prompt Editor stays deleted, and a Generation setting you removed stays on Automatic.

Before 4.9 the order was different: the shipped files beside the program came first. On an installed Windows copy, that meant nothing saved in Configure reached processing or the command line. 4.9 fixed this.

---

## The Configure dialog

Open it with **Tools → Configure Settings** (`Ctrl+Shift+C`) in ImageDescriber. On a Mac it is **ImageDescriber → Preferences**.

The dialog has a tab for each group of settings. On each tab, the settings list comes first. Press Tab from the list to reach an **Explanation** box for the selected setting, which you can read with the cursor. Press Tab again for **Change Setting**, or press Enter on a setting to change it. **OK** saves and closes, **Apply** saves and stays open, and **Cancel** discards changes.

The tabs:

- **AI Model Settings**: ImageDescriber's default provider and default Ollama model.
- **Generation**: what IDT asks a model for besides the prompt, per provider. See [Generation settings](#generation-settings).
- **Prompt Styles**: the default prompt style. To add or change prompt styles, use **Tools → Edit Prompts** (`Ctrl+Shift+P`).
- **Video Extraction**: ImageDescriber's defaults for extracting video frames.
- **Processing Options**: image size, delay between images, and similar processing settings.
- **Metadata Settings**: EXIF reading and geocoding.
- **Workflow Settings**: kept from the old `idt workflow` command. Nothing reads these settings now.
- **Output Format**: what goes into text output.
- **API Keys**: add, edit and delete API keys. See [API keys](#api-keys).
- **Workspace**: the folder where new workspaces are saved. Blank means `Documents\idt` (`~/Documents/idt` on a Mac). This is the same setting as `idt config --set workspace_root=...`.
- **MLX Models** (Mac only): extra MLX models to offer.

### Generation settings

The **Generation** tab lists, for each provider, the settings it can use:

- Ollama: thinking, temperature, top p, top k, repeat penalty, output limit.
- OpenAI: thinking, effort, temperature, top p, output limit.
- Claude: thinking, effort, output limit.
- Claude Code: thinking, effort, output limit.
- Apple Intelligence (Mac only): temperature, output limit.
- MLX (Mac only): output limit.

Every setting starts on **Automatic**, which uses IDT's default for the provider and model. For Ollama, Automatic turns thinking off for descriptions, because the reasoning is thrown away and it is most of the time spent on each picture. A setting a model can't take is skipped, and the run log says so.

The command line uses the same Generation settings. For one run, `idt describe`, `idt download`, `idt video` and `idt watch` can override them with `--think`, `--no-think`, `--temperature` and `--max-tokens`. `idt guideme` takes no options and uses the saved settings.

The Generation tab replaced the old temperature, max tokens, top k, top p and repeat penalty settings, which were saved in a `model_settings` section. Nothing has read `model_settings` since June 2026, and 4.9 removed it from Configure. If your file still has one, it is ignored.

---

## The command line's own settings

`idt config` shows the command line's settings. After each of the default provider, model and prompt, it says where the value comes from: "(set with idt config)", "(from Configure)" or "(default)". `idt config --set KEY=VALUE` changes one and saves it in `~/.idt/config.json`.

The keys `idt config --set` accepts:

- `default_provider`: `anthropic` (or `claude`), `apple`, `claude-code`, `ollama`, `openai` or `Windows-AI`. Any other name is refused.
- `default_model`: the model to use when you don't give `--model`.
- `default_prompt_name`: the default prompt style for a new workspace. It must be one `idt prompts` lists; case doesn't matter.
- `workspace_root`: where new workspaces are created. The default is `Documents\idt` in your user folder.
- `preserve_alt_text`: `true` or `false`. Whether `idt download` saves a web page's alt text as its own description. The default is `true`.

The file can also hold `custom_prompts`, a list of your own prompt styles as name and text, and `copy_originals`, whether new workspaces copy the pictures in. Edit the file to change those. Custom prompts added here work only in `idt`; ImageDescriber doesn't offer them.

### How these relate to ImageDescriber's settings

The command line follows Configure's default provider, model and prompt style, except for any you set with `idt config --set`:

- `~/.idt/config.json` holds only the defaults set with `idt config --set`, and names them in a `user_set` list. Those win for the command line. To follow Configure again, delete the setting and its name in `user_set` from the file.
- Configure's default model is the Ollama model, so the command line uses it only with Ollama. Other providers use their own default model, such as `claude-haiku-5-5` for Claude.
- If Configure's default provider is one only ImageDescriber runs, such as MLX, the command line says so and uses Ollama.
- A file from before 4.9 has no `user_set`. If its default provider, model and prompt are all values IDT used to ship, they are treated as left over, and Configure's settings apply. If any of them differs, all three are kept as your choices.

What `idt describe` uses on a run:

- Provider: `--provider`, else the provider the workspace was last described with, else the default provider.
- Model: `--model`, else the workspace's or the default model when it belongs to that provider, else the provider's own default.
- Prompt: `--prompt` or `--prompt-text`, else the prompt the workspace last used, else the default prompt style. An unknown `--prompt` name stops the command with the list of prompt names.

These are shared between the two:

- The workspace folder (`workspace_root` and Configure's Workspace tab).
- The Generation settings.
- The prompt styles saved in the Prompt Editor.
- API keys.

---

## API keys

Claude (through the API) and OpenAI need an API key. Ollama, Claude Code, Apple Intelligence and Windows AI don't. Ollama's web search in `idt chat` and IDT Chat needs a free ollama.com key.

### Saving a key

The easy way is ImageDescriber's **Configure → API Keys** tab: arrow to the provider, choose **Add Key** (it reads **Replace Key** when the provider already has one) and paste the key. IDT saves it in Windows Credential Manager or the macOS Keychain, under the name "Image Description Toolkit". ImageDescriber, IDT Chat and the command line all use it.

**Test Key** on the same tab checks the selected provider's key with one short request and shows the result in the **Test result** box. For Claude and OpenAI that request costs a small fraction of a cent on your account; for Ollama web search it is one web search. It tests the key IDT would actually use, so if an environment variable outranks the saved key, the environment variable's key is the one tested.

On a system with no credential store (Linux), Configure saves the key in the `api_keys` section of `image_describer_config.json` instead.

### Where IDT looks for a key

IDT uses the first key it finds, in this order:

1. An environment variable: `ANTHROPIC_API_KEY` for Claude, `OPENAI_API_KEY` for OpenAI, `OLLAMA_API_KEY` for Ollama web search.
2. Windows Credential Manager or the macOS Keychain: where Configure saves keys.
3. The `api_keys` section of `image_describer_config.json`. Older versions of ImageDescriber saved keys there.
4. A plain text key file from older versions: `claude.txt` or `anthropic.txt` for Claude, `openai_api_key.txt` or `openai.txt` for OpenAI. IDT looks in the current folder and, for the installed programs, in the folder that holds the program. The file must contain only the key, with nothing else in it.

Because an environment variable comes first, an old key left in `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` wins over the one you saved in Configure. The API Keys tab shows where each provider's key comes from.

Keys are never stored in workspaces, and IDT never prints or logs them.

---

## Export and Import Configuration

ImageDescriber's **Tools** menu has both.

**Export Configuration** saves a zip file holding the three settings files IDT is using: your own copies where you have saved settings, and the shipped defaults otherwise. Use it to back up your settings or to move them to another computer.

- It does not include API keys kept in Windows Credential Manager or the macOS Keychain. Add those again on the other computer.
- It does include any keys in the `api_keys` section of `image_describer_config.json`. Keep the zip private if you have any there.
- It does not include the command line's `~/.idt/config.json`. Copy that file yourself if you want it.

**Import Configuration** asks before it replaces anything, then copies every `.json` file in the zip into your settings folder. Restart ImageDescriber afterwards to use the imported settings.

---

## Editing the files by hand

You can edit the files in your settings folder with any text editor, while ImageDescriber is closed.

- Keep the file valid JSON. IDT accepts a file saved with a byte-order mark, as PowerShell 5 writes one.
- If a file can't be read, IDT logs a warning and uses the shipped defaults for it, rather than overwriting it. Fix the file before you open Configure: Configure shows the defaults in its place, and **OK** or **Apply** would save them over your file.
- To go back to the defaults for one file, delete it from your settings folder. To go back to the defaults for everything, delete the whole folder. API keys in the credential store are not affected; remove those with **Delete Key** in Configure.
- Never edit the shipped defaults beside the program. An upgrade replaces them.

A Generation section looks like this. Leave a setting out to keep it on Automatic:

```json
"generation": {
  "ollama": {"thinking": "off", "temperature": 0.2},
  "openai": {"effort": "low"},
  "claude": {"max_output_tokens": 1200}
}
```

`thinking` takes `auto`, `on` or `off`. `effort` takes `minimal`, `low`, `medium` or `high`.

---

## Environment variables

- `IDT_USER_CONFIG_DIR`: use this folder as your settings folder instead of the usual one.
- `IDT_CONFIG_DIR`: a folder of default settings files, used for anything your own settings don't set. Read before the shipped defaults. Earlier Windows installers set this to `C:\idt\scripts`; the 4.9 installer removes it when it still points there.
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_API_KEY`: API keys. See [API keys](#api-keys).

---

## Troubleshooting

**A setting I changed in Configure isn't used.**

- Check that you're on 4.9 or later: `idt version`. Before 4.9, an installed copy read the shipped defaults before your saved settings.
- Check whether `IDT_CONFIG_DIR` or `IDT_USER_CONFIG_DIR` is set: in a Command Prompt, `set IDT`. If `IDT_USER_CONFIG_DIR` is set, your settings are saved and read there.
- For the command line's default provider, model and prompt, see [How these relate to ImageDescriber's settings](#how-these-relate-to-imagedescribers-settings). `idt config` shows the values the command line uses.

**My API key isn't found, or the wrong one is used.**

- Open **Configure → API Keys**. It says where each provider's key comes from.
- If it says the environment, an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` variable is set and wins. Remove the variable, or put the right key in it.
- A legacy key file must hold only the key.

**I want to start over.**

Close ImageDescriber and delete your settings folder (`%APPDATA%\IDT` on Windows, `~/Library/Application Support/IDT` on macOS). Delete `~/.idt/config.json` too for the command line's settings. The next time you open Configure, it copies the shipped defaults again.
