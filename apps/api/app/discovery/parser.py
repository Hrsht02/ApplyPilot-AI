import json
import re
from urllib.robotparser import RobotFileParser
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from app.discovery.safe_fetch import FetchFailure, fetch_public, normalize_https_url


CAREER_WORDS = ("career", "careers", "jobs", "job-opportunities", "join-us", "work-with-us")
JOB_WORDS = ("job", "jobs", "opening", "opportunity", "position", "career", "apply")
GREENHOUSE_HOSTS = {"boards.greenhouse.io", "job-boards.greenhouse.io"}
LEVER_HOSTS = {"jobs.lever.co"}
KNOWN_ATS_SUFFIXES = (
    "boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co",
    "jobs.ashbyhq.com", "jobs.smartrecruiters.com", "myworkdayjobs.com",
    "workdayjobs.com", "jobs.workable.com", "jobs.personio.com",
    "jobs.jobvite.com", "careers.icims.com",
)
CRAWLER_AGENT = "ApplyPilotJobDiscovery"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.text_parts = []
        self.links = []
        self.meta = {}
        self._in_title = False
        self._skip_depth = 0
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (attrs.get("name") or attrs.get("property") or "").lower()
            if key in {"description", "og:description", "og:title"}:
                self.meta[key] = attrs.get("content", "")
        if tag == "a" and attrs.get("href"):
            self._anchor = {"href": attrs["href"], "text": []}

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False
        if tag == "a" and self._anchor:
            self.links.append((self._anchor["href"], clean_text(" ".join(self._anchor["text"]))))
            self._anchor = None

    def handle_data(self, data):
        if self._skip_depth:
            return
        value = clean_text(data)
        if not value:
            return
        self.text_parts.append(value)
        if self._in_title:
            self.title_parts.append(value)
        if self._anchor:
            self._anchor["text"].append(value)

    @property
    def title(self):
        return clean_text(" ".join(self.title_parts)) or clean_text(self.meta.get("og:title", ""))

    @property
    def description(self):
        return clean_text(self.meta.get("description") or self.meta.get("og:description", ""))

    @property
    def text(self):
        return clean_text(" ".join(self.text_parts))[:12000]


async def _robots_allows(url: str) -> bool:
    normalized = normalize_https_url(url)
    parsed = urlsplit(normalized)
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    robots_url = origin + "/robots.txt"
    try:
        _, _, robots_body = await fetch_public(
            robots_url, accept="text/plain,*/*;q=0.1", max_bytes=200_000, max_redirects=2
        )
    except FetchFailure as exc:
        if "HTTP 404" in str(exc):
            robots_body = b""
        else:
            return False
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(robots_body.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(CRAWLER_AGENT, normalized)


async def fetch_respecting_robots(url: str, *, accept: str = "text/html,application/json;q=0.9,*/*;q=0.1", max_bytes: int = 2_000_000):
    normalized = normalize_https_url(url)
    if not await _robots_allows(normalized):
        raise FetchFailure("The website's robots.txt blocks automated discovery or its policy could not be verified")
    return await fetch_public(
        normalized, accept=accept, max_bytes=max_bytes, redirect_check=_robots_allows
    )

@dataclass
class JobRecord:
    title: str
    description: str
    apply_url: str
    location: str | None = None
    workplace_type: str | None = None
    source: str = "website"


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _same_company_domain(candidate_host: str, company_host: str) -> bool:
    candidate = candidate_host.removeprefix("www.")
    company = company_host.removeprefix("www.")
    return (
        candidate == company
        or candidate.endswith("." + company)
        or company.endswith("." + candidate)
    )


def _known_ats_host(host: str) -> bool:
    return any(host == suffix or host.endswith("." + suffix) for suffix in KNOWN_ATS_SUFFIXES)


def _career_score(url: str, label: str) -> int:
    value = f"{url} {label}".lower()
    return sum(2 if word in value else 0 for word in CAREER_WORDS)


def _job_score(url: str, label: str) -> int:
    value = f"{url} {label}".lower()
    score = sum(1 for word in JOB_WORDS if word in value)
    if label and len(label) > 8:
        score += 1
    return score


def _slug_from_url(url: str, allowed_hosts: set[str]) -> str | None:
    parsed = urlsplit(url)
    if (parsed.hostname or "").lower() not in allowed_hosts:
        return None
    pieces = [part for part in parsed.path.split("/") if part]
    return pieces[0] if pieces else None


def _extract_greenhouse(payload: dict, base: str) -> list[JobRecord]:
    jobs = []
    for item in payload.get("jobs", [])[:200]:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("title", ""))
        apply_url = item.get("absolute_url") or ""
        if title and apply_url:
            try:
                safe_apply_url = normalize_https_url(apply_url)
            except ValueError:
                continue
            description_parser = PageParser()
            description_parser.feed(str(item.get("content", "")))
            location_data = item.get("location") or {}
            location_name = location_data.get("name", "") if isinstance(location_data, dict) else str(location_data)
            jobs.append(JobRecord(
                title=title,
                description=description_parser.text[:12000],
                apply_url=safe_apply_url,
                location=clean_text(location_name) or None,
                source="greenhouse",
            ))
    return jobs


def _extract_lever(payload: list, base: str) -> list[JobRecord]:
    jobs = []
    for item in payload[:200]:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("text", ""))
        apply_url = item.get("hostedUrl") or item.get("applyUrl") or ""
        categories = item.get("categories") or {}
        if not isinstance(categories, dict):
            categories = {}
        description = clean_text(item.get("descriptionPlain") or item.get("description") or "")
        if title and apply_url:
            try:
                safe_apply_url = normalize_https_url(apply_url)
            except ValueError:
                continue
            jobs.append(JobRecord(
                title=title, description=description[:12000],
                apply_url=safe_apply_url,
                location=clean_text(categories.get("location", "")) or None,
                workplace_type=clean_text(categories.get("commitment", "")) or None,
                source="lever",
            ))
    return jobs


async def discover_jobs(start_url: str) -> tuple[str, list[JobRecord]]:
    start = normalize_https_url(start_url)
    final_url, content_type, body = await fetch_respecting_robots(start)
    initial_host = _host(start)
    final_host = _host(final_url)
    if not _same_company_domain(final_host, initial_host) and not _known_ats_host(final_host):
        raise FetchFailure("Company URL redirected to an unrelated, unsupported domain")
    if "json" in content_type:
        raise FetchFailure("The supplied URL returned JSON, not a company page")
    parser = PageParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    start_host = _host(final_url)

    career_candidates = []
    for href, label in parser.links:
        try:
            candidate = normalize_https_url(urljoin(final_url, href))
        except ValueError:
            continue
        host = _host(candidate)
        if _same_company_domain(host, start_host) or _known_ats_host(host):
            score = 10 if _known_ats_host(host) else _career_score(candidate, label)
            if score:
                career_candidates.append((score, candidate))
    career_candidates.sort(key=lambda item: item[0], reverse=True)

    pages = [(final_url, parser)]
    for _, candidate in career_candidates[:4]:
        if candidate == final_url:
            continue
        try:
            page_url, page_type, page_body = await fetch_respecting_robots(candidate, max_bytes=1_000_000)
            if "html" not in page_type:
                continue
            page_parser = PageParser()
            page_parser.feed(page_body.decode("utf-8", errors="replace"))
            pages.append((page_url, page_parser))
        except (FetchFailure, ValueError):
            continue

    jobs: dict[str, JobRecord] = {}
    for page_url, page in pages:
        host = _host(page_url)
        if host in GREENHOUSE_HOSTS:
            slug = _slug_from_url(page_url, GREENHOUSE_HOSTS)
            if slug:
                api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
                try:
                    _, _, payload = await fetch_respecting_robots(api_url, accept="application/json", max_bytes=2_000_000)
                    for job in _extract_greenhouse(json.loads(payload), api_url):
                        jobs[job.apply_url] = job
                except (FetchFailure, ValueError, TypeError):
                    pass
        elif host in LEVER_HOSTS:
            slug = _slug_from_url(page_url, LEVER_HOSTS)
            if slug:
                api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
                try:
                    _, _, payload = await fetch_respecting_robots(api_url, accept="application/json", max_bytes=2_000_000)
                    for job in _extract_lever(json.loads(payload), api_url):
                        jobs[job.apply_url] = job
                except (FetchFailure, ValueError, TypeError):
                    pass

        for href, label in page.links:
            if _job_score(href, label) < 2:
                continue
            try:
                target = normalize_https_url(urljoin(page_url, href))
            except ValueError:
                continue
            target_host = _host(target)
            if not _same_company_domain(target_host, start_host) and not _known_ats_host(target_host):
                continue
            if target in jobs:
                continue
            title = label[:255] or "Open role"
            jobs[target] = JobRecord(
                title=title,
                description=page.description or page.text[:4000],
                apply_url=target,
                source="website",
            )
            if len(jobs) >= 200:
                break
        if len(jobs) >= 200:
            break

    return final_url, list(jobs.values())[:200]
