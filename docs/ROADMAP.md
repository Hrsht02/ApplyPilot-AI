# ApplyPilot AI implementation roadmap

## Implemented baseline
- [x] Next.js web shell and FastAPI API
- [x] PostgreSQL data models and initial Alembic migration
- [x] Redis and Celery worker bootstrap
- [x] Docker Compose with shared local PDF volume
- [x] Render Blueprint for API, worker, PostgreSQL and Redis
- [x] GitHub Actions workflow for API tests and web build/type checks

## Identity and provider credentials
- [x] Google OAuth authorization-code flow with PKCE S256
- [x] OAuth state and nonce checks; Google ID-token signature/audience/expiry validation
- [x] Opaque Redis-backed HttpOnly sessions, CSRF tokens and logout revocation
- [x] Development-only local profile bootstrap and UUID header shim
- [x] BYOK key validation for Gemini, OpenAI, Anthropic and xAI
- [x] Fernet encryption at rest; provider keys are never returned by the API

## Documents
- [x] PDF upload size/type/signature checks
- [x] Local shared-volume and S3-compatible storage adapters
- [x] Celery PDF text extraction with page/text bounds
- [x] Distinguish text PDFs from scanned PDFs (needs_ocr)
- [ ] OCR pipeline, malware scanning, document deletion and retention controls
- [ ] Chunking, embeddings, retrieval and user-scoped knowledge search

## Remaining product modules
- [x] SSRF-resistant HTTPS intake with public-IP DNS pinning, redirect checks, bounded downloads and robots.txt enforcement
- [x] Careers-page discovery with generic HTML links plus Greenhouse and Lever board APIs
- [x] Background Celery discovery task, company status tracking, job normalization, deduplication and tenant-scoped job listing API
- [ ] Resume/job matching with explainable criteria
- [ ] Application preparation and truthful answer generation
- [ ] Human review, explicit submit approval and application history workflow
- [ ] Isolated browser workers for supported portals; pause for CAPTCHA/MFA or unsupported flows

## Production validation
- [ ] Configure Google OAuth, encryption secret, private S3 bucket and Render services
- [ ] Use same-site frontend/API custom domains for browser session cookies
- [ ] Add integration tests with PostgreSQL and Redis services
- [ ] Run security review, observability setup and backup/restore drills
- [ ] Load test API, queue, storage and browser-worker capacity; no 1,000-user capacity claim until measured
