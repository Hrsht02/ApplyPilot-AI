# Production readiness checklist

This is an evolving engineering checklist, not a certification that the application is production-ready.

## Identity and tenant isolation
- [ ] Implement Google OAuth with state and nonce validation, issuer/audience/signature/expiry checks, secure HttpOnly session cookies, CSRF protection, logout and revocation.
- [ ] Remove the development-only X-User-Id identity shim before public deployment.
- [ ] Add tenant-scoped authorization to every user-owned record and automated cross-tenant isolation tests.

## Data and secrets
- [ ] Add Alembic migrations, backup/restore drills, retention and deletion workflows.
- [ ] Replace local uploads with private object storage, signed URLs, malware scanning and upload limits.
- [ ] Encrypt BYOK credentials with managed KMS/envelope encryption; never log plaintext keys.
- [ ] Add request limits, quotas and per-user/provider rate limits.

## Agent and browser safety
- [ ] Protect company URL intake against SSRF, DNS rebinding, unsafe redirects and private IP access before fetching any user-supplied URL.
- [ ] Run browser automation in isolated ephemeral workers with resource limits and per-domain concurrency caps.
- [ ] Require user review and explicit approval before each final submission. Pause for CAPTCHA, MFA, bot protection or unsupported flows.

## Operations and scale
- [ ] Add structured logs, trace IDs, metrics, error reporting, alerting and audit events.
- [ ] Configure Render secrets/private networking and Vercel environment variables.
- [ ] Load test API, queue, database pool and browser workers separately. Do not infer 1,000 simultaneous browser sessions from 1,000 concurrent web users.

## Render deployment
Use render.yaml as a Blueprint starting point. Review service plans and region, provision suitable production database/Redis plans, set APP_BASE_URL to the deployed Vercel origin, and set all secrets in the Render dashboard. Never commit secrets.
