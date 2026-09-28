import io

import pytest
from werkzeug.datastructures import FileStorage

from app.errors import AppError
from app.utils.files import (
    generate_storage_filename,
    get_file_extension,
    get_safe_storage_path,
    validate_uploaded_file,
)


def create_file_storage(filename: str, content: bytes) -> FileStorage:
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
    )


def test_get_file_extension():
    assert get_file_extension("document.pdf") == ".pdf"
    assert get_file_extension("notes.TXT") == ".txt"
    assert get_file_extension("readme.MD") == ".md"
    assert get_file_extension("no_extension") == ""
    assert get_file_extension(None) == ""


def test_generate_storage_filename():
    f1 = generate_storage_filename(".pdf")
    f2 = generate_storage_filename("pdf")
    assert f1.endswith(".pdf")
    assert f2.endswith(".pdf")
    assert f1 != f2
    assert len(f1) > 30


def test_get_safe_storage_path(tmp_path):
    upload_dir = str(tmp_path)
    safe_path = get_safe_storage_path(upload_dir, "test.pdf")
    assert safe_path.startswith(upload_dir)

    # Path traversal should be sanitized or rejected
    traversal_path = get_safe_storage_path(upload_dir, "../../secret.txt")
    assert traversal_path.startswith(upload_dir)
    assert "secret.txt" in traversal_path


def test_validate_valid_pdf():
    valid_pdf_content = b"%PDF-1.4 sample pdf content for testing purposes"
    file = create_file_storage("doc.pdf", valid_pdf_content)

    name, ext, size = validate_uploaded_file(file)
    assert name == "doc.pdf"
    assert ext == ".pdf"
    assert size == len(valid_pdf_content)


def test_validate_valid_txt_and_md():
    txt_file = create_file_storage("notes.txt", b"Hello world text document")
    name, ext, size = validate_uploaded_file(txt_file)
    assert name == "notes.txt"
    assert ext == ".txt"

    md_file = create_file_storage("README.md", b"# Markdown Header\nSome body text.")
    name, ext, size = validate_uploaded_file(md_file)
    assert name == "README.md"
    assert ext == ".md"


def test_validate_unsupported_extensions():
    for bad_name in ["script.exe", "image.png", "archive.zip", "test.docx"]:
        file = create_file_storage(bad_name, b"some content")
        with pytest.raises(AppError) as exc_info:
            validate_uploaded_file(file)
        assert exc_info.value.status_code == 415
        assert exc_info.value.code == "UNSUPPORTED_MEDIA"
        assert "Unsupported file format" in exc_info.value.message


def test_validate_empty_file():
    empty_file = create_file_storage("empty.pdf", b"")
    with pytest.raises(AppError) as exc_info:
        validate_uploaded_file(empty_file)
    assert exc_info.value.status_code == 400
    assert "empty" in exc_info.value.message.lower()


def test_validate_oversized_file():
    small_limit = 100  # 100 bytes
    large_content = b"%PDF-1.4 " + (b"X" * 200)
    file = create_file_storage("large.pdf", large_content)
    with pytest.raises(AppError) as exc_info:
        validate_uploaded_file(file, max_size_bytes=small_limit)
    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "PAYLOAD_TOO_LARGE"
    assert "exceeds" in exc_info.value.message.lower()


def test_validate_fake_pdf():
    # .pdf extension but missing %PDF magic header
    fake_pdf = create_file_storage("fake.pdf", b"This is plain text pretending to be PDF")
    with pytest.raises(AppError) as exc_info:
        validate_uploaded_file(fake_pdf)
    assert exc_info.value.status_code == 400
    assert "Invalid PDF format" in exc_info.value.message


def test_validate_fake_text_with_null_bytes():
    # .txt extension but binary data with null bytes
    binary_txt = create_file_storage("binary.txt", b"Hello\x00\x01\x02world")
    with pytest.raises(AppError) as exc_info:
        validate_uploaded_file(binary_txt)
    assert exc_info.value.status_code == 400
    assert "Binary files are not supported" in exc_info.value.message
