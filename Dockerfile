# Production image for the OCR Dashboard.
# Includes Tesseract OCR (a system dependency pip can't install on its own).
FROM python:3.12-slim

# Install Tesseract OCR engine + minimal build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make sure storage dirs exist even before the persistent disk is mounted over them
RUN mkdir -p storage/uploads storage/outputs

EXPOSE 8000

# Render sets $PORT; default to 8000 for local docker runs
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
