import asyncio
import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import User
from app.session_store import (
    SESSION_TTL, consume_oauth_state, create_session, delete_session,
    get_session, save_oauth_state,
)

router = APIRouter(prefix="/auth", tags=["auth"])
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def create_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


@router.get("/google")
async def google_login():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth is not configured")
    if settings.app_env == "production" and not settings.google_redirect_uri.startswith("https://"):
        raise HTTPException(503, "Google redirect URI must use HTTPS in production")
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = create_pkce_pair()
    await save_oauth_state(state, {"state": state, "nonce": nonce, "verifier": verifier})
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if error:
        raise HTTPException(400, "Google sign-in was cancelled or rejected")
    if not code or not state:
        raise HTTPException(400, "Missing OAuth callback parameters")
    oauth_state = await consume_oauth_state(state)
    if not oauth_state or not secrets.compare_digest(oauth_state["state"], state):
        raise HTTPException(400, "OAuth state is invalid or expired")
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "redirect_uri": settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                    "code_verifier": oauth_state["verifier"],
                },
            )
        token_response.raise_for_status()
        encoded_id_token = token_response.json().get("id_token")
        if not encoded_id_token:
            raise ValueError("Missing ID token")
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token
        claims = await asyncio.to_thread(
            id_token.verify_oauth2_token, encoded_id_token, GoogleRequest(),
            settings.google_client_id,
        )
    except Exception as exc:
        raise HTTPException(401, "Google identity verification failed") from exc

    nonce = claims.get("nonce", "")
    if not nonce or not secrets.compare_digest(nonce, oauth_state["nonce"]):
        raise HTTPException(401, "Google nonce validation failed")
    if claims.get("email_verified") is not True:
        raise HTTPException(403, "A verified Google email address is required")
    google_sub, email = claims.get("sub"), claims.get("email")
    if not google_sub or not email:
        raise HTTPException(401, "Google profile is incomplete")

    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()
    if user is None:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(409, "This email is already linked to another sign-in identity")
        user = User(
            google_sub=google_sub, email=email,
            name=claims.get("name") or email.split("@", 1)[0],
            picture=claims.get("picture"),
        )
        db.add(user)
    else:
        user.email = email
        user.name = claims.get("name") or user.name
        user.picture = claims.get("picture")
    await db.commit()
    await db.refresh(user)

    session_id, _ = await create_session(str(user.id))
    response = RedirectResponse(f"{settings.app_base_url.rstrip('/')}/?signed_in=1", status_code=303)
    response.set_cookie(
        key="applypilot_session", value=session_id, max_age=SESSION_TTL,
        httponly=True, secure=settings.app_env == "production", samesite="lax", path="/",
    )
    return response


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    session_id = request.cookies.get("applypilot_session")
    session = await get_session(session_id) if session_id else None
    if not session:
        return {"authenticated": False}
    user = await db.get(User, session.get("user_id"))
    if not user:
        await delete_session(session_id)
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {"id": str(user.id), "email": user.email, "name": user.name, "picture": user.picture},
        "csrf_token": session["csrf_token"],
    }


@router.post("/logout")
async def logout(
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    session_id = request.cookies.get("applypilot_session")
    session = await get_session(session_id) if session_id else None
    if session and (
        not x_csrf_token or not secrets.compare_digest(x_csrf_token, session["csrf_token"])
    ):
        raise HTTPException(403, "CSRF token is missing or invalid")
    if session_id:
        await delete_session(session_id)
    response = JSONResponse({"logged_out": True})
    response.delete_cookie(
        "applypilot_session", httponly=True, secure=settings.app_env == "production",
        samesite="lax", path="/",
    )
    return response
