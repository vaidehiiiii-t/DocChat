import logging
import re
import time
import uuid

from flask import Flask, g, has_request_context, request

# Sensitive data patterns for redaction
PATTERNS = [
    # Bearer / JWT tokens
    (
        re.compile(
            r"Bearer\s+[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+(\.[A-Za-z0-9\-_.+/=]*)?",
            re.IGNORECASE,
        ),
        "Bearer [REDACTED]",
    ),
    # Passwords in JSON or key-value format
    (
        re.compile(r'([\'"]?password[\'"]?\s*[:=]\s*[\'"])(.*?)([\'"])', re.IGNORECASE),
        r"\1[REDACTED]\3",
    ),
    # Access tokens in JSON
    (
        re.compile(r'([\'"]?access_token[\'"]?\s*[:=]\s*[\'"])(.*?)([\'"])', re.IGNORECASE),
        r"\1[REDACTED]\3",
    ),
    # OpenAI / OpenRouter API keys
    (
        re.compile(r"(sk-[A-Za-z0-9\-_]{16,})", re.IGNORECASE),
        "sk-[REDACTED]",
    ),
    # Document raw text / excerpts dump in JSON
    (
        re.compile(
            r'([\'"]?(?:document_text|raw_content|chunk_text)[\'"]?\s*[:=]\s*[\'"])(.{30,})([\'"])',
            re.IGNORECASE,
        ),
        r"\1[REDACTED_DOCUMENT_TEXT]\3",
    ),
]


def redact_sensitive_text(text: str) -> str:
    """Sanitize string by masking credentials, tokens, and raw document dumps."""
    if not isinstance(text, str):
        return text
    sanitized = text
    for pattern, replacement in PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class RequestIdFilter(logging.Filter):
    """Logging filter that injects the current Flask request ID into records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
        else:
            record.request_id = "-"
        return True


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts passwords, tokens, and document content."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_sensitive_text(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_sensitive_text(v) if isinstance(v, str) else v for v in record.args
                )
        return True


def setup_logging(app: Flask) -> None:
    """Configure structured logging with Request ID and redaction filters on the Flask application."""
    req_filter = RequestIdFilter()
    redact_filter = SensitiveDataFilter()

    # Formatter with request ID
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [req:%(request_id)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Attach filters to app logger
    app.logger.addFilter(req_filter)
    app.logger.addFilter(redact_filter)

    for handler in app.logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(req_filter)
        handler.addFilter(redact_filter)

    @app.before_request
    def set_request_context():
        # Read incoming X-Request-ID or generate new UUID
        req_id = request.headers.get("X-Request-ID")
        if not req_id or not req_id.strip():
            req_id = uuid.uuid4().hex
        g.request_id = req_id.strip()
        g.request_start_time = time.time()

    @app.after_request
    def log_response(response):
        req_id = getattr(g, "request_id", "-")
        response.headers["X-Request-ID"] = req_id

        # Compute duration
        start = getattr(g, "request_start_time", None)
        duration_ms = round((time.time() - start) * 1000, 2) if start else 0.0

        app.logger.info(
            "%s %s %s (%sms)",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response
