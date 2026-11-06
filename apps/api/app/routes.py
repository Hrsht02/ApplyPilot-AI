import asyncio
import hashlib
import secrets
import uuid
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import Application, Company, JobOpening, KnowledgeDocument, ProviderCredential, User
from app.providers.registry import ProviderValidationError, validate_provider_key
from app.security import encrypt_secret
from app.storage import StorageError, save_bytes
from app.worker.tasks import discover_company, extract_document
from app.discovery.safe_fetch import UnsafeTarget, normalize_https_url
from app.session_store import get_session

router = APIRouter(prefix="/v1")


async def current_user(
    request: Request,
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    db: AsyncSession = Depends(get_db),
):
    session_id = request.cookies.get("applypilot_session")
    session = await get_session(session_id) if session_id else None
    if session:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            expected = session.get("csrf_token", "")
            if not x_csrf_token or not secrets.compare_digest(x_csrf_token, expected):
                raise HTTPException(403, "CSRF token is missing or invalid")
        try:
            user_id = uuid.UUID(session["user_id"])
        except (ValueError, KeyError, TypeError):
            raise HTTPException(401, "Invalid session")
        user = await db.get(User, user_id)
        if user:
            return user
        raise HTTPException(401, "Session user not found")

    # Local-only shim. Production requests must use a server-issued session cookie.
    if settings.app_env == "development" and x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(401, "Invalid development user ID")
        user = await db.get(User, user_id)
        if user:
            return user
    raise HTTPException(401, "Authenticated session required")


class ProviderIn(BaseModel):
    provider: Literal["openai", "gemini", "anthropic", "xai"]
    api_key: str = Field(min_length=10, max_length=500)
    model: str = Field(min_length=1, max_length=120)


class CompanyIn(BaseModel):
    website_url: str


@router.put("/settings/provider-key")
async def save_key(p: ProviderIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    try:
        await validate_provider_key(p.provider, p.api_key, p.model)
    except ProviderValidationError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    q = select(ProviderCredential).where(
        ProviderCredential.user_id == u.id, ProviderCredential.provider == p.provider
    )
    row = (await db.execute(q)).scalar_one_or_none()
    if row:
        row.encrypted_api_key = encrypt_secret(p.api_key)
        row.model = p.model
    else:
        db.add(ProviderCredential(
            user_id=u.id, provider=p.provider,
            encrypted_api_key=encrypt_secret(p.api_key), model=p.model,
        ))
    await db.commit()
    return {"provider": p.provider, "model": p.model, "configured": True}


@router.get("/settings/provider-key")
async def keys(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(ProviderCredential).where(ProviderCredential.user_id == u.id)
    )).scalars()
    return [{"provider": row.provider, "model": row.model, "configured": True} for row in rows]


@router.post("/documents", status_code=202)
async def upload(
    file: UploadFile = File(...),
    u: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(415, "PDF only")
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, "PDF too large")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(415, "The uploaded file is not a valid PDF")
    key = f"{u.id}/{hashlib.sha256(data).hexdigest()}.pdf"
    try:
        await asyncio.to_thread(save_bytes, key, data, "application/pdf")
    except StorageError as exc:
        raise HTTPException(503, "Document storage is unavailable") from exc
    document = KnowledgeDocument(user_id=u.id, filename=file.filename[:255], storage_key=key)
    db.add(document)
    await db.commit()
    await db.refresh(document)
    try:
        extract_document.delay(str(document.id))
    except Exception as exc:
        document.status = "queue_error"
        await db.commit()
        raise HTTPException(503, "PDF stored, but the processing queue is unavailable") from exc
    return {"id": str(document.id), "filename": document.filename, "status": "queued"}


@router.get("/documents")
async def list_documents(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.user_id == u.id)
        .order_by(KnowledgeDocument.created_at.desc())
        .limit(100)
    )).scalars()
    return [
        {"id": str(row.id), "filename": row.filename, "status": row.status, "created_at": row.created_at.isoformat()}
        for row in rows
    ]

@router.post("/companies", status_code=202)
async def add_company(
    p: CompanyIn,
    u: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        safe_url = normalize_https_url(p.website_url)
    except UnsafeTarget as exc:
        raise HTTPException(400, str(exc)) from exc
    domain = (urlparse(safe_url).hostname or "").lower().removeprefix("www.")
    query = select(Company).where(
        Company.user_id == u.id,
        Company.normalized_domain == domain,
    )
    company = (await db.execute(query)).scalar_one_or_none()
    if company is None:
        company = Company(
            user_id=u.id,
            website_url=safe_url,
            normalized_domain=domain,
            discovery_status="queued",
        )
        db.add(company)
    else:
        company.website_url = safe_url
        company.discovery_status = "queued"
        company.discovery_error = None
    await db.commit()
    await db.refresh(company)
    try:
        discover_company.delay(str(company.id))
    except Exception as exc:
        company.discovery_status = "queue_error"
        company.discovery_error = "The discovery queue is unavailable"
        await db.commit()
        raise HTTPException(503, "Company saved, but the discovery queue is unavailable") from exc
    return {
        "id": str(company.id),
        "website_url": company.website_url,
        "discovery_status": company.discovery_status,
    }


@router.get("/companies")
async def list_companies(
    u: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(Company)
        .where(Company.user_id == u.id)
        .order_by(Company.id.desc())
        .limit(100)
    )).scalars()
    return [
        {
            "id": str(row.id),
            "website_url": row.website_url,
            "normalized_domain": row.normalized_domain,
            "discovery_status": row.discovery_status,
            "discovery_error": row.discovery_error,
            "last_discovered_at": row.last_discovered_at.isoformat() if row.last_discovered_at else None,
        }
        for row in rows
    ]


@router.get("/jobs")
async def list_jobs(
    company_id: uuid.UUID | None = None,
    u: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(JobOpening, Company)
        .join(Company, Company.id == JobOpening.company_id)
        .where(Company.user_id == u.id)
        .order_by(JobOpening.last_seen_at.desc())
        .limit(200)
    )
    if company_id:
        query = query.where(Company.id == company_id)
    rows = (await db.execute(query)).all()
    return [
        {
            "id": str(job.id),
            "company_id": str(company.id),
            "company": company.normalized_domain,
            "title": job.title,
            "description": job.description,
            "apply_url": job.apply_url,
            "location": job.location,
            "workplace_type": job.workplace_type,
            "source": job.source,
            "match_score": job.match_score,
            "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
            "last_seen_at": job.last_seen_at.isoformat() if job.last_seen_at else None,
        }
        for job, company in rows
    ]

@router.get("/applications")
async def history(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(Application).where(Application.user_id == u.id)
        .order_by(Application.id.desc()).limit(100)
    )).scalars()
    return [
        {"id": str(row.id), "job_id": str(row.job_id), "status": row.status,
         "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None}
        for row in rows
    ]
