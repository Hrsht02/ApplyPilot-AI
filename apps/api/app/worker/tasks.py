import asyncio
import io
import uuid

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.db import SessionLocal, engine
from app.models import KnowledgeDocument
from app.storage import read_bytes
from app.worker.celery_app import celery_app

MAX_PDF_PAGES = 250
MAX_EXTRACTED_CHARS = 5_000_000


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content), strict=False)
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("PDF exceeds the page limit")
    chunks = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            remaining = MAX_EXTRACTED_CHARS - total
            chunks.append(text[:remaining])
            total += min(len(text), remaining)
        if total >= MAX_EXTRACTED_CHARS:
            break
    return "\n\n".join(chunks).strip()


async def process_document(document_id: str) -> str:
    async with SessionLocal() as db:
        document = await db.get(KnowledgeDocument, uuid.UUID(document_id))
        if document is None:
            return "missing"
        document.status = "processing"
        await db.commit()

        content = await asyncio.to_thread(read_bytes, document.storage_key)
        try:
            extracted = await asyncio.to_thread(extract_pdf_text, content)
        except (PdfReadError, ValueError):
            document.status = "failed"
            document.extracted_text = None
            await db.commit()
            return document.status

        document.extracted_text = extracted or None
        document.status = "ready" if extracted else "needs_ocr"
        await db.commit()
        return document.status


async def process_and_dispose(document_id: str) -> str:
    try:
        return await process_document(document_id)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="applypilot.documents.extract", max_retries=3, default_retry_delay=30)
def extract_document(self, document_id: str) -> str:
    try:
        return asyncio.run(process_and_dispose(document_id))
    except Exception as exc:
        raise self.retry(exc=exc)
