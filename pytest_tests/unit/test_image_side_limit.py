"""Pictures sent to Claude are fitted to its limits: under the byte limit AND
no side over 8,000 pixels.

In Kelly's 4.9.0 test run (11/18/2026) Claude refused IMG_1251.JPG: "At least
one of the image dimensions exceed max allowed size: 8000 pixels". The shrink
step only looked at bytes, so a panorama under the byte limit went as read.
ImageDescriber's Claude path and Claude chat attachments didn't fit pictures
at all.
"""
import base64
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytestmark = pytest.mark.unit


def _jpeg(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (90, 140, 200)).save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def _size(data):
    return Image.open(io.BytesIO(data)).size


def test_a_panorama_under_the_byte_limit_is_brought_to_8000():
    from idt_core.providers import claude_code

    pano = _jpeg(12000, 1500)
    assert len(pano) < claude_code.MAX_IMAGE_BYTES   # small in bytes: the old check passed it
    data, mime = claude_code.fit_image(pano, "image/jpeg")
    assert mime == "image/jpeg"
    assert _size(data) == (8000, 1000)   # no further: as much detail as Claude takes


def test_a_tall_picture_is_limited_too():
    from idt_core.providers import claude_code

    data, _ = claude_code.fit_image(_jpeg(900, 9000), "image/jpeg")
    assert max(_size(data)) == 8000


def test_a_picture_within_both_limits_is_sent_unchanged():
    from idt_core.providers import claude_code

    ok = _jpeg(8000, 2000)
    assert claude_code.fit_image(ok, "image/jpeg") == (ok, "image/jpeg")


def test_over_the_bytes_still_goes_to_the_long_edge():
    from idt_core import converter

    big = _jpeg(9000, 3000)
    data, _ = converter.fit_image(big, "image/jpeg", max_bytes=1000, long_edge=1568)
    assert max(_size(data)) <= 1568


def test_unreadable_bytes_are_left_alone():
    from idt_core import converter

    junk = b"\xff\xd8not an image"
    assert converter.fit_image(junk, "image/jpeg", 10_000, 1568) == (junk, "image/jpeg")


def test_imagedescriber_claude_sends_the_fitted_picture(tmp_path, monkeypatch):
    """ImageDescriber's ClaudeProvider read the file and sent it as it was."""
    import ai_providers

    pano = tmp_path / "IMG_1251.JPG"
    pano.write_bytes(_jpeg(12000, 1500))
    sent = {}

    class FakeMessages:
        def create(self, **params):
            sent.update(params)

            class Usage:
                input_tokens, output_tokens = 10, 5

            class Block:
                type, text = "text", "A wide view."

            class Message:
                content, usage, stop_reason = [Block()], Usage(), "end_turn"
            return Message()

    provider = ai_providers.ClaudeProvider.__new__(ai_providers.ClaudeProvider)
    provider.client = type("C", (), {"messages": FakeMessages()})()
    monkeypatch.setattr(provider, "is_available", lambda: True, raising=False)
    text = provider.describe_image(str(pano), "Describe.", "claude-haiku-5-5")
    assert "wide view" in text
    image = sent["messages"][0]["content"][0]["source"]
    assert _size(base64.b64decode(image["data"])) == (8000, 1000)


def test_claude_chat_attachments_are_fitted(tmp_path):
    from idt_core.chat.encoding import encode_attachment_claude
    from idt_core.chat.messages import Attachment

    pano = tmp_path / "pano.jpg"
    pano.write_bytes(_jpeg(12000, 1500))
    block = encode_attachment_claude(Attachment("image/jpeg", path=str(pano)))
    assert block["type"] == "image"
    assert max(_size(base64.b64decode(block["source"]["data"]))) == 8000
