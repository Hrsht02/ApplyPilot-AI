import pytest

from app.worker import tasks


def test_pdf_extraction_rejects_documents_over_page_limit(monkeypatch):
    class FakeReader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [object()] * (tasks.MAX_PDF_PAGES + 1)

    monkeypatch.setattr(tasks, "PdfReader", FakeReader)
    with pytest.raises(ValueError, match="page limit"):
        tasks.extract_pdf_text(b"%PDF-test")


def test_pdf_extraction_caps_text_length(monkeypatch):
    class FakePage:
        def extract_text(self):
            return "x" * (tasks.MAX_EXTRACTED_CHARS + 10)

    class FakeReader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [FakePage()]

    monkeypatch.setattr(tasks, "PdfReader", FakeReader)
    text = tasks.extract_pdf_text(b"%PDF-test")
    assert len(text) == tasks.MAX_EXTRACTED_CHARS
