import asyncio
import io
import uuid
from datetime import datetime, timezone

from pypdf import PdfReader

from app.db import SessionLocal, engine
from app.models import Company, JobOpening, KnowledgeDocument
from app.storage import read_bytes
from app.discovery.parser import discover_jobs
from app.discovery.safe_fetch import FetchFailure, UnsafeTarget
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
    return "\\n\\n".join(chunks).strip()


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
        except Exception:
            document.status = "failed"
            document.extracted_text = None
            await db.commit()
            return document.status
        document.extracted_text = extracted or None
        document.status = "ready" if extracted else "needs_ocr"
        await db.commit()
        return document.status


async def process_company_discovery(company_id: str) -> str:
    async with SessionLocal() as db:
        company = await db.get(Company, uuid.UUID(company_id))
        if company is None:
            return "missing"
        company.discovery_status = "processing"
        company.discovery_error = None
        await db.commit()

        try:
            final_url, discovered = await discover_jobs(company.website_url)
        except (FetchFailure, UnsafeTarget, ValueError) as exc:
            company.discovery_status = "failed"
            company.discovery_error = str(exc)[:500]
            await db.commit()
            return company.discovery_status

        now = datetime.now(timezone.utc)
        for item in discovered:
            result = await db.execute(
                __import__("sqlalchemy").select(JobOpening).where(
                    JobOpening.company_id == company.id,
                    JobOpening.apply_url == item.apply_url,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                db.add(JobOpening(
                    company_id=company.id,
                    title=item.title[:255],
                    description=item.description[:12000],
                    apply_url=item.apply_url,
                    location=item.location[:255] if item.location else None,
                    workplace_type=item.workplace_type[:120] if item.workplace_type else None,
                    source=item.source,
                    first_seen_at=now,
                    last_seen_at=now,
                ))
            else:
                row.title = item.title[:255]
                row.description = item.description[:12000]
                row.location = item.location[:255] if item.location else None
                row.workplace_type = item.workplace_type[:120] if item.workplace_type else None
                row.source = item.source
                row.last_seen_at = now

        from urllib.parse import urlsplit
        company.normalized_domain = (urlsplit(final_url).hostname or company.normalized_domain).lower()
        company.discovery_status = "completed"
        company.discovery_error = None
        company.last_discovered_at = now
        await db.commit()
        return f"completed:{len(discovered)}"


async def process_and_dispose(document_id: str) -> str:
    try:
        return await process_document(document_id)
    finally:
        await engine.dispose()


async def process_discovery_and_dispose(company_id: str) -> str:
    try:
        return await process_company_discovery(company_id)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="applypilot.documents.extract", max_retries=3, default_retry_delay=30)
def extract_document(self, document_id: str) -> str:
    try:
        return asyncio.run(process_and_dispose(document_id))
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, name="applypilot.companies.discover", max_retries=2, default_retry_delay=60)
def discover_company(self, company_id: str) -> str:
    try:
        return asyncio.run(process_discovery_and_dispose(company_id))
    except Exception as exc:
        raise self.retry(exc=exc)
