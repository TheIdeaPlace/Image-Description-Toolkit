"""
Image loading and format conversion.
All HEIC conversion is done in memory — nothing is written to the source directory.
When a persistent JPEG copy is needed (for .idt/ storage), callers use save_heic_copy().
"""
from __future__ import annotations

import io
from pathlib import Path

MIME_TYPES: dict[str, str] = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
    ".gif":  "image/gif",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff",
    ".bmp":  "image/jpeg",   # converted on the fly
    ".heic": "image/jpeg",   # converted on the fly
    ".heif": "image/jpeg",   # converted on the fly
}

# Formats that need to be converted before sending to an API
_NEEDS_CONVERSION = frozenset({".heic", ".heif", ".bmp", ".tiff", ".tif"})


def load_for_api(path: Path) -> tuple[bytes, str]:
    """
    Load an image as bytes ready for an AI provider API call.
    HEIC/HEIF and BMP are converted to JPEG in memory.
    TIFF is also converted because several cloud providers reject it.
    Returns (image_bytes, mime_type).
    """
    suffix = path.suffix.lower()
    if suffix in (".heic", ".heif"):
        return _heic_to_jpeg_bytes(path)
    if suffix in (".bmp", ".tiff", ".tif"):
        return _pil_to_jpeg_bytes(path)
    with open(path, "rb") as f:
        data = f.read()
    return data, MIME_TYPES.get(suffix, "image/jpeg")


def save_heic_copy(source: Path, dest_dir: Path) -> Path:
    """
    Convert a HEIC/HEIF file to JPEG and save it in dest_dir.
    dest_dir should be a path inside the .idt/ mirror — never the source directory.
    Returns the path to the saved JPEG.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    jpeg_path = dest_dir / source.with_suffix(".jpg").name
    img_bytes, _ = _heic_to_jpeg_bytes(source)
    jpeg_path.write_bytes(img_bytes)
    return jpeg_path


def _heic_to_jpeg_bytes(path: Path) -> tuple[bytes, str]:
    try:
        import pillow_heif
        from PIL import Image
    except ImportError:
        raise ImportError(
            "pillow-heif is required for HEIC/HEIF support: pip install pillow-heif"
        )
    pillow_heif.register_heif_opener()
    img = Image.open(path).convert("RGB")
    return _pil_image_to_jpeg_bytes(img)


def _pil_to_jpeg_bytes(path: Path) -> tuple[bytes, str]:
    from PIL import Image
    img = Image.open(path).convert("RGB")
    return _pil_image_to_jpeg_bytes(img)


#: The most pixels fit_image will decode. Pillow's own guard against
#: "decompression bombs" stops at about 179 MP, which a stitched phone or drone
#: panorama can pass; IDT reads only pictures the user chose, so it allows
#: more, but not without limit (#487 review).
_MAX_DECODE_PIXELS = 600_000_000


def _open_large(image_bytes: bytes):
    """Image.open with the pixel cap above instead of Pillow's."""
    from PIL import Image

    saved = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = _MAX_DECODE_PIXELS
    try:
        return Image.open(io.BytesIO(image_bytes))
    finally:
        Image.MAX_IMAGE_PIXELS = saved


def _side_of(image_bytes: bytes) -> int:
    """The longer side in pixels, read from the header only; 0 if it can't be read."""
    try:
        with _open_large(image_bytes) as img:
            return max(img.size)
    except Exception:
        return 0


def _flatten(img):
    """RGB for JPEG. Transparent areas go white, not black: a transparent PNG
    diagram or logo strip otherwise reaches the model as dark on black."""
    from PIL import Image

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        white = Image.new("RGB", img.size, (255, 255, 255))
        white.paste(img, mask=img.getchannel("A"))
        return white
    return img if img.mode == "RGB" else img.convert("RGB")


def fit_image(image_bytes: bytes, mime_type: str, max_bytes: int,
              long_edge: int, max_side: int | None = None,
              accepted_types: frozenset | None = None) -> tuple[bytes, str]:
    """``(bytes, mime)`` no bigger than ``max_bytes``, with no side over ``max_side`` pixels
    (when given) and of a type in ``accepted_types`` (when given): unchanged when it already
    is. Over the bytes, it's scaled to ``long_edge`` on its longer side; otherwise only down to
    ``max_side``, so a panorama keeps as much detail as the provider allows. Anything changed is
    saved as a JPEG.

    For providers that take a picture's bytes inline and have a size limit. A 24 or 48 MP phone
    JPEG, or a large PNG scan, is over most limits and would otherwise fail on every attempt.
    """
    over_bytes = len(image_bytes) > max_bytes
    wrong_type = bool(accepted_types) and mime_type not in accepted_types
    side = _side_of(image_bytes) if (max_side or wrong_type) else 0
    too_big = bool(max_side) and side > max_side
    if not (over_bytes or too_big or wrong_type):
        return image_bytes, mime_type
    if over_bytes:
        long_edge = min(long_edge, max_side) if max_side else long_edge
    elif too_big:
        long_edge = max_side
    else:  # only the type: keep the size, up to the long edge it would get anyway
        long_edge = max(side, 1) if side else long_edge
    from PIL import Image

    from PIL import ImageOps

    img = _open_large(image_bytes)
    # A JPEG can decode at 1/2, 1/4 or 1/8 size directly: much faster for a huge
    # picture, and the full-size image is never held in memory.
    if img.format == "JPEG":
        img.draft("RGB", (long_edge, long_edge))
    # The copy is saved without EXIF, so a phone photo is turned upright first, or it would
    # reach the model on its side.
    img = _flatten(ImageOps.exif_transpose(img))
    # Almost every photo fits at long_edge. One that doesn't (fine detail or noise compresses
    # badly) is made smaller again until it does, rather than sent over the limit.
    while True:
        img.thumbnail((long_edge, long_edge), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        if out.tell() <= max_bytes or long_edge <= 256:
            return out.getvalue(), "image/jpeg"
        long_edge = int(long_edge * 0.75)


def _pil_image_to_jpeg_bytes(img) -> tuple[bytes, str]:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92, optimize=True)
    return buf.getvalue(), "image/jpeg"


def convert_heic_to_jpg(
    input_path: Path,
    output_path: Path | None = None,
    quality: int = 95,
    keep_metadata: bool = True,
    max_file_size: int = 4_718_592,  # 4.5 MB — safe under Claude's 5 MB limit
) -> bool:
    """Convert a HEIC/HEIF file to JPEG with progressive quality reduction if needed.

    Returns True on success, False on failure.
    """
    try:
        import pillow_heif
        from PIL import Image
    except ImportError:
        raise ImportError("pillow-heif is required: pip install pillow-heif")

    pillow_heif.register_heif_opener()
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path.with_suffix(".jpg")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(input_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            exif_data = img.info.get("exif", b"") if keep_metadata else b""

            current_quality = quality
            for _ in range(10):
                save_kwargs: dict = {"format": "JPEG", "quality": current_quality, "optimize": True}
                if exif_data:
                    save_kwargs["exif"] = exif_data
                img.save(output_path, **save_kwargs)
                if output_path.stat().st_size <= max_file_size:
                    break
                if current_quality > 75:
                    current_quality -= 5
                else:
                    # Resize to 75 %
                    img = img.resize(
                        (int(img.width * 0.75), int(img.height * 0.75)),
                        Image.LANCZOS,
                    )
        return True
    except Exception:
        return False
