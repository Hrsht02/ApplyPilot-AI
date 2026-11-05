# ApplyPilot AI

AI-assisted job application workspace. The product direction is to let candidates connect their own model provider, upload career documents, discover roles from company career pages, prepare applications, and track progress.

## Foundation status
The repository contains a Next.js web shell, FastAPI API, PostgreSQL models and migrations, Redis/Celery workers, Google OAuth sign-in, opaque Redis-backed sessions, provider-key validation and encryption, PDF upload and text extraction, local Docker Compose, Render Blueprint, and GitHub Actions checks. The development-only user UUID header remains available only when APP_ENV=development; it is not production authentication.

## Stack
- Web: Next.js 15, React 19, TypeScript
- API: FastAPI, SQLAlchemy async, PostgreSQL
- Queue: Redis and Celery
- Deployment target: Vercel (web) + Render (API and worker)

## Local development
1. Install Docker Desktop.
2. Copy .env.example to .env.
3. Run docker compose up --build.
4. Open http://localhost:3000 and http://localhost:8000/docs.
5. API liveness: http://localhost:8000/health/live; readiness checks PostgreSQL and Redis at /health/ready.

The local Compose database password is for development only. Never reuse it in hosted environments. Set CREDENTIAL_ENCRYPTION_KEY to a strong random secret before saving provider credentials. Local PDF files are stored on a Docker volume shared by the API and worker; Render is configured for an S3-compatible private bucket, so provision the bucket and set S3_BUCKET, S3_REGION, S3_ENDPOINT_URL (if needed), AWS_ACCESS_KEY_ID, and AWS_SECRET_ACCESS_KEY.

## Google sign-in setup
1. Create an OAuth 2.0 Web application client in Google Cloud.
2. Add the exact API callback URL from GOOGLE_REDIRECT_URI to the authorized redirect URIs.
3. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI in the API environment.
4. Set APP_BASE_URL to the frontend origin. For production browser sessions, use a frontend and API on the same site (for example, app.example.com and api.example.com); default Vercel and Render hostnames are cross-site and may be blocked by browser third-party-cookie policies.

Google sign-in uses one-time Redis OAuth state, nonce verification, PKCE S256, Google ID-token signature/audience verification, and an opaque HttpOnly session cookie. State-changing authenticated API calls require a CSRF token returned by /api/auth/me. BYOK keys are validated against the selected provider/model endpoint before being encrypted and saved. PDF extraction runs asynchronously; scanned PDFs are marked needs_ocr because OCR is not yet included.

## CI checks
GitHub Actions installs API dependencies and runs pytest, then installs web dependencies and runs TypeScript checks and a Next.js production build.

## Safety and production readiness
Application submission must require explicit user approval. The system must not bypass CAPTCHA, MFA, bot protection, access controls, or site restrictions, and must not invent candidate answers. Review docs/PRODUCTION_CHECKLIST.md and docs/ROADMAP.md for the current implementation status.

This repository is not yet load-tested and makes no claim of supporting 1,000 concurrent sessions. Capacity must be established with realistic API, queue, database and browser-worker load tests.
