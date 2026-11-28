"""#465: Markdown in descriptions, shown as HTML in the HTML exports.

The report, ImageDescriber's Export HTML and the gallery showed "## Setting"
and "**Foreground:**" as typed, so a screen reader read "number sign number
sign" and "star star". markdown_to_safe_html escapes first, then adds a small
set of tags.
"""
import pytest

from idt_core.markdown_html import markdown_to_safe_html as md

pytestmark = pytest.mark.unit


def test_plain_text_is_a_paragraph():
    assert md("A dog on a beach.") == "<p>A dog on a beach.</p>"


def test_single_line_breaks_are_kept():
    assert md("Line one\nLine two") == "<p>Line one<br>Line two</p>"


def test_blank_lines_start_paragraphs():
    assert md("One.\n\nTwo.") == "<p>One.</p><p>Two.</p>"


def test_html_in_a_description_stays_text():
    out = md('<script>alert("x")</script> & <b>bold</b>')
    assert "<script>" not in out and "<b>" not in out
    assert "&lt;script&gt;" in out and "&amp;" in out and "&quot;x&quot;" in out


def test_markup_inside_markdown_is_escaped_too():
    out = md("**<img src=x onerror=alert(1)>**\n- <iframe>")
    assert "<img" not in out and "<iframe>" not in out
    assert out.startswith("<p><strong>&lt;img")


@pytest.mark.parametrize("level", range(1, 7))
def test_headings_become_bold_paragraphs_not_h_tags(level):
    out = md("#" * level + " Setting")
    assert out == "<p><strong>Setting</strong></p>"
    assert "<h" not in out


def test_closing_hashes_on_a_heading_are_dropped():
    assert md("## Setting ##") == "<p><strong>Setting</strong></p>"


def test_a_hash_without_a_space_is_not_a_heading():
    assert md("#1 in the series") == "<p>#1 in the series</p>"


def test_bold_and_italic():
    assert md("**Foreground:** a *red* chair") == (
        "<p><strong>Foreground:</strong> a <em>red</em> chair</p>")
    assert md("__Background__") == "<p><strong>Background</strong></p>"


def test_underscores_in_file_names_are_left_alone():
    assert md("IMG_0001_edit.jpg") == "<p>IMG_0001_edit.jpg</p>"


def test_a_lone_star_is_not_italic():
    assert md("5 * 3 = 15") == "<p>5 * 3 = 15</p>"


def test_code_is_not_styled_inside():
    assert md("Run `**not bold**` now") == "<p>Run <code>**not bold**</code> now</p>"


def test_bulleted_list():
    assert md("- one\n* two\n+ three") == "<ul><li>one</li><li>two</li><li>three</li></ul>"


def test_numbered_list():
    assert md("1. first\n2) second") == "<ol><li>first</li><li>second</li></ol>"


def test_a_list_after_a_paragraph():
    assert md("Items:\n- a\n- b") == "<p>Items:</p><ul><li>a</li><li>b</li></ul>"


def test_switching_list_kinds_closes_the_first():
    assert md("- a\n1. b") == "<ul><li>a</li></ul><ol><li>b</li></ol>"


def test_an_indented_line_continues_a_list_item():
    assert md("- a long item\n  that wraps") == "<ul><li>a long item that wraps</li></ul>"


def test_bold_inside_a_list_item():
    assert md("- **Sky:** blue") == "<ul><li><strong>Sky:</strong> blue</li></ul>"


def test_horizontal_rules_are_dropped():
    assert md("One\n\n---\n\nTwo") == "<p>One</p><p>Two</p>"


def test_empty_text():
    assert md("") == "" and md("   \n  ") == ""


def test_no_raw_newlines_between_tags():
    """The lightbox shows its description with white-space: pre-wrap."""
    assert "\n" not in md("## A\n\nPara one\nline two\n\n- x\n- y")


def test_windows_line_endings():
    assert md("One\r\nTwo") == "<p>One<br>Two</p>"


def test_a_typical_model_answer():
    text = ("## Overview\nA kitchen in the morning.\n\n"
            "**Foreground:**\n- A granite counter\n- A *blue* mug\n\n"
            "### Lighting\nSoft daylight from the left.")
    assert md(text) == (
        "<p><strong>Overview</strong></p><p>A kitchen in the morning.</p>"
        "<p><strong>Foreground:</strong></p>"
        "<ul><li>A granite counter</li><li>A <em>blue</em> mug</li></ul>"
        "<p><strong>Lighting</strong></p><p>Soft daylight from the left.</p>")


# --------------------------------------------------------------------------- #
# The call sites                                                               #
# --------------------------------------------------------------------------- #

def test_the_gallery_renders_markdown_in_a_div():
    from idt_core.gallery_exporter import _render_descriptions_html
    out = _render_descriptions_html([{"text": "## Scene\n- a", "label": ""}], "card-desc")
    assert out == ('<div class="card-desc"><p><strong>Scene</strong></p>'
                   '<ul><li>a</li></ul></div>')


def test_the_gallery_labelled_blocks_render_markdown():
    from idt_core.gallery_exporter import _render_descriptions_html
    out = _render_descriptions_html(
        [{"text": "**A**", "label": "m1"}, {"text": "<b>x</b>", "label": "m2"}], "essay-desc")
    assert '<div class="essay-desc"><p><strong>A</strong></p></div>' in out
    assert "&lt;b&gt;x&lt;/b&gt;" in out and "<b>x</b>" not in out


def test_the_workspace_report_renders_markdown(tmp_path):
    from idt_core.exporter import export_workspace_html
    from idt_core.workspace import Workspace, WorkspaceDescription, WorkspaceItem
    src = tmp_path / "a.jpg"
    src.write_bytes(b"x")
    ws = Workspace.create(tmp_path / "w.idtw")
    item = WorkspaceItem(image="a.jpg", source_path=str(src), storage="reference")
    item.add_description(WorkspaceDescription.create(
        "## Scene\n**Sky:** blue\n<script>x</script>", provider="ollama", model="m"))
    ws.save_item(item)
    path = export_workspace_html(ws)
    html = path.read_text(encoding="utf-8")
    assert "<p><strong>Scene</strong></p>" in html
    assert "<strong>Sky:</strong> blue" in html
    assert "## Scene" not in html and "**Sky:**" not in html
    assert "<script>x</script>" not in html and "&lt;script&gt;x&lt;/script&gt;" in html
