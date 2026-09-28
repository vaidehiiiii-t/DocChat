import os
from pathlib import Path

import pymupdf as fitz

from app.errors import AppError


class NoTextError(AppError):
    def __init__(
        self,
        message: str = "PDF contains no extractable text. Scanned documents and image-only PDFs are not supported.",
    ):
        super().__init__(message=message, code="NO_TEXT", status_code=422)


class ParsingService:
    @staticmethod
    def parse_pdf(file_path: str) -> list[tuple[int, str]]:
        """
        Extract text per page from a PDF file using PyMuPDF.
        Returns a list of (page_number, text) tuples (1-indexed).
        Raises NoTextError if total extracted text across all pages is < 50 characters.
        """
        pages: list[tuple[int, str]] = []
        doc = None
        try:
            doc = fitz.open(file_path)
            for page_index in range(len(doc)):
                page = doc[page_index]
                text = page.get_text("text") or ""
                pages.append((page_index + 1, text))
        finally:
            if doc is not None:
                doc.close()

        total_text_len = sum(len(text.strip()) for _, text in pages)
        if total_text_len < 50:
            raise NoTextError(
                "PDF contains no extractable text. Scanned documents and image-only PDFs are not supported."
            )

        return pages

    @staticmethod
    def parse_text(file_path: str) -> list[tuple[int, str]]:
        """
        Read TXT or MD file with UTF-8 encoding, falling back to latin-1.
        Returns [(1, text)].
        Raises NoTextError if text has fewer than 10 non-whitespace characters.
        """
        content = ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()

        if len(content.strip()) < 10:
            raise NoTextError("File contains no readable text.")

        return [(1, content)]

    @classmethod
    def parse(cls, file_path: str, original_filename: str | None = None) -> list[tuple[int, str]]:
        """
        Parse file based on extension.
        Returns list of (page_number, text) tuples.
        """
        if not os.path.exists(file_path):
            raise AppError(f"File not found: {file_path}", code="NOT_FOUND", status_code=404)

        filename = original_filename or file_path
        ext = Path(filename).suffix.lower()

        if ext == ".pdf":
            return cls.parse_pdf(file_path)
        elif ext in {".txt", ".md"}:
            return cls.parse_text(file_path)
        else:
            raise AppError(
                f"Unsupported file format '{ext}' for parsing",
                code="VALIDATION_ERROR",
                status_code=400,
            )
