import asyncio

import pytest

from app.discovery import parser
from app.discovery.safe_fetch import FetchFailure


def test_robots_disallow_prevents_page_fetch(monkeypatch):
    calls = []

    async def fake_fetch(url, **kwargs):
        calls.append(url)
        return url, "text/plain", b"User-agent: ApplyPilotJobDiscovery\nDisallow: /careers"

    monkeypatch.setattr(parser, "fetch_public", fake_fetch)
    with pytest.raises(FetchFailure, match="robots.txt"):
        asyncio.run(parser.fetch_respecting_robots("https://example.com/careers"))
    assert calls == ["https://example.com/robots.txt"]


def test_missing_robots_file_allows_public_page(monkeypatch):
    calls = []

    async def fake_fetch(url, **kwargs):
        calls.append(url)
        if url.endswith("/robots.txt"):
            raise FetchFailure("Website returned HTTP 404")
        return url, "text/html", b"<html><title>Jobs</title></html>"

    monkeypatch.setattr(parser, "fetch_public", fake_fetch)
    result = asyncio.run(parser.fetch_respecting_robots("https://example.com/careers"))
    assert result[1] == "text/html"
    assert calls == ["https://example.com/robots.txt", "https://example.com/careers"]
