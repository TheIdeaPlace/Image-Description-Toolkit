"""ImageDescriber's worker keeps a phone photo upright when it shrinks it.

A JPEG over 3.75 MB is re-saved at lower quality before it goes to any
provider. The copy had no EXIF, so the orientation tag was lost and a portrait
phone photo reached every provider on its side (#487 review).

Imports workers_wx, which imports wx: runs in the test VM and CI.
"""
import io
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "imagedescriber")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

wx = pytest.importorskip("wx", reason="wxPython not installed in this environment")

pytestmark = pytest.mark.unit


def test_a_sideways_tagged_photo_comes_out_upright():
    from PIL import Image

    import workers_wx

    # Stored 400 wide by 300 tall, tagged "rotate 90": it should be seen 300 x 400.
    img = Image.new("RGB", (400, 300), "red")
    exif = img.getexif()
    exif[0x0112] = 6
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    worker = workers_wx.ProcessingWorker.__new__(workers_wx.ProcessingWorker)
    out = worker._resize_image_data(buf.getvalue(), max_size=10)   # forces the re-save
    assert Image.open(io.BytesIO(out)).size == (300, 400)
