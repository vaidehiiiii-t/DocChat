import os
import uuid
from pathlib import Path
from typing import BinaryIO

from werkzeug.datastructures import FileStorage

from app.errors import AppError

DEFAULT_ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
DEFAULT_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


def get_file_extension(filename: str | None) -> str:
    """Extract lowercase extension including the dot (e.g. '.pdf')."""
    if not filename:
        return ""
    ext = Path(filename).suffix.lower()
    return ext


def generate_storage_filename(extension: str) -> str:
    """Generate a safe, unique filename using UUID4."""
    if not extension.startswith("."):
        extension = f".{extension}"
    return f"{uuid.uuid4().hex}{extension.lower()}"


def get_safe_storage_path(upload_dir: str, stored_filename: str) -> str:
    """
    Resolve safe absolute path within upload_dir, guarding against path traversal.
    """
    abs_upload_dir = os.path.abspath(upload_dir)
    safe_path = os.path.abspath(os.path.join(abs_upload_dir, os.path.basename(stored_filename)))
    if not safe_path.startswith(abs_upload_dir):
        raise AppError("Invalid file path", code="VALIDATION_ERROR", status_code=400)
    return safe_path


def validate_uploaded_file(
    file: FileStorage,
    allowed_extensions: set[str] | None = None,
    max_size_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[str, str, int]:
    """
    Validate an uploaded file:
    1. Check filename presence and extension.
    2. Check file size (non-empty and <= max_size_bytes).
    3. Check magic bytes / content inspection.

    Returns (original_filename, extension, file_size_in_bytes).
    Leaves file stream pointer at position 0.
    """
    allowed_exts = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS

    if not file or not file.filename:
        raise AppError("No file provided", code="VALIDATION_ERROR", status_code=400)

    original_filename = file.filename.strip()
    ext = get_file_extension(original_filename)

    if ext not in allowed_exts:
        allowed_list = ", ".join(sorted(allowed_exts))
        raise AppError(
            f"Unsupported file format '{ext}'. Allowed formats: {allowed_list}",
            code="UNSUPPORTED_MEDIA",
            status_code=415,
        )

    # Determine size
    stream: BinaryIO = file.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)

    if size == 0:
        raise AppError("Uploaded file is empty", code="VALIDATION_ERROR", status_code=400)

    if size > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise AppError(
            f"File size exceeds maximum allowed size ({max_mb:.0f} MB)",
            code="PAYLOAD_TOO_LARGE",
            status_code=413,
        )

    # Magic bytes check
    header = stream.read(1024)
    stream.seek(0)

    if ext == ".pdf":
        if not header.startswith(b"%PDF-") and not header.startswith(b"%PDF"):
            raise AppError(
                "Invalid PDF format. File is missing standard PDF header.",
                code="VALIDATION_ERROR",
                status_code=400,
            )
    elif ext in {".txt", ".md"}:
        # Reject binary files containing null bytes
        if b"\x00" in header:
            raise AppError(
                "Invalid text format. Binary files are not supported.",
                code="VALIDATION_ERROR",
                status_code=400,
            )

    return original_filename, ext, size
