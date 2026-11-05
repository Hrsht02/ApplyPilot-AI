import asyncio

import httpx
import pytest

from app.providers import registry


class FakeClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers):
        return self.response


def test_openai_key_validation_calls_model_endpoint(monkeypatch):
    response = httpx.Response(200, json={"id": "gpt-4.1-mini"})
    monkeypatch.setattr(registry.httpx, "AsyncClient", lambda **kwargs: FakeClient(response))
    asyncio.run(registry.validate_provider_key("openai", "test-key", "gpt-4.1-mini"))


def test_invalid_provider_key_is_rejected_without_leaking_provider_body(monkeypatch):
    response = httpx.Response(401, json={"error": {"message": "secret provider details"}})
    monkeypatch.setattr(registry.httpx, "AsyncClient", lambda **kwargs: FakeClient(response))
    with pytest.raises(registry.ProviderValidationError) as error:
        asyncio.run(registry.validate_provider_key("openai", "bad-key", "gpt-4.1-mini"))
    assert error.value.status_code == 401
    assert "secret provider details" not in error.value.message


def test_xai_model_must_be_listed(monkeypatch):
    response = httpx.Response(200, json={"data": [{"id": "grok-3-mini"}]})
    monkeypatch.setattr(registry.httpx, "AsyncClient", lambda **kwargs: FakeClient(response))
    asyncio.run(registry.validate_provider_key("xai", "test-key", "grok-3-mini"))
    with pytest.raises(registry.ProviderValidationError) as error:
        asyncio.run(registry.validate_provider_key("xai", "test-key", "unknown-model"))
    assert error.value.status_code == 404
