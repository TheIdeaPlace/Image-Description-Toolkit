"""ImageDescriber's usage line stays with the description, out of everything else.

ImageDescriber appends "[Token Usage: ... | Time: ...]" to each description it
stores. Kelly reads it there, so it stays in the stored text and in
ImageDescriber's own views. Everywhere the text leaves those views it comes
off: HTML/CSV/text exports (body and alt text), the gallery, idt show and
idt combine, and metadata embedded into image files. All of them use one
helper, idt_core.description_text.strip_usage_line.

The clipboard and chat paths are wx; they are in test_usage_line_outside_wx.py.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

import pytest

from idt_core.description_text import strip_usage_line

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]

BODY = "Madison, Wisconsin - A red barn [left of frame] under a grey sky."
BOTH = "\n\n[Token Usage: 4,196 total (3,000 prompt + 1,196 completion) | Time: 8.12s]"
TOKENS_ONLY = "\n\n[Token Usage: 1,200 total (1,000 prompt + 200 completion)]"
TIME_ONLY = "\n\n[Time: 3.40s]"
STORED = BODY + BOTH


def _no_usage(text: str) -> None:
    assert "[Token Usage" not in text
    assert "[Time:" not in text
    assert "4,196 total" not in text


# ------------------------------------------------------------------ #
# The helper                                                           #
# ------------------------------------------------------------------ #

class TestStripUsageLine:
    @pytest.mark.parametrize("suffix", [BOTH, TOKENS_ONLY, TIME_ONLY])
    def test_each_form_comes_off(self, suffix):
        assert strip_usage_line(BODY + suffix) == BODY

    @pytest.mark.parametrize("trailer", ["\n", "  ", "\r\n", "\n\n \t\n"])
    def test_trailing_whitespace_after_the_line(self, trailer):
        assert strip_usage_line(BODY + BOTH + trailer) == BODY

    def test_windows_line_endings(self):
        assert strip_usage_line(BODY + "\r\n\r\n[Time: 1.00s]") == BODY

    def test_location_byline_is_kept(self):
        assert strip_usage_line(STORED).startswith("Madison, Wisconsin - ")

    def test_text_without_the_line_is_unchanged(self):
        for text in (BODY, BODY + "\n", "Line one.\n\nLine two.  "):
            assert strip_usage_line(text) == text

    def test_brackets_mid_text_are_left_alone(self):
        text = "Before.\n\n[Token Usage: 5 total]\n\nThe description goes on after it."
        assert strip_usage_line(text) == text
        text = "A sign reads [Time: 9:00] on the door.\n\nMore text."
        assert strip_usage_line(text) == text

    def test_only_the_last_line_comes_off(self):
        text = "First.\n\n[Time: 1.00s]\n\n---\n\nSecond." + TIME_ONLY
        assert strip_usage_line(text) == "First.\n\n[Time: 1.00s]\n\n---\n\nSecond."

    def test_a_bracket_line_not_set_off_by_a_blank_line_stays(self):
        text = BODY + "\n[Time: 3.40s]"
        assert strip_usage_line(text) == text

    def test_other_bracketed_endings_stay(self):
        for end in ("\n\n[Note: taken at dusk]", "\n\n[Tokens: 5]", "\n\n[Time 3s]"):
            assert strip_usage_line(BODY + end) == BODY + end

    def test_a_bracket_inside_the_usage_line_ends_it(self):
        """[^\\]]: a second bracketed block after it is not part of it."""
        text = BODY + "\n\n[Time: 1.00s] [Something else]"
        assert strip_usage_line(text) == text

    @pytest.mark.parametrize("value", ["", None])
    def test_empty(self, value):
        assert strip_usage_line(value) == ""

    def test_only_whitespace_is_unchanged(self):
        assert strip_usage_line("  \n ") == "  \n "

    def test_matches_what_the_worker_writes(self):
        """The exact shapes _add_token_usage_info builds (workers_wx.py)."""
        total, prompt, completion, secs = 4196, 3000, 1196, 8.123
        parts = [f"Token Usage: {total:,} total ({prompt:,} prompt + {completion:,} completion)",
                 f"Time: {secs:.2f}s"]
        for chosen in (parts, parts[:1], parts[1:]):
            assert strip_usage_line(BODY + "\n\n[" + " | ".join(chosen) + "]") == BODY

    def test_thousands_of_blank_lines_are_quick(self):
        """A small model looping on blank lines until its token limit stores a
        description like this. The first version rescanned the run from every
        newline: 20,000 blank lines took 6 seconds a call (#489 review)."""
        import time

        for text in ("x" + "\n" * 20000, "x" + "\n \n" * 20000,
                     "x" + "\n" * 20000 + "\n\n[Time: 1.00s]"):
            start = time.perf_counter()
            strip_usage_line(text)
            assert time.perf_counter() - start < 0.2


# ------------------------------------------------------------------ #
# A workspace whose descriptions carry the line                         #
# ------------------------------------------------------------------ #

@pytest.fixture
def ws(tmp_path):
    from PIL import Image
    from idt_core.workspace import Workspace, WorkspaceDescription

    src = tmp_path / "Photos"
    src.mkdir()
    w = Workspace.create(tmp_path / "usage", name="usage", copy_originals=False)
    for n, suffix in enumerate((BOTH, TIME_ONLY)):
        p = src / f"pic{n}.jpg"
        Image.new("RGB", (16, 16), (40 * n, 90, 160)).save(p, "JPEG")
        item = w.add_image(p, copy=False)
        item.add_description(WorkspaceDescription.create(
            "Older one." + TOKENS_ONLY, provider="claude", model="claude-haiku-5-5"))
        item.add_description(WorkspaceDescription.create(
            f"{BODY} Picture {n}." + suffix, provider="claude", model="claude-haiku-5-5"))
        w.save_item(item)
    w.save_manifest()
    return w


def test_the_stored_text_keeps_the_line(ws):
    """Kelly reads it in ImageDescriber: storage is not changed."""
    from idt_core.workspace import Workspace
    texts = [d.text for i in Workspace.open(ws.path).items() for d in i.descriptions]
    assert any("[Token Usage" in t for t in texts)
    assert any(t.endswith("[Time: 3.40s]") for t in texts)


class TestWorkspaceExports:
    def test_html_body_and_alt(self, ws):
        from idt_core.exporter import export_workspace_html
        html = export_workspace_html(ws).read_text(encoding="utf-8")
        _no_usage(html)
        alts = re.findall(r'alt="([^"]*)"', html)
        assert alts and all("Madison, Wisconsin - A red barn" in a for a in alts)
        assert "Older one." in html

    def test_csv(self, ws):
        from idt_core.exporter import export_workspace_csv
        with open(export_workspace_csv(ws), encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        for row in rows:
            _no_usage(row["description"])
            assert row["description"].startswith(BODY)

    def test_txt(self, ws):
        from idt_core.exporter import export_workspace_txt
        text = export_workspace_txt(ws).read_text(encoding="utf-8")
        _no_usage(text)
        assert text.count("Madison, Wisconsin - ") == 2


class TestProjectExports:
    """The older .idt project exporters read the same kind of text."""

    @pytest.fixture
    def project(self, tmp_path):
        from PIL import Image
        from idt_core.image_item import Description, ImageItem
        from idt_core.project import Project

        src = tmp_path / "Album"
        src.mkdir()
        pic = src / "a.jpg"
        Image.new("RGB", (16, 16), "blue").save(pic, "JPEG")
        proj = Project.open(src)
        item = ImageItem(source_path=pic, sidecar_path=proj.sidecar_path(pic))
        item.add_description(Description.create(STORED, "m", "p", "n", "t"))
        item.save()
        return proj

    def test_html(self, project):
        from idt_core.exporter import export_html
        html = export_html(project).read_text(encoding="utf-8")
        _no_usage(html)
        assert 'alt="Madison, Wisconsin - A red barn' in html

    def test_csv_and_txt(self, project):
        from idt_core.exporter import export_csv, export_txt
        _no_usage(export_csv(project).read_text(encoding="utf-8"))
        _no_usage(export_txt(project).read_text(encoding="utf-8"))


class TestGallery:
    @pytest.fixture
    def items(self, tmp_path):
        sys.path.insert(0, str(_ROOT / "imagedescriber"))
        from PIL import Image
        from data_models import ImageDescription, ImageItem

        p = tmp_path / "g.jpg"
        Image.new("RGB", (16, 16), "green").save(p, "JPEG")
        item = ImageItem(str(p))
        item.add_description(ImageDescription("Oldest." + TIME_ONLY, "m", "s", provider="claude"))
        item.add_description(ImageDescription(STORED, "m", "s", provider="claude"))
        return {str(p): item}

    @pytest.mark.parametrize("selection", ["newest", "oldest", "all"])
    @pytest.mark.parametrize("style", ["card_grid", "photo_essay", "lightbox_grid", "simple_list"])
    def test_no_usage_line(self, items, tmp_path, selection, style):
        from idt_core import gallery_exporter
        out = gallery_exporter.export_gallery(items, {
            "output_dir": str(tmp_path / f"out_{style}_{selection}"), "style": style,
            "description_selection": selection})
        html = Path(out["output_file"]).read_text(encoding="utf-8")
        _no_usage(html)
        assert ("Oldest." in html) == (selection in ("oldest", "all"))


# ------------------------------------------------------------------ #
# Embedded metadata                                                    #
# ------------------------------------------------------------------ #

def _xmp_text(path: Path) -> str:
    from idt_core.embedder import _extract_xmp_from_jpeg
    return _extract_xmp_from_jpeg(path.read_bytes()).decode("utf-8")


class TestEmbedder:
    def test_jpeg_user_comment_and_xmp(self, tmp_path):
        import piexif
        import piexif.helper
        from PIL import Image
        from idt_core.embedder import embed_image_file

        src = tmp_path / "s.jpg"
        Image.new("RGB", (16, 16), "red").save(src, "JPEG")
        dest = tmp_path / "out" / "s.jpg"
        embed_image_file(src, STORED, dest)
        comment = piexif.helper.UserComment.load(
            piexif.load(str(dest))["Exif"][piexif.ExifIFD.UserComment])
        assert comment == BODY
        xmp = _xmp_text(dest)
        _no_usage(xmp)
        assert "Madison, Wisconsin - A red barn" in xmp

    def test_png(self, tmp_path):
        from PIL import Image
        from idt_core.embedder import embed_image_file

        src = tmp_path / "s.png"
        Image.new("RGB", (16, 16), "red").save(src, "PNG")
        dest = tmp_path / "out.png"
        embed_image_file(src, BODY + TIME_ONLY, dest)
        info = Image.open(dest).text
        assert info["Description"] == BODY
        _no_usage(info.get("XML:com.adobe.xmp", ""))

    def test_in_place_embed_too(self, tmp_path):
        import piexif
        import piexif.helper
        from PIL import Image
        from idt_core.embedder import embed_image_file

        src = tmp_path / "s.jpg"
        Image.new("RGB", (16, 16), "red").save(src, "JPEG")
        embed_image_file(src, STORED, src)
        comment = piexif.helper.UserComment.load(
            piexif.load(str(src))["Exif"][piexif.ExifIFD.UserComment])
        assert comment == BODY

    def test_idt_embed_on_a_workspace(self, ws):
        """cli _do_embed_workspace -> embed_image_file."""
        import piexif
        import piexif.helper
        from cli import main as cli_main

        cli_main._do_embed_workspace(ws, force=True, dry_run=False, quiet=True)
        outs = sorted((ws.path / "embedded").rglob("*.jpg"))
        assert len(outs) == 2
        for out in outs:
            comment = piexif.helper.UserComment.load(
                piexif.load(str(out))["Exif"][piexif.ExifIFD.UserComment])
            _no_usage(comment)
            assert comment.startswith(BODY)
            _no_usage(_xmp_text(out))


# ------------------------------------------------------------------ #
# idt show and idt combine                                             #
# ------------------------------------------------------------------ #

class TestCli:
    def test_show_text(self, ws, capsys):
        from cli import main as cli_main
        item = ws.items()[0]
        cli_main._print_item(item, argparse.Namespace(json_out=False))
        out = capsys.readouterr().out
        _no_usage(out)
        assert BODY in out

    def test_show_json(self, ws, capsys):
        from cli import main as cli_main
        item = ws.items()[1]
        cli_main._print_item(item, argparse.Namespace(json_out=True))
        data = json.loads(capsys.readouterr().out)
        assert data["description"] == f"{BODY} Picture 1."

    def test_combine(self, ws, tmp_path, capsys):
        from cli import main as cli_main
        out = tmp_path / "all.csv"
        cli_main.cmd_combine(argparse.Namespace(
            directory=str(ws.path.parent), output=str(out), format="csv", sort="file"))
        with open(out, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        for row in rows:
            _no_usage(row["description"])
            assert row["description"].startswith(BODY)
