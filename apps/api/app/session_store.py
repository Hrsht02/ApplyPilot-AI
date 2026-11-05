import json
from typing import Any

from redis.asyncio import Redis

from app.config import settings

OAUTH_STATE_TTL = 600
SESSION_TTL = 60 * 60 * 24 * 7


def redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=3)


async def save_oauth_state(state: str, payload: dict[str, str]) -> None:
    client = redis_client()
    try:
        await client.setex(f"oauth:state:{state}", OAUTH_STATE_TTL, json.dumps(payload))
    finally:
        await client.aclose()


async def consume_oauth_state(state: str) -> dict[str, Any] | None:
    client = redis_client()
    try:
        raw = await client.getdel(f"oauth:state:{state}")
        return json.loads(raw) if raw else None
    finally:
        await client.aclose()


async def create_session(user_id: str) -> tuple[str, str]:
    import secrets

    session_id = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    client = redis_client()
    try:
        await client.setex(
            f"session:{session_id}",
            SESSION_TTL,
            json.dumps({"user_id": user_id, "csrf_token": csrf_token}),
        )
    finally:
        await client.aclose()
    return session_id, csrf_token


async def get_session(session_id: str) -> dict[str, Any] | None:
    client = redis_client()
    try:
        raw = await client.get(f"session:{session_id}")
        return json.loads(raw) if raw else None
    finally:
        await client.aclose()


async def delete_session(session_id: str) -> None:
    client = redis_client()
    try:
        await client.delete(f"session:{session_id}")
    finally:
        await client.aclose()
