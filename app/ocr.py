"""
OCR extraction logic.

Uses pytesseract (Tesseract OCR engine) to extract text from an image file.
Isolated in its own module so the engine can be swapped later (e.g. for a
cloud vision API) without touching the rest of the app.
"""
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import TESSERACT_LANG

# On Windows, Tesseract usually isn't on PATH, so point at the default install
# location. On Linux (e.g. the Render/Docker deployment), the Dockerfile installs
# tesseract-ocr via apt-get and it's already on PATH, so this is skipped entirely.
_WINDOWS_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.name == "nt" and os.path.exists(_WINDOWS_TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = _WINDOWS_TESSERACT_PATH

logger = logging.getLogger("ocr_dashboard.ocr")


class OCRError(Exception):
    """Raised when text extraction fails for a recoverable reason."""


@dataclass
class OCRResult:
    text: str
    char_count: int
    confidence: float  # 0-100 average word confidence


# Characters that are almost never part of genuine text but frequently show up as
# OCR misreads of icons, borders, and UI clutter (especially on screenshots).
_NOISE_CHARS = re.compile(r"[\\|{}~^`_]+")


def clean_text(text: str) -> str:
    """
    Strip common OCR noise characters and tidy up whitespace, without touching
    normal punctuation (periods, commas, currency symbols, parentheses, etc).
    """
    text = _NOISE_CHARS.sub("", text)

    cleaned_lines = []
    blank_run = 0
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line == "":
            blank_run += 1
            if blank_run <= 1:  # collapse multiple blank lines into one
                cleaned_lines.append(line)
        else:
            blank_run = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _preprocess(image: Image.Image) -> Image.Image:
    """Light preprocessing to improve OCR accuracy: grayscale + autocontrast."""
    image = ImageOps.exif_transpose(image)  # respect camera rotation metadata
    image = image.convert("L")  # grayscale
    image = ImageOps.autocontrast(image)
    return image


def extract_text_from_image(file_path: str | Path) -> OCRResult:
    """
    Run OCR on an image file and return the extracted text plus metadata.
    Raises OCRError on failure (bad/corrupt image, engine failure, etc).
    """
    path = Path(file_path)
    if not path.exists():
        raise OCRError(f"File not found: {path}")

    try:
        image = Image.open(path)
        image.load()
    except UnidentifiedImageError as exc:
        raise OCRError("File is not a valid/readable image") from exc
    except Exception as exc:  # noqa: BLE001 - surface as OCRError
        raise OCRError(f"Failed to open image: {exc}") from exc

    try:
        processed = _preprocess(image)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Preprocessing failed, using original image: %s", exc)
        processed = image

    try:
        text = pytesseract.image_to_string(processed, lang=TESSERACT_LANG)
    except pytesseract.TesseractError as exc:
        raise OCRError(f"Tesseract engine error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise OCRError(f"OCR extraction failed: {exc}") from exc

    # Compute average confidence from detailed data (best effort; don't fail the request over it)
    confidence = 0.0
    try:
        data = pytesseract.image_to_data(processed, lang=TESSERACT_LANG, output_type=pytesseract.Output.DICT)
        confidences = [int(c) for c in data.get("conf", []) if c not in ("-1", -1)]
        if confidences:
            confidence = sum(confidences) / len(confidences)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not compute OCR confidence: %s", exc)

    cleaned = clean_text(text)
    return OCRResult(text=cleaned, char_count=len(cleaned), confidence=round(confidence, 2))
