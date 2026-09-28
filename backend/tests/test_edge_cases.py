import io
import os

import pymupdf as fitz
import pytest

from app.errors import AppError
from app.services.chunking import ChunkingService
from app.services.parsing import NoTextError, ParsingService
from app.utils.files import validate_uploaded_file


def test_one_word_txt_rejected_with_clear_error(tmp_path):
    txt_path = os.path.join(tmp_path, "tiny.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Hello")

    with pytest.raises(NoTextError) as exc_info:
        ParsingService.parse(txt_path, "tiny.txt")
    assert "no readable text" in str(exc_info.value).lower()


def test_non_english_multilingual_parsing_and_chunking(tmp_path):
    txt_path = os.path.join(tmp_path, "multilingual.txt")
    content = (
        "Bonjour le monde! Ceci est un document en français avec accents: café, résumé, forêt, naïf.\n\n"
        "这是一个中文测试文档，用于验证自然语言分块与向量检索系统在非英文语境下的稳定性和可靠性。\n\n"
        "هذا نص تجريبي باللغة العربية لاختبار قدرة النظام على معالجة وتجزئة النصوص متعددة اللغات بدقة.\n\n"
        "日本のテストドキュメント：自然言語処理システムが正常に動作することを確認します。"
    )
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)

    pages = ParsingService.parse(txt_path, "multilingual.txt")
    assert len(pages) == 1
    page_num, text = pages[0]
    assert "café" in text
    assert "这是一个中文测试文档" in text
    assert "هذا نص تجريبي" in text
    assert "日本のテストドキュメント" in text

    # Chunking multilingual text
    chunker = ChunkingService(chunk_size=150, chunk_overlap=30)
    chunks = chunker.chunk_pages(pages)
    assert len(chunks) > 1
    # Verify indices contiguous from 0
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.char_count == len(c.text)


def test_500_page_pdf_parsing_and_chunking(tmp_path):
    pdf_path = os.path.join(tmp_path, "500_pages.pdf")
    doc = fitz.open()
    for page_i in range(1, 501):
        p = doc.new_page()
        p.insert_text(
            fitz.Point(50, 72),
            f"DocChat stress testing document. Page {page_i} of 500 pages total. "
            f"Verifying scalable indexing, chunk index contiguity, and page metadata preservation.",
        )
    doc.save(pdf_path)
    doc.close()

    # Parse 500 pages
    pages = ParsingService.parse(pdf_path, "500_pages.pdf")
    assert len(pages) == 500
    assert pages[0][0] == 1
    assert pages[499][0] == 500

    # Chunk 500 pages
    chunker = ChunkingService(chunk_size=800, chunk_overlap=150)
    chunks = chunker.chunk_pages(pages)
    assert len(chunks) == 500
    # Every chunk should preserve its respective page number and have contiguous index
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.page_number == idx + 1


def test_oversize_file_rejected_with_413():
    from unittest.mock import MagicMock

    from werkzeug.datastructures import FileStorage

    # 25 MB file (exceeds 20 MB limit)
    fake_stream = io.BytesIO(b"%PDF-1.4\n" + b"x" * 50)
    fake_file = FileStorage(stream=fake_stream, filename="large.pdf")
    fake_stream.tell = MagicMock(return_value=25 * 1024 * 1024)

    with pytest.raises(AppError) as exc_info:
        validate_uploaded_file(
            fake_file,
            allowed_extensions={".pdf"},
            max_size_bytes=20 * 1024 * 1024,
        )
    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "PAYLOAD_TOO_LARGE"
