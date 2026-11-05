from app import storage


def test_local_storage_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(tmp_path))
    storage.save_bytes("user/document.pdf", b"%PDF-test", "application/pdf")
    assert storage.read_bytes("user/document.pdf") == b"%PDF-test"


def test_local_storage_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "storage_backend", "local")
    monkeypatch.setattr(storage.settings, "local_storage_path", str(tmp_path))
    try:
        storage.save_bytes("../outside.pdf", b"not allowed")
    except storage.StorageError:
        pass
    else:
        raise AssertionError("Path traversal key was accepted")
