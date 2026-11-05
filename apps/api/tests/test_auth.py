import base64
import hashlib

from app.auth import create_pkce_pair


def test_pkce_pair_uses_s256_challenge():
    verifier, challenge = create_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    assert 43 <= len(verifier) <= 128
    assert challenge == expected
    assert "=" not in challenge
