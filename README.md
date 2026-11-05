# ApplyPilot AI

AI-assisted job application workspace. The product direction is to let candidates connect their own model provider, upload career documents, discover roles from company career pages, prepare applications, and track progress.

## Foundation status
The repository contains a Next.js web shell, FastAPI API, PostgreSQL models, Redis/Celery worker bootstrap, local Docker Compose, Render Blueprint, and GitHub Actions checks. Google sign-in intentionally fails closed until secure OAuth state/nonce validation and session issuance are implemented. The development-only user UUID header is not production authentication.

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

The local Compose database password is for development only. Never reuse it in hosted environments. Set CREDENTIAL_ENCRYPTION_KEY to a strong random secret before saving provider credentials.

## CI checks
GitHub Actions installs API dependencies and runs pytest, then installs web dependencies and runs TypeScript checks and a Next.js production build.

## Safety and production readiness
Application submission must require explicit user approval. The system must not bypass CAPTCHA, MFA, bot protection, access controls, or site restrictions, and must not invent candidate answers. Review docs/PRODUCTION_CHECKLIST.md.

This repository is not yet load-tested and makes no claim of supporting 1,000 concurrent sessions. Capacity must be established with realistic API, queue, database and browser-worker load tests.
