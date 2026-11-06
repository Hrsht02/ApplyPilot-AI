import pytest

from app.discovery.safe_fetch import UnsafeTarget, normalize_https_url


def test_normalize_https_url_removes_fragment_and_default_port():
    assert normalize_https_url("https://Example.com:443/careers#jobs") == "https://example.com/careers"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/jobs",
        "https://127.0.0.1/admin",
        "https://10.0.0.2/",
        "https://localhost/",
        "https://user:pass@example.com/",
        "https://example.com:8443/",
    ],
)
def test_rejects_unsafe_url_shapes(url):
    with pytest.raises(UnsafeTarget):
        normalize_https_url(url)
