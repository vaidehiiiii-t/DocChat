import os

import pymupdf as fitz
import pytest

from app.errors import AppError
from app.services.parsing import NoTextError, ParsingService


def create_test_pdf(file_path: str, pages_text: list[str]) -> None:
    """Helper to generate real PDF files with PyMuPDF for testing."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        # insert text at point (50, 72)
        page.insert_text(fitz.Point(50, 72), text)
    doc.save(file_path)
    doc.close()


def test_parse_valid_pdf_multi_page(tmp_path):
    pdf_path = os.path.join(tmp_path, "sample.pdf")
    page1_text = "DocChat test document page 1. This page contains detailed system documentation."
    page2_text = "Known phrase on page 2: PyMuPDF parsing works seamlessly with multi-page PDFs."
    create_test_pdf(pdf_path, [page1_text, page2_text])

    pages = ParsingService.parse(pdf_path, "sample.pdf")
    assert len(pages) == 2
    assert pages[0][0] == 1
    assert "DocChat test document page 1" in pages[0][1]
    assert pages[1][0] == 2
    assert "Known phrase on page 2" in pages[1][1]


def test_parse_scanned_or_empty_pdf(tmp_path):
    pdf_path = os.path.join(tmp_path, "empty.pdf")
    # Only 10 characters across all pages (< 50 chars threshold)
    create_test_pdf(pdf_path, ["Hi there!"])

    with pytest.raises(NoTextError) as exc_info:
        ParsingService.parse(pdf_path, "empty.pdf")

    assert "PDF contains no extractable text" in str(exc_info.value.message)
    assert exc_info.value.code == "NO_TEXT"
    assert exc_info.value.status_code == 422


def test_parse_valid_txt_and_md(tmp_path):
    txt_path = os.path.join(tmp_path, "notes.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("This is a simple text file with more than enough readable characters.")

    pages = ParsingService.parse(txt_path, "notes.txt")
    assert len(pages) == 1
    assert pages[0][0] == 1
    assert "simple text file" in pages[0][1]

    md_path = os.path.join(tmp_path, "readme.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Header 1\n\nThis is a markdown document with descriptive content.")

    pages_md = ParsingService.parse(md_path, "readme.md")
    assert len(pages_md) == 1
    assert pages_md[0][0] == 1
    assert "# Header 1" in pages_md[0][1]


def test_parse_latin1_text_fallback(tmp_path):
    latin1_path = os.path.join(tmp_path, "latin1.txt")
    text_content = "Le café de la plage propose d'excellents gâteaux à déguster."
    with open(latin1_path, "wb") as f:
        f.write(text_content.encode("latin-1"))

    pages = ParsingService.parse(latin1_path, "latin1.txt")
    assert len(pages) == 1
    assert "café" in pages[0][1]
    assert "gâteaux" in pages[0][1]


def test_parse_empty_text_raises_notexterror(tmp_path):
    empty_txt = os.path.join(tmp_path, "empty.txt")
    with open(empty_txt, "w", encoding="utf-8") as f:
        f.write("   \n\t  ")

    with pytest.raises(NoTextError):
        ParsingService.parse(empty_txt, "empty.txt")


def test_parse_non_existent_file():
    with pytest.raises(AppError) as exc_info:
        ParsingService.parse("non_existent_file.pdf", "sample.pdf")
    assert exc_info.value.status_code == 404


def test_parse_unsupported_extension(tmp_path):
    csv_file = os.path.join(tmp_path, "data.csv")
    with open(csv_file, "w") as f:
        f.write("a,b,c\n1,2,3")
    with pytest.raises(AppError) as exc_info:
        ParsingService.parse(csv_file, "data.csv")
    assert exc_info.value.status_code == 400
