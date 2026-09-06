"""
OCR Dashboard - production-style FastAPI app.

Features:
- Upload an image -> OCR text extraction (Tesseract) -> saved as .txt and .pdf
- SQLite persistence of every document + its extracted text/metadata
- Dashboard UI (static HTML/JS) for browsing, previewing, downloading, deleting
- REST API, fully documented at /docs
- Same endpoints exposed as MCP tools at /mcp (via fastapi-mcp), so any
  MCP-compatible client (e.g. Claude Desktop) can call this as a tool server.
"""
import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    API_TITLE, API_VERSION, UPLOAD_DIR, OUTPUT_DIR,
    MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, ALLOWED_EXTENSIONS,
)
from app.database import Document, DocumentStatus, init_db, get_db
from app.ocr import extract_text_from_image, OCRError
from app.pdf_gen import text_to_pdf
from app.schemas import DocumentOut, DocumentDetail, StatsOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ocr_dashboard")

app = FastAPI(title=API_TITLE, version=API_VERSION, description="Extract text from photos and export as TXT/PDF.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your real frontend origin(s) in production
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent.parent


@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialized.")


def _doc_to_out(doc: Document) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        original_filename=doc.original_filename,
        status=doc.status,
        char_count=doc.char_count or 0,
        confidence=doc.confidence,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        has_txt=bool(doc.txt_path and Path(doc.txt_path).exists()),
        has_pdf=bool(doc.pdf_path and Path(doc.pdf_path).exists()),
    )


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

@app.post("/api/documents", response_model=DocumentDetail, tags=["documents"], operation_id="extract_text_from_photo")
async def upload_and_extract(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a photo, run OCR on it, and save the result as .txt and .pdf.
    Returns the extracted text and document metadata.
    """
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large. Max size is {MAX_UPLOAD_MB} MB.")
    if not contents:
        raise HTTPException(400, "Uploaded file is empty.")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = UPLOAD_DIR / stored_name
    with open(stored_path, "wb") as f:
        f.write(contents)

    doc = Document(
        original_filename=file.filename or stored_name,
        stored_filename=stored_name,
        content_type=file.content_type,
        status=DocumentStatus.PROCESSING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        result = extract_text_from_image(stored_path)
        txt_path = OUTPUT_DIR / f"{doc.id}.txt"
        pdf_path = OUTPUT_DIR / f"{doc.id}.pdf"
        txt_path.write_text(result.text, encoding="utf-8")
        text_to_pdf(result.text, pdf_path, title=doc.original_filename)

        doc.extracted_text = result.text
        doc.char_count = result.char_count
        doc.confidence = result.confidence
        doc.status = DocumentStatus.DONE
        doc.txt_path = str(txt_path)
        doc.pdf_path = str(pdf_path)
        doc.error_message = None
    except OCRError as exc:
        logger.warning("OCR failed for document %s: %s", doc.id, exc)
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(exc)
    except Exception as exc:  # noqa: BLE001 - never leak stack traces to clients
        logger.exception("Unexpected error processing document %s", doc.id)
        doc.status = DocumentStatus.FAILED
        doc.error_message = "Internal error during processing."

    db.commit()
    db.refresh(doc)
    return DocumentDetail(**_doc_to_out(doc).model_dump(), extracted_text=doc.extracted_text)


@app.get("/api/documents", response_model=list[DocumentOut], tags=["documents"], operation_id="list_documents")
def list_documents(
    db: Session = Depends(get_db),
    status_filter: Optional[DocumentStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List processed documents, most recent first."""
    q = db.query(Document)
    if status_filter:
        q = q.filter(Document.status == status_filter)
    docs = q.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
    return [_doc_to_out(d) for d in docs]


@app.get("/api/documents/{doc_id}", response_model=DocumentDetail, tags=["documents"], operation_id="get_document")
def get_document(doc_id: int, db: Session = Depends(get_db)):
    """Get full details (including extracted text) for one document."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return DocumentDetail(**_doc_to_out(doc).model_dump(), extracted_text=doc.extracted_text)


@app.get("/api/documents/{doc_id}/download", tags=["documents"], operation_id="download_document")
def download_document(doc_id: int, fmt: str = Query("txt", pattern="^(txt|pdf)$"), db: Session = Depends(get_db)):
    """Download the extracted text as a .txt or .pdf file."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    path = doc.txt_path if fmt == "txt" else doc.pdf_path
    if not path or not Path(path).exists():
        raise HTTPException(404, f"No {fmt} output available for this document")
    media_type = "text/plain" if fmt == "txt" else "application/pdf"
    filename = f"{Path(doc.original_filename).stem}.{fmt}"
    return FileResponse(path, media_type=media_type, filename=filename)


@app.delete("/api/documents/{doc_id}", tags=["documents"], operation_id="delete_document")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Delete a document and its associated files."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    for p in (UPLOAD_DIR / doc.stored_filename, doc.txt_path, doc.pdf_path):
        if p:
            Path(p).unlink(missing_ok=True)

    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}


@app.get("/api/stats", response_model=StatsOut, tags=["stats"], operation_id="get_stats")
def get_stats(db: Session = Depends(get_db)):
    """Aggregate stats for the dashboard header."""
    total = db.query(func.count(Document.id)).scalar() or 0
    done = db.query(func.count(Document.id)).filter(Document.status == DocumentStatus.DONE).scalar() or 0
    failed = db.query(func.count(Document.id)).filter(Document.status == DocumentStatus.FAILED).scalar() or 0
    chars = db.query(func.coalesce(func.sum(Document.char_count), 0)).scalar() or 0
    avg_conf = db.query(func.avg(Document.confidence)).filter(Document.status == DocumentStatus.DONE).scalar()
    return StatsOut(
        total_documents=total,
        total_done=done,
        total_failed=failed,
        total_characters_extracted=chars,
        average_confidence=round(avg_conf, 2) if avg_conf is not None else None,
    )


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Dashboard (static UI)
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", tags=["meta"], include_in_schema=False)
def dashboard():
    return FileResponse(str(BASE_DIR / "templates" / "index.html"))


# ---------------------------------------------------------------------------
# MCP mount - exposes the above endpoints as MCP tools automatically
# ---------------------------------------------------------------------------
try:
    from fastapi_mcp import FastApiMCP

    mcp = FastApiMCP(
        app,
        name="ocr-dashboard-mcp",
        description="Extract text from photos and manage extracted documents via MCP.",
    )
    mcp.mount()
    logger.info("MCP server mounted at /mcp")
except Exception as exc:  # noqa: BLE001 - app should still run without MCP if it fails
    logger.warning("Could not mount MCP server: %s", exc)
