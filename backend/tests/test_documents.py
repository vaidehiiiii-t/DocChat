import io
import os
import tempfile
import time

from app.extensions import db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.services.vector_store import VectorStore
from app.utils.files import generate_storage_filename


def get_auth_token(client, email="testuser@example.com", password="Password123!"):
    # Register and login to obtain JWT token
    client.post(
        "/api/auth/register",
        json={"name": "Test User", "email": email, "password": password},
    )
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    return res.get_json()["access_token"]


def test_upload_document_auth_and_validation(client):
    # 1. No auth -> 401
    res = client.post("/api/documents")
    assert res.status_code == 401

    token = get_auth_token(client, "user_upload@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Missing file field -> 400
    res = client.post("/api/documents", headers=headers, data={})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "VALIDATION_ERROR"

    # 3. Unsupported media -> 415
    data = {"file": (io.BytesIO(b"binary"), "script.exe")}
    res = client.post(
        "/api/documents", headers=headers, data=data, content_type="multipart/form-data"
    )
    assert res.status_code == 415
    assert res.get_json()["error"]["code"] == "UNSUPPORTED_MEDIA"

    # 4. Empty file -> 400
    data = {"file": (io.BytesIO(b""), "empty.txt")}
    res = client.post(
        "/api/documents", headers=headers, data=data, content_type="multipart/form-data"
    )
    assert res.status_code == 400


def test_upload_document_success_and_async_processing(client, app):
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as chroma_tmp,
        tempfile.TemporaryDirectory() as upload_tmp,
    ):
        app.config["UPLOAD_DIR"] = upload_tmp
        app.config["CHROMA_DIR"] = chroma_tmp

        token = get_auth_token(client, "uploader@test.com")
        headers = {"Authorization": f"Bearer {token}"}

        file_content = (
            b"DocChat document management system test. "
            b"This text provides sufficient content for parsing and chunking verification. "
            b"It tests asynchronous processing via ThreadPoolExecutor."
        )
        data = {"file": (io.BytesIO(file_content), "async_test.txt")}

        start_time = time.time()
        res = client.post(
            "/api/documents",
            headers=headers,
            data=data,
            content_type="multipart/form-data",
        )
        elapsed = time.time() - start_time

        # Response must be fast (< 1s) and return 202 Accepted
        assert elapsed < 1.5
        assert res.status_code == 202
        res_data = res.get_json()
        assert res_data["status"] == "pending"
        assert res_data["filename"] == "async_test.txt"
        doc_id = res_data["id"]

        # Poll GET /api/documents/<id> until ready or failed (max 10s)
        ready = False
        for _ in range(50):
            time.sleep(0.2)
            check_res = client.get(f"/api/documents/{doc_id}", headers=headers)
            assert check_res.status_code == 200
            current_status = check_res.get_json()["status"]
            if current_status == "ready":
                ready = True
                break
            elif current_status == "failed":
                break

        assert ready is True
        doc_details = check_res.get_json()
        assert doc_details["chunk_count"] > 0
        assert doc_details["error_message"] is None


def test_startup_recovery_processing_reset(app):
    with app.app_context():
        user = User(name="Restart User", email="restart@test.com", password_hash="hash")
        db.session.add(user)
        db.session.commit()

        doc = Document(
            user_id=user.id,
            filename="stuck.pdf",
            stored_name=generate_storage_filename(".pdf"),
            mime_type="application/pdf",
            size_bytes=1024,
            status="processing",
        )
        db.session.add(doc)
        db.session.commit()

        # Run startup recovery
        from app import reset_stuck_documents

        reset_stuck_documents(app)

        recovered_doc = db.session.get(Document, doc.id)
        assert recovered_doc.status == "failed"
        assert "restarted" in recovered_doc.error_message.lower()


def test_list_and_get_document_owner_isolation(client, app):
    from unittest.mock import patch

    token_a = get_auth_token(client, "user_a@test.com")
    token_b = get_auth_token(client, "user_b@test.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Upload document as User A
    data_a = {
        "file": (
            io.BytesIO(b"User A confidential research memo regarding quarterly goals."),
            "user_a_memo.txt",
        )
    }
    with patch("app.api.documents.executor.submit"):
        res_a = client.post(
            "/api/documents", headers=headers_a, data=data_a, content_type="multipart/form-data"
        )
    assert res_a.status_code == 202
    doc_a_id = res_a.get_json()["id"]

    # 1. User A lists documents: contains doc_a
    list_a = client.get("/api/documents", headers=headers_a)
    assert list_a.status_code == 200
    ids_a = [d["id"] for d in list_a.get_json()]
    assert doc_a_id in ids_a

    # 2. User B lists documents: does NOT contain doc_a
    list_b = client.get("/api/documents", headers=headers_b)
    assert list_b.status_code == 200
    ids_b = [d["id"] for d in list_b.get_json()]
    assert doc_a_id not in ids_b

    # 3. User A gets own document -> 200
    get_own = client.get(f"/api/documents/{doc_a_id}", headers=headers_a)
    assert get_own.status_code == 200
    assert get_own.get_json()["filename"] == "user_a_memo.txt"

    # 4. Cross-user access: User B attempts to get User A's document -> 404 NOT_FOUND (never 403, per D2)
    get_other = client.get(f"/api/documents/{doc_a_id}", headers=headers_b)
    assert get_other.status_code == 404
    assert get_other.get_json()["error"]["code"] == "NOT_FOUND"


def test_delete_document_and_isolation(client, app):
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as chroma_tmp,
        tempfile.TemporaryDirectory() as upload_tmp,
    ):
        app.config["UPLOAD_DIR"] = upload_tmp
        app.config["CHROMA_DIR"] = chroma_tmp

        token_a = get_auth_token(client, "deleter_a@test.com")
        token_b = get_auth_token(client, "deleter_b@test.com")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Create document directly in DB and Chroma
        with app.app_context():
            user_a = User.query.filter_by(email="deleter_a@test.com").first()
            stored_name = "test_del.txt"
            file_path = os.path.join(upload_tmp, stored_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Document content to be deleted.")

            doc = Document(
                user_id=user_a.id,
                filename="to_delete.txt",
                stored_name=stored_name,
                mime_type="text/plain",
                size_bytes=len("Document content to be deleted."),
                status="ready",
                chunk_count=1,
            )
            db.session.add(doc)
            db.session.commit()

            chunk = Chunk(
                document_id=doc.id,
                chunk_index=0,
                page_number=1,
                text="Document content to be deleted.",
                char_count=len("Document content to be deleted."),
            )
            db.session.add(chunk)
            db.session.commit()

            # Insert vector
            store = VectorStore(persist_dir=chroma_tmp, collection_name="doc_chunks")
            try:
                store.upsert(
                    [
                        {
                            "chunk_id": chunk.id,
                            "user_id": user_a.id,
                            "document_id": doc.id,
                            "chunk_index": 0,
                            "page": 1,
                            "filename": "to_delete.txt",
                            "text": chunk.text,
                            "embedding": [0.05] * 384,
                        }
                    ]
                )
                assert store.count(user_id=user_a.id) == 1
            finally:
                store.close()

            doc_id = doc.id

        # 1. User B tries to delete User A's document -> 404 (never 403)
        res_del_b = client.delete(f"/api/documents/{doc_id}", headers=headers_b)
        assert res_del_b.status_code == 404

        # 2. User A deletes own document -> 200
        res_del_a = client.delete(f"/api/documents/{doc_id}", headers=headers_a)
        assert res_del_a.status_code == 200
        assert res_del_a.get_json()["message"] == "Document deleted"

        # 3. Verify file is gone from disk
        assert not os.path.exists(file_path)

        # 4. Verify Document and Chunks are gone from MySQL
        with app.app_context():
            assert db.session.get(Document, doc_id) is None
            assert Chunk.query.filter_by(document_id=doc_id).count() == 0

        # 5. Verify vectors removed from Chroma
        store = VectorStore(persist_dir=chroma_tmp, collection_name="doc_chunks")
        try:
            assert store.count(user_id=user_a.id) == 0
        finally:
            store.close()
