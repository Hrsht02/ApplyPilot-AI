from fastapi import APIRouter,HTTPException
from app.config import settings
router=APIRouter(prefix="/auth",tags=["auth"])
@router.get("/google")
async def google_login():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503,"Google OAuth is not configured")
    # Fail closed until OAuth state/nonce persistence, callback validation and
    # signed HttpOnly session issuance are implemented for this deployment.
    raise HTTPException(501,"OAuth callback/session configuration is required before sign-in can be enabled")
