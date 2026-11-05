from app import security


def test_provider_secret_is_encrypted_and_round_trips(monkeypatch):
    monkeypatch.setattr(security.settings, "credential_encryption_key", "test-only-key-for-unit-tests")
    encrypted = security.encrypt_secret("provider-api-key-value")
    assert encrypted != "provider-api-key-value"
    assert security.decrypt_secret(encrypted) == "provider-api-key-value"
