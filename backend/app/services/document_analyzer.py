"""Document and Multimodal File Analyzer for Cognexa AI.

Processes uploaded PDFs, images, source code files, and tabular documents,
extracting textual context and metadata for downstream reasoning.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, Optional
import uuid
from PIL import Image
import PyPDF2

logger = logging.getLogger(__name__)

UPLOADS_DIR = Path("uploads").resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text content from uploaded PDF document."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        extracted_pages = []
        for idx, page in enumerate(reader.pages[:30]):  # up to first 30 pages
            text = page.extract_text() or ""
            if text.strip():
                # Detect vertical / fragmented single-word per line formatting from certain PDF generators
                raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
                if raw_lines and len(raw_lines) > 8 and (sum(len(l.split()) for l in raw_lines) / len(raw_lines)) < 2.5:
                    # Single words per line -> merge them smoothly
                    normalized = " ".join(raw_lines)
                    # Restore question numbering boundaries on new lines (e.g., " 1. ", " 2. ")
                    normalized = re.sub(r"\s*(\d+\.\s+)", r"\n\1", normalized).strip()
                    extracted_pages.append(f"--- Page {idx + 1} ---\n{normalized}")
                else:
                    extracted_pages.append(f"--- Page {idx + 1} ---\n{text.strip()}")
        return "\n\n".join(extracted_pages)
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def extract_metadata_from_image(file_bytes: bytes) -> Dict[str, Any]:
    """Extract resolution and basic attributes from image."""
    try:
        img = Image.open(io.BytesIO(file_bytes))
        width, height = img.size
        fmt = img.format or "JPEG"
        mode = img.mode
        return {
            "width": width,
            "height": height,
            "format": fmt,
            "mode": mode,
            "summary": f"Image dimensions: {width}x{height} pixels ({fmt}, {mode} color space).",
        }
    except Exception as exc:
        logger.warning("Image inspection failed: %s", exc)
        return {"summary": "Uploaded image file."}


def analyze_uploaded_file(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Analyze and persist uploaded document or image."""
    file_id = uuid.uuid4().hex[:10]
    safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", filename)
    saved_filename = f"{file_id}_{safe_name}"
    saved_path = UPLOADS_DIR / saved_filename

    with open(saved_path, "wb") as f:
        f.write(file_bytes)

    size_kb = len(file_bytes) // 1024
    ext = os.path.splitext(filename)[1].lower()

    extracted_text = ""
    file_type = "document"

    if ext in [".pdf"]:
        file_type = "pdf"
        extracted_text = extract_text_from_pdf(file_bytes)
        summary = f"PDF Document '{filename}' ({size_kb} KB, {len(extracted_text.splitlines())} lines extracted)."
    elif ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]:
        file_type = "image"
        img_meta = extract_metadata_from_image(file_bytes)
        summary = f"Image '{filename}' ({size_kb} KB) — {img_meta['summary']}"
        extracted_text = f"[Attached Screenshot/Image: {filename} | {img_meta['summary']}]"
    elif ext in [".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".sql", ".sol"]:
        file_type = "code" if ext not in [".txt", ".md", ".csv"] else "text"
        try:
            extracted_text = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            extracted_text = ""
        summary = f"Source/Data file '{filename}' ({size_kb} KB, {len(extracted_text.splitlines())} lines)."
    else:
        summary = f"Uploaded binary/data file '{filename}' ({size_kb} KB)."

    chunks_indexed = 0
    if extracted_text and file_type in ["pdf", "text", "code", "document"]:
        try:
            from app.services.document_rag import document_rag
            chunks_indexed = document_rag.index_document(file_id, filename, extracted_text)
            summary += f" [RAG Vector Index: {chunks_indexed} semantic chunks ready for retrieval]."
        except Exception as rag_err:
            logger.warning("RAG indexing skipped for %s: %s", filename, rag_err)

    return {
        "file_id": file_id,
        "filename": filename,
        "saved_path": str(saved_path),
        "file_type": file_type,
        "size_kb": size_kb,
        "summary": summary,
        "extracted_text": extracted_text[:8000],  # cap for prompt context preview
        "url": f"http://localhost:8001/uploads/{saved_filename}",
        "chunks_indexed": chunks_indexed,
        "rag_ready": chunks_indexed > 0,
    }
