"""Preparing files for a provider: MIME, HEIC, limits, and partial failure.

This logic lives in the engine because three callers need it — ImageDescriber's
chat window, the standalone chat app, and `idt chat`. It previously existed only
inside `ChatWindow.on_attach_files`; copying it into the new app is exactly how
this repo ended up with three provider layers.

The behaviour worth pinning down is what happens when a *selection* is partly
bad. Someone attaching ten files, one of which is a PDF over Claude's 32 MB limit,
should get nine attachments and one explanation — not an empty queue and a
dialog. `prepare_attachments` is written for that case and
`test_one_bad_file_does_not_discard_the_others` is the assertion that keeps it.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from idt_core.chat.attachments import (  # noqa: E402
    AttachmentError,
    infer_media_type,
    prepare_attachment,
    prepare_attachments,
)
from idt_core.providers.registry import capabilities_for  # noqa: E402

CLAUDE_IMAGE_LIMIT = 5 * 1024 * 1024
CLAUDE_PDF_LIMIT = 32 * 1024 * 1024


_REAL_PICTURE = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF",
                 ".webp": "WEBP"}


@pytest.fixture
def files(tmp_path):
    """A file of ``size`` bytes. Pictures start with a real tiny image (the
    rest is padding a decoder ignores), because a picture for Claude must be
    readable to be attached (#494 review)."""
    def make(name, size=64):
        import io

        from PIL import Image

        path = tmp_path / name
        fmt = _REAL_PICTURE.get(path.suffix.lower())
        head = b""
        if fmt:
            buf = io.BytesIO()
            Image.new("RGB", (4, 4), "red").save(buf, format=fmt)
            head = buf.getvalue()
        path.write_bytes(head + b"x" * max(size - len(head), 0))
        return path
    return make


# ---------------------------------------------------------------------------
# MIME inference
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("a.jpg", "image/jpeg"),
    ("a.JPEG", "image/jpeg"),
    ("a.png", "image/png"),
    ("a.gif", "image/gif"),
    ("a.webp", "image/webp"),
    ("a.pdf", "application/pdf"),
    ("a.unknown", "application/octet-stream"),
    ("noextension", "application/octet-stream"),
])
def test_media_type_from_extension(name, expected):
    assert infer_media_type(name) == expected


# ---------------------------------------------------------------------------
# Acceptance
# ---------------------------------------------------------------------------

def test_image_is_accepted_by_every_image_provider(files):
    image = files("photo.png")
    for provider in ("ollama", "openai", "claude"):
        attachment, converted = prepare_attachment(image, provider)
        assert attachment.media_type == "image/png"
        assert attachment.path == str(image)
        assert converted is None


def test_pdf_is_accepted_by_the_document_providers(files):
    """Claude takes PDFs as document blocks, OpenAI as file content parts.
    Ollama has no PDF slot in its API at all."""
    pdf = files("doc.pdf")

    for provider in ("claude", "openai"):
        attachment, _ = prepare_attachment(pdf, provider)
        assert attachment.media_type == "application/pdf"

    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(pdf, "ollama")
    # The message must say what IS accepted, not just what failed.
    assert "accepts" in str(excinfo.value)


def test_unknown_file_type_is_rejected_with_its_name(files):
    odd = files("notes.xyz")
    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(odd, "claude")
    assert "notes.xyz" in str(excinfo.value)


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(tmp_path / "gone.png", "claude")
    assert "not found" in str(excinfo.value).lower()


def test_a_provider_taking_no_attachments_says_so(files):
    image = files("photo.png")
    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(image, "ollama cloud")
    assert "does not accept attachments" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Size limits
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", ["claude", "claude-code", "anthropic"])
def test_a_large_photo_is_fitted_for_claude_not_refused(tmp_path, provider):
    """Claude chat fits every picture before sending it, so a phone photo
    over 5 MB is scaled down. It was refused at attach time, before it
    could be fitted (#487 review, 11/19/2026)."""
    import base64
    import io

    from PIL import Image

    from idt_core.chat.encoding import encode_attachment_claude

    big = tmp_path / "phone.png"
    # Noise doesn't compress: well over 5 MB as a PNG.
    import os

    Image.frombytes("RGB", (1800, 1400), os.urandom(1800 * 1400 * 3)
                    ).save(big, format="PNG", compress_level=0)
    assert big.stat().st_size > CLAUDE_IMAGE_LIMIT
    attachment, _ = prepare_attachment(big, provider)
    block = encode_attachment_claude(attachment)
    assert len(base64.b64decode(block["source"]["data"])) <= CLAUDE_IMAGE_LIMIT
    Image.open(io.BytesIO(base64.b64decode(block["source"]["data"])))   # a real picture


@pytest.mark.parametrize("provider", ["claude", "claude-code"])
def test_a_damaged_picture_is_refused_when_attached(tmp_path, provider):
    """Not when sent: there, Pillow's error was classified as a connection
    failure and reported as "could not reach the provider" (#494 review)."""
    bad = tmp_path / "broken.jpg"
    bad.write_bytes(b"not a picture" * 600_000)   # about 7.8 MB
    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(bad, provider)
    assert "broken.jpg" in str(excinfo.value)
    assert "can't be read as a picture" in str(excinfo.value)


def test_fitting_is_a_registry_capability():
    assert capabilities_for("claude").fits_images
    assert capabilities_for("claude-code").fits_images
    assert not capabilities_for("openai").fits_images
    assert not capabilities_for("ollama").fits_images


def test_a_document_over_the_limit_is_still_refused(files):
    big = files("big.pdf", 33 * 1024 * 1024)
    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(big, "claude")
    message = str(excinfo.value)
    assert "big.pdf" in message
    assert "MB" in message  # the limit is stated in units a person reads


def test_a_file_exactly_on_the_limit_is_allowed(files):
    exact = files("exact.png", CLAUDE_IMAGE_LIMIT)
    attachment, _ = prepare_attachment(exact, "claude")
    assert attachment.media_type == "image/png"


def test_pdfs_get_the_larger_document_limit(files):
    """A 6 MB PDF is fine for Claude even though a 6 MB image is not."""
    pdf = files("big.pdf", 6 * 1024 * 1024)
    attachment, _ = prepare_attachment(pdf, "claude")
    assert attachment.media_type == "application/pdf"


def test_providers_without_documented_limits_do_not_invent_one(files):
    """None means "no published limit", so let the API report the error."""
    assert capabilities_for("ollama").size_limit_for("image/png") is None
    huge = files("huge.png", 20 * 1024 * 1024)
    attachment, _ = prepare_attachment(huge, "ollama")
    assert attachment.media_type == "image/png"


# ---------------------------------------------------------------------------
# Text files -- inlined into the prompt, so every chat provider takes them
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("notes.txt", "text/plain"),
    ("run.log", "text/plain"),
    ("readme.md", "text/markdown"),
    ("data.csv", "text/csv"),
    ("script.py", "text/x-python"),
    ("config.json", "application/json"),
    ("stack.yml", "application/yaml"),
])
def test_text_media_types_from_extension(name, expected):
    assert infer_media_type(name) == expected


def test_text_files_are_accepted_by_every_chat_provider(files):
    notes = files("notes.txt")
    for provider in ("ollama", "openai", "claude"):
        attachment, converted = prepare_attachment(notes, provider)
        assert attachment.media_type == "text/plain"
        assert attachment.is_text
        assert converted is None


def test_mlx_still_takes_images_only(files):
    """MLX is a one-image vision path; text would be silently ignored there."""
    with pytest.raises(AttachmentError):
        prepare_attachment(files("notes.txt"), "mlx")


def test_oversized_text_is_rejected_at_attach_time(files):
    """~1 MB of text is more prompt than any model here can take; say so now
    rather than as an API error mid-conversation."""
    from idt_core.providers.registry import DEFAULT_MAX_TEXT_BYTES

    big = files("huge.log", DEFAULT_MAX_TEXT_BYTES + 1)
    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(big, "ollama")
    assert "huge.log" in str(excinfo.value)


def test_rejection_message_lists_extensions_not_mime_subtypes(files):
    """".jpg, .txt" reads better than "jpeg, plain, x-python"."""
    odd = files("thing.xyz")
    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(odd, "ollama")
    message = str(excinfo.value)
    assert ".jpg" in message
    assert ".txt" in message


# ---------------------------------------------------------------------------
# HEIC conversion
# ---------------------------------------------------------------------------

def test_heic_is_converted_to_jpeg(tmp_path, monkeypatch):
    """No provider decodes HEIC, so it must be converted on the way in."""
    import idt_core.converter as converter

    source = tmp_path / "IMG_1234.heic"
    source.write_bytes(b"fake-heic")

    converted_calls = []

    def fake_convert(src, dst):
        from PIL import Image

        converted_calls.append((src, dst))
        Image.new("RGB", (4, 4), "red").save(dst, format="JPEG")   # a real JPEG

    monkeypatch.setattr(converter, "convert_heic_to_jpg", fake_convert)

    workdir = tmp_path / "work"
    attachment, converted = prepare_attachment(source, "claude", workdir)

    assert converted_calls, "conversion was never attempted"
    assert attachment.media_type == "image/jpeg"
    assert attachment.path.endswith(".jpg")
    assert converted is not None and converted.exists()
    # Caller owns cleanup, so the temp path must be reported back.
    assert converted.parent == workdir


def test_a_failed_heic_conversion_names_the_file(tmp_path, monkeypatch):
    import idt_core.converter as converter

    source = tmp_path / "broken.heic"
    source.write_bytes(b"not really heic")

    def boom(_src, _dst):
        raise ValueError("no decoder")

    monkeypatch.setattr(converter, "convert_heic_to_jpg", boom)

    with pytest.raises(AttachmentError) as excinfo:
        prepare_attachment(source, "claude", tmp_path / "work")
    assert "broken.heic" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Batch behaviour
# ---------------------------------------------------------------------------

def test_one_bad_file_does_not_discard_the_others(files):
    """Nine good photos and one oversized document should attach nine. (A
    large photo is no longer a bad file for Claude: it's fitted.)"""
    good = [files(f"ok{i}.png") for i in range(9)]
    bad = files("toobig.pdf", 33 * 1024 * 1024)

    attachments, converted, errors = prepare_attachments(
        good + [bad], "claude")

    assert len(attachments) == 9
    assert len(errors) == 1
    assert "toobig.pdf" in errors[0]
    assert converted == []


def test_batch_reports_every_problem(files):
    pdf = files("doc.pdf")
    odd = files("thing.xyz")
    image = files("fine.png")

    attachments, _converted, errors = prepare_attachments(
        [pdf, odd, image], "ollama")

    assert [a.name for a in attachments] == ["fine.png"]
    assert len(errors) == 2


def test_empty_selection_is_not_an_error():
    attachments, converted, errors = prepare_attachments([], "claude")
    assert (attachments, converted, errors) == ([], [], [])


def test_attachment_name_defaults_to_the_filename(files):
    attachment, _ = prepare_attachment(files("holiday.png"), "claude")
    assert attachment.name == "holiday.png"
