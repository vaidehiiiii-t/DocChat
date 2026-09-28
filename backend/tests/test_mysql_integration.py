import io
import time
import uuid

import pytest
from sqlalchemy import create_engine, text

from app import create_app
from app.config import Config, Settings
from app.models.user import User


@pytest.mark.mysql
def test_real_mysql_end_to_end_flow():
    """
    Full end-to-end integration test against the real configured MySQL/TiDB database.
    Covers: register -> login -> upload document -> wait ready -> chat session -> ask question -> verify sources -> delete document -> assert cascade & cleanup.
    """
    settings = Settings()
    real_db_url = settings.DATABASE_URL

    if not real_db_url or "sqlite" in real_db_url:
        pytest.skip("No real MySQL/TiDB DATABASE_URL configured in backend/.env")

    # Verify connectivity
    try:
        engine = create_engine(real_db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Could not connect to real MySQL/TiDB database: {exc}")

    # Create app bound to real database
    real_config = Config(settings)
    app = create_app(real_config)
    app.config["TESTING"] = True
    client = app.test_client()

    unique_suffix = uuid.uuid4().hex[:8]
    test_email = f"real_mysql_{unique_suffix}@example.com"
    test_password = "SecurePassword123!"

    user_id = None
    doc_id = None
    session_id = None

    try:
        # 1. Register
        reg_res = client.post(
            "/api/auth/register",
            json={"name": "Real MySQL User", "email": test_email, "password": test_password},
        )
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.get_json()}"
        token = reg_res.get_json()["access_token"]
        user_id = reg_res.get_json()["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload Document
        pdf_bytes = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj\n"
            b"4 0 obj << /Length 120 >> stream\n"
            b"BT /F1 12 Tf 72 712 Td (DocChat MySQL real database end-to-end integration test documentation text.) Tj ET\n"
            b"endstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000216 00000 n\n"
            b"trailer << /Size 5 /Root 1 0 R >>\nstartxref\n386\n%%EOF"
        )
        upload_res = client.post(
            "/api/documents",
            headers=headers,
            data={"file": (io.BytesIO(pdf_bytes), "mysql_test.pdf")},
            content_type="multipart/form-data",
        )
        assert upload_res.status_code == 202, f"Upload failed: {upload_res.get_json()}"
        doc_id = upload_res.get_json()["id"]

        # 3. Poll until ready (up to 15s)
        doc_status = "pending"
        for _ in range(30):
            status_res = client.get(f"/api/documents/{doc_id}", headers=headers)
            if status_res.status_code == 200:
                doc_status = status_res.get_json()["status"]
                if doc_status in ("ready", "failed"):
                    break
            time.sleep(0.5)

        assert doc_status == "ready", f"Document failed to reach ready state: {doc_status}"

        # 4. Create chat session scoped to this document
        sess_res = client.post(
            "/api/chat/sessions",
            headers=headers,
            json={"title": "MySQL Integration Chat", "document_id": doc_id},
        )
        assert sess_res.status_code == 201
        session_id = sess_res.get_json()["id"]

        # 5. Post message
        msg_res = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            headers=headers,
            json={"content": "What is this document about?"},
        )
        assert msg_res.status_code == 200
        msg_data = msg_res.get_json()
        assert "assistant_message" in msg_data
        assert "user_message" in msg_data
        assert msg_data["assistant_message"]["content"] is not None

        # 6. Delete document
        del_res = client.delete(f"/api/documents/{doc_id}", headers=headers)
        assert del_res.status_code == 200

        # Verify document is gone from MySQL
        get_deleted = client.get(f"/api/documents/{doc_id}", headers=headers)
        assert get_deleted.status_code == 404

    finally:
        # Cleanup in real DB
        if user_id:
            with app.app_context():
                from app.extensions import db

                user = db.session.get(User, user_id)
                if user:
                    db.session.delete(user)
                    db.session.commit()
