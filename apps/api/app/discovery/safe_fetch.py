import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import aiohttp


class UnsafeTarget(ValueError):
    pass


class FetchFailure(RuntimeError):
    pass


class PublicOnlyResolver(aiohttp.abc.AbstractResolver):
    """Resolve hostnames only to globally routable addresses (DNS pinning per connection)."""

    async def resolve(self, host, port=0, family=socket.AF_UNSPEC):
        loop = asyncio.get_running_loop()
        try:
            records = await loop.getaddrinfo(
                host, port, family=family, type=socket.SOCK_STREAM
            )
        except socket.gaierror as exc:
            raise OSError("DNS lookup failed") from exc

        resolved = []
        seen = set()
        for record_family, _, proto, _, sockaddr in records:
            address = sockaddr[0]
            ip = ipaddress.ip_address(address.split("%", 1)[0])
            if not ip.is_global:
                raise UnsafeTarget("Host resolves to a non-public IP address")
            key = (address, record_family)
            if key in seen:
                continue
            seen.add(key)
            resolved.append({
                "hostname": host,
                "host": address,
                "port": port,
                "family": record_family,
                "proto": proto,
                "flags": socket.AI_NUMERICHOST,
            })
        if not resolved:
            raise UnsafeTarget("Host has no public IP addresses")
        return resolved

    async def close(self):
        return None


def normalize_https_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise UnsafeTarget("URL is missing or exceeds the 2048-character limit")
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (ValueError, AttributeError) as exc:
        raise UnsafeTarget("Invalid URL") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise UnsafeTarget("Only HTTPS URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeTarget("URLs containing credentials are not allowed")
    if port not in (None, 443):
        raise UnsafeTarget("Only the standard HTTPS port is allowed")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeTarget("Local hostnames are not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise UnsafeTarget("Private and reserved IP addresses are not allowed")
    netloc = f"[{host}]" if isinstance(literal, ipaddress.IPv6Address) else host
    path = parsed.path or "/"
    return urlunsplit(("https", netloc, path, parsed.query, ""))


async def fetch_public(
    url: str,
    *,
    accept: str = "text/html,application/json;q=0.9,*/*;q=0.1",
    max_bytes: int = 2_000_000,
    max_redirects: int = 4,
    redirect_check: Callable[[str], Awaitable[bool]] | None = None,
) -> tuple[str, str, bytes]:
    """Fetch a public HTTPS resource with DNS pinning, bounded redirects and body size."""
    current = normalize_https_url(url)
    timeout = aiohttp.ClientTimeout(total=18, connect=5, sock_read=10)
    connector = aiohttp.TCPConnector(
        resolver=PublicOnlyResolver(), use_dns_cache=False, limit=4, ssl=True
    )
    headers = {
        "User-Agent": "ApplyPilotJobDiscovery/0.1 (+https://github.com/Hrsht02/ApplyPilot-AI)",
        "Accept": accept,
    }
    async with aiohttp.ClientSession(
        connector=connector, timeout=timeout, trust_env=False, headers=headers,
        auto_decompress=True,
    ) as session:
        for redirect_number in range(max_redirects + 1):
            try:
                async with session.get(current, allow_redirects=False) as response:
                    if response.status in {301, 302, 303, 307, 308}:
                        if redirect_number >= max_redirects:
                            raise FetchFailure("Too many redirects")
                        location = response.headers.get("Location")
                        if not location:
                            raise FetchFailure("Redirect response had no destination")
                        next_url = normalize_https_url(urljoin(current, location))
                        if redirect_check is not None and not await redirect_check(next_url):
                            raise FetchFailure("Redirect destination does not permit automated discovery")
                        current = next_url
                        continue
                    if response.status in {401, 403, 407, 429}:
                        raise FetchFailure(f"Website declined automated access (HTTP {response.status})")
                    if response.status >= 400:
                        raise FetchFailure(f"Website returned HTTP {response.status}")
                    content_type = response.headers.get("Content-Type", "").lower()
                    if not any(kind in content_type for kind in ("text/html", "application/json", "text/plain")):
                        raise FetchFailure("Unsupported page content type")
                    length = response.headers.get("Content-Length")
                    if length and int(length) > max_bytes:
                        raise FetchFailure("Response exceeds the download limit")
                    chunks = []
                    total = 0
                    async for chunk in response.content.iter_chunked(65536):
                        total += len(chunk)
                        if total > max_bytes:
                            raise FetchFailure("Response exceeds the download limit")
                        chunks.append(chunk)
                    return str(response.url), content_type, b"".join(chunks)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
                if isinstance(exc, (UnsafeTarget, FetchFailure)):
                    raise
                raise FetchFailure("Could not safely fetch the requested website") from exc
    raise FetchFailure("Unable to fetch requested URL")
