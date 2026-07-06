import textwrap
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from config import THUMBNAIL_DIR

THUMB_WIDTH = 320
THUMB_HEIGHT = 200
JPEG_QUALITY = 68

_IMAGE_TYPES = {".jpg", ".jpeg", ".png"}


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(text: str, width: int = 42) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return ["No preview available"]
    return textwrap.wrap(cleaned, width=width)[:8]


def _save_thumbnail(image: Image.Image, name: str) -> str:
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    if image.mode != "RGB":
        image = image.convert("RGB")
    out = THUMBNAIL_DIR / f"{name}.jpg"
    image.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return f"/static/thumbnails/{name}.jpg"


def _text_preview_thumbnail(file_type: str, extracted_text: str) -> str:
    image = Image.new("RGB", (THUMB_WIDTH, THUMB_HEIGHT), (236, 244, 250))
    draw = ImageDraw.Draw(image)
    title_font = _load_font(15)
    body_font = _load_font(11)

    label = file_type.upper().lstrip(".") or "FILE"
    draw.rectangle((0, 0, THUMB_WIDTH, 34), fill=(2, 132, 199))
    draw.text((12, 9), label, fill=(255, 255, 255), font=title_font)

    y = 44
    for line in _wrap_text(extracted_text):
        draw.text((12, y), line, fill=(30, 58, 79), font=body_font)
        y += 16
        if y > THUMB_HEIGHT - 12:
            break

    return _save_thumbnail(image, uuid.uuid4().hex)


def _image_thumbnail(source_path: Path) -> str:
    with Image.open(source_path) as image:
        copy = image.copy()
        copy.thumbnail((THUMB_WIDTH, THUMB_HEIGHT), Image.Resampling.LANCZOS)
        return _save_thumbnail(copy, uuid.uuid4().hex)


def create_thumbnail(source_path: Path, file_type: str, extracted_text: str) -> str | None:
    ext = file_type.lower()
    try:
        if ext in _IMAGE_TYPES:
            return _image_thumbnail(source_path)
        return _text_preview_thumbnail(ext, extracted_text)
    except Exception:
        return None


def remove_thumbnail(thumbnail_path: str | None) -> None:
    if not thumbnail_path or not thumbnail_path.startswith("/static/thumbnails/"):
        return
    file_path = THUMBNAIL_DIR / Path(thumbnail_path).name
    file_path.unlink(missing_ok=True)
