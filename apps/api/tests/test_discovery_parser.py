import asyncio
import json

from app.discovery import parser


def test_greenhouse_payload_is_normalized():
    jobs = parser._extract_greenhouse(
        {
            "jobs": [
                {
                    "title": "Backend Engineer",
                    "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                    "content": "<p>Build APIs</p>",
                    "location": {"name": "Remote"},
                }
            ]
        },
        "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
    )
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].location == "Remote"
    assert jobs[0].source == "greenhouse"


def test_lever_payload_is_normalized():
    jobs = parser._extract_lever(
        [
            {
                "text": "ML Engineer",
                "hostedUrl": "https://jobs.lever.co/acme/abc",
                "descriptionPlain": "Build models",
                "categories": {"location": "Remote", "commitment": "Full-time"},
            }
        ],
        "https://api.lever.co/v0/postings/acme?mode=json",
    )
    assert jobs[0].title == "ML Engineer"
    assert jobs[0].location == "Remote"
    assert jobs[0].workplace_type == "Full-time"


def test_generic_careers_page_extracts_job_links(monkeypatch):
    html = b"""
    <html><head><title>Acme Careers</title>
    <meta name="description" content="Join our engineering team"></head>
    <body><a href="/jobs/123">Senior Python Engineer</a></body></html>
    """

    async def fake_fetch(url, **kwargs):
        return url, "text/html; charset=utf-8", html

    monkeypatch.setattr(parser, "fetch_respecting_robots", fake_fetch)
    final_url, jobs = asyncio.run(parser.discover_jobs("https://acme.example/careers"))
    assert final_url == "https://acme.example/careers"
    assert len(jobs) == 1
    assert jobs[0].title == "Senior Python Engineer"
    assert jobs[0].apply_url == "https://acme.example/jobs/123"
