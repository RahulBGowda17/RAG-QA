import pytest
from app.ingestion.validator import validate_upload, sanitize_filename, compute_file_hash, ValidationError
from app.ingestion.parsers import clean_text, parse_document
from app.ingestion.chunker import chunk_document_elements


def test_sanitize_filename():
    assert sanitize_filename("../../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("my report 2026.docx") == "my_report_2026.docx"
    assert sanitize_filename("..hidden.txt") == "hidden.txt"


def test_validation_empty_file():
    with pytest.raises(ValidationError):
        validate_upload("empty.txt", b"")


def test_validation_unsupported_extension():
    with pytest.raises(ValidationError):
        validate_upload("malware.exe", b"MZ\x90\x00\x03\x00")


def test_validation_valid_txt():
    content = b"This is a valid test knowledge document."
    name, ext, size = validate_upload("guide.txt", content)
    assert ext == "txt"
    assert size == len(content)


def test_compute_file_hash():
    h1 = compute_file_hash(b"Content A")
    h2 = compute_file_hash(b"Content A")
    h3 = compute_file_hash(b"Content B")
    assert h1 == h2
    assert h1 != h3


def test_clean_text():
    raw = "  Hello \xa0 world!\n\n\n\nExtra newlines   "
    cleaned = clean_text(raw)
    assert cleaned == "Hello   world!\n\nExtra newlines"


def test_chunking_structural_split():
    elements = [
        {"page_number": 1, "section": "Section 1", "text": "First sentence. Second sentence. Third sentence."}
    ]
    chunks = chunk_document_elements("doc-1", elements, chunk_size_tokens=5, chunk_overlap_tokens=2)
    assert len(chunks) >= 2
    for c in chunks:
        assert c["document_id"] == "doc-1"
        assert c["page_number"] == 1
        assert c["token_count"] > 0
