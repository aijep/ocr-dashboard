"""
Central configuration for the OCR Dashboard app.
Reads from environment variables where sensible so the app is
container/production friendly, with safe local defaults.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Storage locations
UPLOAD_DIR = Path(os.getenv("OCR_UPLOAD_DIR", BASE_DIR / "storage" / "uploads"))
OUTPUT_DIR = Path(os.getenv("OCR_OUTPUT_DIR", BASE_DIR / "storage" / "outputs"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Database
DB_PATH = Path(os.getenv("OCR_DB_PATH", BASE_DIR / "storage" / "ocr.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Upload constraints
MAX_UPLOAD_MB = int(os.getenv("OCR_MAX_UPLOAD_MB", "15"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

# OCR
TESSERACT_LANG = os.getenv("OCR_LANG", "eng")

# API metadata
API_TITLE = "OCR Dashboard API"
API_VERSION = "1.0.0"
