# ApplyPilot AI

AI-assisted job application workspace with Google sign-in, bring-your-own-model-key (Gemini/OpenAI/Claude/Grok), PDF knowledge base, company careers URL intake, job discovery, application preparation, human review, and application history.

## Current implementation status
This repository is being initialized. The planned architecture is a Next.js web app, FastAPI API, PostgreSQL, Redis/Celery workers, provider-key encryption, PDF ingestion, company/job discovery, and isolated browser workers.

## Local setup
Copy .env.example to .env, configure secrets, then run docker compose up --build. Web: http://localhost:3000; API docs: http://localhost:8000/docs.

Google OAuth must be configured in Google Cloud. Do not enable sign-in until OAuth state/nonce validation and secure session-cookie issuance are implemented.

## BYOK
Support planned for Gemini, OpenAI, Anthropic Claude, and xAI Grok. Provider keys must be encrypted at rest, never returned to clients, and decrypted only in isolated background workers.

## Application safety
Require explicit user approval before each final submission. Do not bypass CAPTCHA, MFA, bot protection, access controls, or website restrictions. Do not fabricate answers. Unsupported portals should pause for manual completion.

## 1,000 concurrent users
This repository is not load-tested and makes no capacity guarantee. Scaling requires stateless API replicas, managed PostgreSQL with PgBouncer, Redis HA, object storage, isolated autoscaled worker pools, per-domain browser concurrency controls, observability, and realistic load testing. See docs/PRODUCTION_CHECKLIST.md.
