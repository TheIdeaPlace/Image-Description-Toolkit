"""Fixes from the 4.9.0 bug bash ("the IDT guru", S1-S4, S7, S8).

S1  video frames went missing on a non-ASCII path (cv2.imwrite fails silently
    on Windows); frames are now encoded in memory and written by Python.
S2  `idt download --describe --embed` crashed with NameError '_do_embed' after
    doing all the work.
S3  describing commands exited 0 when every picture failed. Now 0 all done (or
    nothing to do), 1 nothing described or couldn't start, 2 a wrong option
    (argparse's code), 3 some described and some failed.
S4  `idt show` couldn't find a picture in a subfolder of the described folder,
    and could pick an unrelated workspace named like the picture's folder.
S7  ImageDescriber said "Prompt: custom" for every CLI description.
S8  --limit, --interval, --scene, --video-interval and chat --max-tokens took
    out-of-range values without a word.

Everything here is windowless: the CLI runs in-process with a fake provider.
"""
import io
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cli.main as cli_main  # noqa: E402
from idt_core.providers.base import DescriptionResult  # noqa: E402

#: Non-ASCII on purpose: a Windows profile like C:\Users\José, a folder named 写真.
UNICODE_DIR = "é 写真"


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #

class FakeProvider:
    """Describes JPEGs; fails every PNG, so a test picks its failures by format."""

    def __init__(self, *_a, **_k):
        self.calls = 0

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return "fake"

    def describe(self, image_bytes, mime_type, prompt):
        self.calls += 1
        if "png" in (mime_type or ""):
            raise RuntimeError("model refused to load")
        return DescriptionResult(text=f"A picture, number {self.calls}.",
                                 provider="ollama", model="fake",
                                 input_tokens=10, output_tokens=5)


def _jpeg(path: Path, colour=(120, 80, 200)):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), colour).save(path, "JPEG")
    return path


def _png(path: Path):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), (10, 200, 30)).save(path, "PNG")
    return path


@pytest.fixture
def idt_home(tmp_path, monkeypatch):
    """A scratch ~/.idt/config.json whose workspace root is under tmp_path, and a
    fake provider in place of the real ones."""
    from idt_core import config as cfg_mod

    root = tmp_path / "wsroot"
    config_file = tmp_path / ".idt" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps({"workspace_root": str(root)}), encoding="utf-8")
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_file)
    monkeypatch.setattr(cli_main, "_make_provider", lambda *a, **k: FakeProvider())
    monkeypatch.setattr(cli_main, "_set_console_title", lambda *_a, **_k: None)
    return root


def run_idt(monkeypatch, *argv) -> int:
    """Run `idt <argv>` through main(), as the console does; return the exit code."""
    monkeypatch.setattr(sys, "argv", ["idt", *[str(a) for a in argv]])
    try:
        cli_main.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return 0


DESCRIBE = ("--provider", "ollama", "--model", "fake", "--no-export", "--no-metadata")


def _tiny_video(path: Path, seconds: int = 2, fps: int = 5) -> Path:
    """A small synthetic video, or skip when this OpenCV can't write one."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (32, 24))
    if not writer.isOpened():
        pytest.skip("OpenCV here can't write an MJPG video")
    for i in range(seconds * fps):
        frame = np.full((24, 32, 3), (i * 10) % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()
    if not path.exists() or path.stat().st_size == 0:
        pytest.skip("OpenCV here wrote an empty video")
    return path


# --------------------------------------------------------------------------- #
# S1: frames on non-ASCII paths                                                #
# --------------------------------------------------------------------------- #

def test_write_frame_writes_to_a_non_ascii_folder(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from idt_core.video import write_frame

    folder = tmp_path / UNICODE_DIR
    folder.mkdir()
    frame = np.zeros((12, 16, 3), dtype=np.uint8)
    frame[:, :, 2] = 255
    dest = write_frame(folder / "IMG_3136_0.00s.jpg", frame)

    assert dest.is_file() and dest.stat().st_size > 0
    decoded = cv2.imdecode(np.frombuffer(dest.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None and decoded.shape == (12, 16, 3)


def test_write_frame_uses_the_extension_for_the_format(tmp_path):
    pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from idt_core.video import write_frame

    (tmp_path / UNICODE_DIR).mkdir()
    dest = write_frame(tmp_path / UNICODE_DIR / "f.png", np.zeros((4, 4, 3), np.uint8))
    assert dest.read_bytes().startswith(b"\x89PNG")


def test_write_frame_raises_instead_of_failing_silently(tmp_path):
    pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    from idt_core.video import FrameWriteError, write_frame

    frame = np.zeros((4, 4, 3), np.uint8)
    with pytest.raises(FrameWriteError):
        write_frame(tmp_path / "no such folder" / "f.jpg", frame)     # can't write
    with pytest.raises(FrameWriteError):
        write_frame(tmp_path / "f.notanimageformat", frame)           # can't encode


def test_extract_frames_into_a_non_ascii_folder(tmp_path):
    from idt_core.video import VideoExtractionOptions, extract_frames_to_dir

    video = _tiny_video(tmp_path / "clip.avi")
    out = tmp_path / UNICODE_DIR / "frames"
    result = extract_frames_to_dir(video, out, VideoExtractionOptions(interval_seconds=1.0))

    assert result.frame_paths, "no frames extracted"
    for frame in result.frame_paths:
        assert frame.is_file(), f"frame listed but not written: {frame}"


def test_no_cv2_imwrite_left_in_the_apps():
    """Every frame writer goes through write_frame; imwrite fails silently on Windows."""
    for rel in ("idt_core/video.py", "imagedescriber/workers_wx.py",
                "imagedescriber/imagedescriber_wx.py", "cli/main.py"):
        text = (_ROOT / rel).read_text(encoding="utf-8")
        assert "cv2.imwrite(" not in text, f"{rel} still calls cv2.imwrite"


# --------------------------------------------------------------------------- #
# S3: exit codes                                                               #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("described, failed, code", [
    (0, 0, 0), (3, 0, 0), (2, 1, 3), (0, 1, 1), (0, 5, 1),
])
def test_describe_exit_code(described, failed, code):
    assert cli_main._describe_exit_code(described, failed) == code


def test_describe_all_described_exits_0(tmp_path, idt_home, monkeypatch):
    src = tmp_path / "Pics"
    _jpeg(src / "a.jpg")
    _jpeg(src / "b.jpg")
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 0


def test_describe_some_failed_exits_2(tmp_path, idt_home, monkeypatch):
    src = tmp_path / "Pics"
    _jpeg(src / "a.jpg")
    _png(src / "b.png")
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 3


def test_describe_all_failed_exits_1(tmp_path, idt_home, monkeypatch):
    src = tmp_path / "Pics"
    _png(src / "a.png")
    _png(src / "b.png")
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 1


def test_describe_nothing_to_do_exits_0(tmp_path, idt_home, monkeypatch):
    src = tmp_path / "Pics"
    _jpeg(src / "a.jpg")
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 0
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 0   # already described


def test_describe_returns_the_code_rather_than_exiting(tmp_path, idt_home, monkeypatch):
    """guideme calls cmd_describe and carries on to offer the report, so it returns."""
    src = tmp_path / "Pics"
    _jpeg(src / "a.jpg")
    _png(src / "b.png")
    monkeypatch.setattr(sys, "argv", ["idt"])
    args = cli_main.build_parser().parse_args(["describe", str(src), *DESCRIBE])
    assert cli_main.cmd_describe(args) == 3


def _stdin(monkeypatch, lines):
    data = ("\n".join(str(p) for p in lines) + "\n").encode("utf-8")
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(data), encoding="utf-8"))


def test_stdin_mode_missing_path_counts_as_a_failure(tmp_path, idt_home, monkeypatch):
    good = _jpeg(tmp_path / "in" / "a.jpg")
    _stdin(monkeypatch, [good, tmp_path / "in" / "gone.jpg"])
    assert run_idt(monkeypatch, "describe", "-", *DESCRIBE) == 3


def test_stdin_mode_all_failed_exits_1(tmp_path, idt_home, monkeypatch):
    _stdin(monkeypatch, [_png(tmp_path / "in" / "a.png")])
    assert run_idt(monkeypatch, "describe", "-", *DESCRIBE) == 1


def test_stdin_mode_all_described_exits_0(tmp_path, idt_home, monkeypatch):
    _stdin(monkeypatch, [_jpeg(tmp_path / "in" / "a.jpg")])
    assert run_idt(monkeypatch, "describe", "-", *DESCRIBE) == 0


def test_watch_reports_the_whole_watch_when_stopped(tmp_path, idt_home, monkeypatch):
    src = tmp_path / "Inbox"
    _jpeg(src / "a.jpg")
    _png(src / "b.png")

    def _stop(_seconds):
        raise KeyboardInterrupt
    monkeypatch.setattr("time.sleep", _stop)
    assert run_idt(monkeypatch, "watch", src, "--provider", "ollama", "--model", "fake",
                   "--no-metadata", "--quiet") == 3


def test_video_describe_exit_code_and_unicode_workspace(tmp_path, monkeypatch, idt_home):
    """S1 end to end: the workspace path has non-ASCII characters, as it does for
    anyone whose Windows profile name does. The frames must be on disk and described."""
    from idt_core import config as cfg_mod

    root = tmp_path / UNICODE_DIR / "idt"
    cfg_mod._CONFIG_FILE.write_text(json.dumps({"workspace_root": str(root)}), encoding="utf-8")
    video = _tiny_video(tmp_path / "Movies" / "clip.avi")

    code = run_idt(monkeypatch, "video", video, "--interval", "1", "--describe",
                   "--provider", "ollama", "--model", "fake", "--quiet")
    assert code == 0

    from idt_core.workspace import Workspace
    ws = Workspace.open(root / "Movies.idtw")
    frames = [i for i in ws.items() if i.item_type == "extracted_frame"]
    assert frames, "no frames registered"
    for item in frames:
        assert ws.image_path(item).is_file(), f"frame not on disk: {ws.image_path(item)}"
        assert item.described


# --------------------------------------------------------------------------- #
# S2: download --describe --embed                                              #
# --------------------------------------------------------------------------- #

@pytest.fixture
def fake_download(tmp_path, monkeypatch):
    """download_into_workspace without the network: adds local pictures."""
    from idt_core import downloader
    from idt_core.downloader import WorkspaceDownloadResult

    pictures = [_jpeg(tmp_path / "site" / "one.jpg"), _jpeg(tmp_path / "site" / "two.jpg")]

    def _download(ws, url, **_kwargs):
        result = WorkspaceDownloadResult(workspace=ws, subfolder="downloads/site")
        for p in pictures:
            result.items.append(ws.add_image(p, subfolder="downloads/site", copy=True))
            result.downloaded += 1
        return result

    monkeypatch.setattr(downloader, "download_into_workspace", _download)
    return pictures


def test_download_describe_embed_finishes_cleanly(tmp_path, idt_home, monkeypatch,
                                                  fake_download, capsys):
    code = run_idt(monkeypatch, "download", "https://example.com/gallery", "site",
                   "--describe", "--embed", "--provider", "ollama", "--model", "fake",
                   "--no-preserve-alt-text")
    err = capsys.readouterr().err
    assert "_do_embed" not in err and "is not defined" not in err, err
    assert code == 0
    embedded = list((idt_home / "site.idtw" / "embedded").rglob("*.jpg"))
    assert len(embedded) == 2


def test_cmd_download_calls_only_defined_functions():
    """The leftover block called _do_embed, which was removed in 4.5.0."""
    assert "_do_embed(" not in (_ROOT / "cli" / "main.py").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# S4: idt show finds pictures in subfolders                                    #
# --------------------------------------------------------------------------- #

def test_show_finds_a_picture_in_a_subfolder(tmp_path, idt_home, monkeypatch, capsys):
    src = tmp_path / "Guru Photos"
    _jpeg(src / "top.jpg")
    _jpeg(src / "nested" / "outdoor.jpg", colour=(1, 2, 3))
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 0
    capsys.readouterr()

    assert run_idt(monkeypatch, "show", src / "nested" / "outdoor.jpg", "--json") == 0
    row = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert row["described"] is True
    assert Path(row["source"]) == src / "nested" / "outdoor.jpg"


def test_show_ignores_an_unrelated_workspace_named_like_the_folder(tmp_path, idt_home,
                                                                  monkeypatch, capsys):
    """A different folder also called "nested" has its own nested.idtw holding an
    outdoor.jpg; matching on the file name printed that picture's description."""
    other = tmp_path / "Elsewhere" / "nested"
    _jpeg(other / "outdoor.jpg")
    assert run_idt(monkeypatch, "describe", other, *DESCRIBE) == 0

    src = tmp_path / "Guru Photos"
    _jpeg(src / "nested" / "outdoor.jpg", colour=(9, 9, 9))   # never described
    capsys.readouterr()

    assert run_idt(monkeypatch, "show", src / "nested" / "outdoor.jpg") == 1
    out = capsys.readouterr()
    assert "No description found" in out.err
    assert "A picture" not in out.out


def test_show_still_finds_a_top_level_picture(tmp_path, idt_home, monkeypatch, capsys):
    src = tmp_path / "Guru Photos"
    _jpeg(src / "top.jpg")
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 0
    capsys.readouterr()
    assert run_idt(monkeypatch, "show", src / "top.jpg") == 0
    assert "A picture" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# S7: "Prompt: custom" only for prompts the user wrote                         #
# --------------------------------------------------------------------------- #

def test_named_prompt_with_its_own_text_is_not_custom():
    from idt_core.config import BUILT_IN_PROMPTS
    from idt_core.gui_bridge import is_custom_prompt, prompt_label

    name = "simple" if "simple" in BUILT_IN_PROMPTS else next(iter(BUILT_IN_PROMPTS))
    text = BUILT_IN_PROMPTS[name]
    assert not is_custom_prompt(name, text)
    assert prompt_label(name, text) == name
    # Stored with stray whitespace, or with the name capitalized as Configure once offered it.
    assert not is_custom_prompt(name, f"\n{text}  ")
    assert prompt_label(name.capitalize(), text) == name.capitalize()


def test_genuinely_custom_prompts_still_say_custom():
    from idt_core.config import BUILT_IN_PROMPTS
    from idt_core.gui_bridge import is_custom_prompt, prompt_label

    name = next(iter(BUILT_IN_PROMPTS))
    assert prompt_label("custom", "Describe it for a museum label.") == "custom"
    assert prompt_label("", "Describe it for a museum label.") == "custom"
    # ImageDescriber's own: the style picked, and the user's text in Custom Prompt.
    assert prompt_label(name, "Describe it for a museum label.") == "custom"
    # A name IDT doesn't know: its text can't be checked, so keep calling it custom.
    assert is_custom_prompt("no_such_style", "anything")


def test_no_prompt_text_is_never_custom():
    from idt_core.gui_bridge import is_custom_prompt, prompt_label

    assert not is_custom_prompt("narrative", "")
    assert not is_custom_prompt("narrative", None)
    assert prompt_label("narrative", "") == "narrative"


def test_cli_custom_prompt_from_idt_config_is_named(tmp_path, monkeypatch):
    """A prompt added to ~/.idt/config.json is a named style on the command line."""
    from idt_core import config as cfg_mod
    from idt_core.gui_bridge import prompt_label

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"custom_prompts": {"museum_label": "Write a label."}}),
                           encoding="utf-8")
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_file)
    assert prompt_label("museum_label", "Write a label.") == "museum_label"
    assert prompt_label("museum_label", "Something else.") == "custom"


def test_cli_description_reaches_the_gui_labelled_by_name():
    """The path the bug took: a CLI description, through the bridge, to the label."""
    from idt_core.config import BUILT_IN_PROMPTS
    from idt_core.gui_bridge import _ws_desc_to_gui, prompt_label
    from idt_core.workspace import WorkspaceDescription

    w = WorkspaceDescription.create(text="A desk.", model="fake", provider="ollama",
                                    prompt_name="narrative",
                                    prompt_text=BUILT_IN_PROMPTS["narrative"])
    gui = _ws_desc_to_gui(w)
    assert gui["custom_prompt"] == w.prompt_text          # still kept, losslessly
    assert prompt_label(gui["prompt_style"], gui["custom_prompt"]) == "narrative"


def test_imagedescriber_uses_prompt_label_everywhere():
    text = (_ROOT / "imagedescriber" / "imagedescriber_wx.py").read_text(encoding="utf-8")
    assert 'prompt_display = "custom"' not in text
    assert text.count("_prompt_label(") >= 3


# --------------------------------------------------------------------------- #
# S8: range checks                                                             #
# --------------------------------------------------------------------------- #

def _parse_error(capsys, *argv) -> str:
    with pytest.raises(SystemExit) as exc:
        cli_main.build_parser().parse_args([str(a) for a in argv])
    assert exc.value.code == 2
    return capsys.readouterr().err


@pytest.mark.parametrize("value", ["0", "-1", "-5"])
def test_limit_must_be_1_or_more(capsys, value):
    err = _parse_error(capsys, "describe", "x", "--limit", value)
    assert "--limit" in err and "greater than 0" in err


def test_limit_1_is_accepted():
    args = cli_main.build_parser().parse_args(["describe", "x", "--limit", "1"])
    assert args.limit == 1


@pytest.mark.parametrize("value", ["0", "-3", "0.4", "60.5", "nan", "abc"])
def test_video_interval_range(capsys, value):
    err = _parse_error(capsys, "video", "x", "--interval", value)
    assert "--interval" in err


@pytest.mark.parametrize("value", ["0.5", "5", "60"])
def test_video_interval_accepts_the_range(value):
    args = cli_main.build_parser().parse_args(["video", "x", "--interval", value])
    assert args.interval == float(value)


@pytest.mark.parametrize("value", ["-5", "0", "0.5", "101"])
def test_scene_range(capsys, value):
    err = _parse_error(capsys, "video", "x", "--scene", value)
    assert "--scene" in err and "from 1 to 100" in err


@pytest.mark.parametrize("value", ["1", "30", "100"])
def test_scene_accepts_the_range(value):
    args = cli_main.build_parser().parse_args(["video", "x", "--scene", value])
    assert args.scene == float(value)


def test_scene_left_out_still_means_interval_mode():
    assert cli_main.build_parser().parse_args(["video", "x"]).scene == 0.0


@pytest.mark.parametrize("value", ["0", "0.1", "61"])
def test_describe_video_interval_range(capsys, value):
    err = _parse_error(capsys, "describe", "x", "--video-interval", value)
    assert "--video-interval" in err and "from 0.5 to 60" in err


@pytest.mark.parametrize("value", ["0", "-5"])
def test_chat_max_tokens_must_be_positive(capsys, value):
    err = _parse_error(capsys, "chat", "--max-tokens", value)
    assert "--max-tokens" in err


def test_watch_interval_must_be_positive(capsys):
    assert "--interval" in _parse_error(capsys, "watch", "x", "--interval", "0")


def test_ranges_match_imagedescriber():
    from idt_core.video import SCENE_THRESHOLD_RANGE, VIDEO_INTERVAL_RANGE
    from shared import number_entry

    assert number_entry.VIDEO_INTERVAL_RANGE == VIDEO_INTERVAL_RANGE == (0.5, 60.0)
    assert number_entry.SCENE_THRESHOLD_RANGE == SCENE_THRESHOLD_RANGE == (1.0, 100.0)


def test_help_documents_the_exit_codes(capsys):
    for cmd in ("describe", "download", "video", "watch"):
        with pytest.raises(SystemExit):
            cli_main.build_parser().parse_args([cmd, "--help"])
        out = capsys.readouterr().out
        assert "exit codes" in out, cmd
        assert "3  some pictures were described and some failed" in out, cmd
        assert "2  an option was wrong" in out, cmd


def test_exit_code_constants():
    assert (cli_main.EXIT_OK, cli_main.EXIT_FAILED, cli_main.EXIT_USAGE,
            cli_main.EXIT_PARTIAL) == (0, 1, 2, 3)


def test_bad_min_size_is_a_usage_error(tmp_path, idt_home, monkeypatch):
    assert run_idt(monkeypatch, "download", "https://example.com", "site",
                   "--min-size", "wide") == 2


# --------------------------------------------------------------------------- #
# Review fixes: videos in describe, guideme's limit, sibling bundles in show   #
# --------------------------------------------------------------------------- #

def _frames_cannot_be_written(monkeypatch):
    from idt_core import video as video_mod

    def _fail(dest, frame):
        raise video_mod.FrameWriteError(f"Could not write video frame {dest}: disk full")
    monkeypatch.setattr(video_mod, "write_frame", _fail)


def test_describe_videos_only_folder_whose_frames_fail_exits_1(tmp_path, idt_home,
                                                               monkeypatch, capsys):
    src = tmp_path / "Clips"
    _tiny_video(src / "clip.avi")
    _frames_cannot_be_written(monkeypatch)
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 1
    assert "clip.avi: skipped" in capsys.readouterr().err


def test_describe_failed_video_beside_good_pictures_is_partial(tmp_path, idt_home,
                                                              monkeypatch):
    src = tmp_path / "Clips"
    _tiny_video(src / "clip.avi")
    _jpeg(src / "a.jpg")
    _frames_cannot_be_written(monkeypatch)
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 3


def test_describe_with_videos_that_extract_exits_0(tmp_path, idt_home, monkeypatch):
    src = tmp_path / "Clips"
    _tiny_video(src / "clip.avi")
    assert run_idt(monkeypatch, "describe", src, *DESCRIBE) == 0


def _answers(monkeypatch, *replies):
    it = iter(replies)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(it))


@pytest.mark.parametrize("bad", ["0", "-1", "abc", "2.5"])
def test_guideme_limit_refuses_and_asks_again(monkeypatch, capsys, bad):
    from cli import guide

    _answers(monkeypatch, bad, "5")
    assert guide._ask_limit() == 5
    assert "1 or more" in capsys.readouterr().out


def test_guideme_limit_enter_means_no_limit(monkeypatch):
    from cli import guide

    _answers(monkeypatch, "")
    assert guide._ask_limit() is None


def test_guideme_extra_options_never_carry_a_bad_limit(monkeypatch):
    from cli import guide

    # limit: 0 (refused), then 3; then "No" to every yes/no question after it.
    _answers(monkeypatch, "0", "3", *(["2"] * 10))
    opts = guide._step_extra_options("dir")
    assert opts["limit"] == 3


def test_show_sibling_bundle_matches_on_the_original_path(tmp_path, idt_home,
                                                          monkeypatch, capsys):
    """An old-style sibling bundle (Photos.idtw beside Photos) holding a.jpg from
    Photos/2025 must not answer for Photos/2026/a.jpg, a different picture."""
    from idt_core.workspace import Workspace, WorkspaceDescription

    photos = tmp_path / "Photos"
    old = _jpeg(photos / "2025" / "a.jpg")
    new = _jpeg(photos / "2026" / "a.jpg", colour=(5, 5, 5))

    ws = Workspace.create(tmp_path / "Photos")          # Photos.idtw, beside Photos
    item = ws.add_image(old, subfolder="2025", copy=False)
    item.add_description(WorkspaceDescription.create(text="The 2025 picture.",
                                                     provider="ollama", model="fake"))
    ws.save_item(item)

    assert run_idt(monkeypatch, "show", new) == 1
    assert "The 2025 picture." not in capsys.readouterr().out
    assert run_idt(monkeypatch, "show", old) == 0
    assert "The 2025 picture." in capsys.readouterr().out
