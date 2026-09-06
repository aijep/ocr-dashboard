# Scanroom — OCR Dashboard

Extracts text from photos (OCR), saves the result as `.txt` and `.pdf`, and gives you a
dashboard to upload, browse, preview, and download everything. Built with **FastAPI**,
**SQLite**, **Tesseract OCR**, and exposes the same functionality as **MCP tools**
(via `fastapi-mcp`) so it can be used directly from Claude Desktop or any MCP client.

## Features

- **Upload → OCR → export**: drop a photo, get back extracted text as `.txt` and `.pdf`
- **SQLite persistence**: every document, its status, extracted text, and confidence score is stored
- **Dashboard UI**: served at `/` — upload, filter by status, preview extracted text, download, delete
- **REST API**: fully documented at `/docs` (Swagger) and `/redoc`
- **MCP server**: mounted at `/mcp` — the same operations (`extract_text_from_photo`,
  `list_documents`, `get_document`, `download_document`, `delete_document`, `get_stats`)
  are callable as MCP tools
- Input validation (file type / size limits), structured error handling, and logging suitable
  for production use

## Requirements

- Python 3.10+
- **Tesseract OCR engine** installed on the host:
  - Ubuntu/Debian: `sudo apt-get install -y tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: install from https://github.com/UB-Mannheim/tesseract/wiki

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run (development)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** for the dashboard, **http://localhost:8000/docs** for the API.

## Run (production)

Use multiple workers behind a reverse proxy (nginx/Caddy) that terminates TLS:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Or with gunicorn + uvicorn workers:

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Configuration (environment variables)

| Variable            | Default                  | Purpose                              |
|---------------------|---------------------------|---------------------------------------|
| `OCR_UPLOAD_DIR`    | `storage/uploads`          | Where raw uploaded images are kept   |
| `OCR_OUTPUT_DIR`    | `storage/outputs`          | Where generated `.txt`/`.pdf` go     |
| `OCR_DB_PATH`       | `storage/ocr.db`           | SQLite database file                 |
| `OCR_MAX_UPLOAD_MB` | `15`                       | Max upload size in MB                |
| `OCR_LANG`          | `eng`                      | Tesseract language code(s), e.g. `eng+fra` |

### Production notes

- **Reverse proxy + TLS**: put nginx/Caddy in front; don't expose uvicorn directly to the internet.
- **CORS**: `app/main.py` currently allows `*` — restrict `allow_origins` to your real frontend domain(s).
- **Database**: SQLite is fine for single-node / low-to-moderate concurrency. For heavier
  multi-writer workloads, swap the `DATABASE_URL` in `app/config.py` for Postgres — the
  SQLAlchemy models need no changes.
- **File storage**: for multi-instance deployments, point `OCR_UPLOAD_DIR`/`OCR_OUTPUT_DIR`
  at a shared volume or object storage mount rather than local disk.
- **Process manager**: run under systemd, Docker, or a process supervisor so it restarts on crash.
- **Backups**: back up `storage/ocr.db` and `storage/outputs/` regularly.

## Using it as an MCP server

Once running, the MCP endpoint is available at `http://localhost:8000/mcp`. Add it as a
custom connector in an MCP-compatible client (e.g. Claude Desktop's `mcpServers` config,
pointed at that URL) to call `extract_text_from_photo`, `list_documents`, `get_document`,
etc. directly from a conversation.

## API quick reference

| Method | Path                                   | Purpose                          |
|--------|-----------------------------------------|-----------------------------------|
| POST   | `/api/documents`                        | Upload image, run OCR, get result |
| GET    | `/api/documents`                        | List documents (filter by `status`) |
| GET    | `/api/documents/{id}`                   | Get one document + full text      |
| GET    | `/api/documents/{id}/download?fmt=txt`  | Download as `.txt`                |
| GET    | `/api/documents/{id}/download?fmt=pdf`  | Download as `.pdf`                |
| DELETE | `/api/documents/{id}`                   | Delete document + files           |
| GET    | `/api/stats`                            | Aggregate stats for dashboard     |
| GET    | `/health`                               | Liveness probe                    |

## Project structure

```
ocr-dashboard/
├── app/
│   ├── main.py        FastAPI app, routes, MCP mount
│   ├── config.py       Settings (paths, limits)
│   ├── database.py     SQLAlchemy models + SQLite session
│   ├── schemas.py       Pydantic response models
│   ├── ocr.py          Tesseract OCR extraction
│   └── pdf_gen.py       Text -> PDF export
├── static/              Dashboard CSS/JS
├── templates/index.html Dashboard shell
├── storage/             uploads/, outputs/, ocr.db (created at runtime)
├── requirements.txt
└── README.md
```

## Swapping the OCR engine

`app/ocr.py` is the only file that talks to the OCR engine. To use a cloud vision API
(Google Vision, AWS Textract, Azure Document Intelligence, or a Claude vision call)
instead of local Tesseract, replace `extract_text_from_image()` with a call to that
API and keep returning an `OCRResult(text, char_count, confidence)` — nothing else
in the app needs to change.
"# ocr-dashboard" 
