import logging

from app.utils.logging import SensitiveDataFilter, redact_sensitive_text


def test_request_id_in_response_headers(client):
    # Auto-generated request ID
    res = client.get("/api/health")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    assert len(res.headers["X-Request-ID"]) > 0

    # Custom request ID preserved
    custom_id = "custom-trace-uuid-12345"
    res2 = client.get("/api/health", headers={"X-Request-ID": custom_id})
    assert res2.status_code == 200
    assert res2.headers["X-Request-ID"] == custom_id


def test_redact_sensitive_text_utility():
    # Passwords
    msg_pw = '{"email": "test@test.com", "password": "supersecretpassword"}'
    redacted_pw = redact_sensitive_text(msg_pw)
    assert "supersecretpassword" not in redacted_pw
    assert "[REDACTED]" in redacted_pw

    # Bearer tokens
    msg_bearer = "Authorization header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy.signature"
    redacted_bearer = redact_sensitive_text(msg_bearer)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted_bearer
    assert "Bearer [REDACTED]" in redacted_bearer

    # API Keys
    msg_key = "Using OpenRouter API key: sk-or-v1-abcdef1234567890abcdef1234567890"
    redacted_key = redact_sensitive_text(msg_key)
    assert "abcdef1234567890" not in redacted_key
    assert "sk-[REDACTED]" in redacted_key

    # Document text
    msg_doc = (
        '{"document_text": "This is a confidential text snippet from a private company document"}'
    )
    redacted_doc = redact_sensitive_text(msg_doc)
    assert "confidential text snippet" not in redacted_doc
    assert "[REDACTED_DOCUMENT_TEXT]" in redacted_doc


def test_sensitive_data_filter():
    filter_obj = SensitiveDataFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Login attempt for user with password: 'plain_password'",
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)
    assert "plain_password" not in record.msg
    assert "[REDACTED]" in record.msg
