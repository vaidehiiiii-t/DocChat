import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.extensions import db, limiter
from app.models.chat import ChatSession
from app.services.llm import LLMService


@pytest.fixture(autouse=True)
def reset_limiters():
    """Ensure limiter storage and LLM sliding window are clean before each test."""
    LLMService.reset_rate_limiter()
    limiter.reset()
    yield
    LLMService.reset_rate_limiter()
    limiter.reset()


def _create_user_and_token(client, email="ratetest@example.com"):
    res = client.post(
        "/api/auth/register",
        json={"name": "Rate Test", "email": email, "password": "password123"},
    )
    return res.get_json()["access_token"], res.get_json()["user"]["id"]


def test_chat_messages_per_user_rate_limit(client):
    token1, user1_id = _create_user_and_token(client, "user1@example.com")
    token2, user2_id = _create_user_and_token(client, "user2@example.com")

    # Create session for user 1
    session1 = ChatSession(user_id=user1_id, title="Test 1")
    session2 = ChatSession(user_id=user2_id, title="Test 2")
    db.session.add_all([session1, session2])
    db.session.commit()

    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    # User 1 makes 6 calls (limit is 6/min)
    for i in range(6):
        res = client.post(
            f"/api/chat/sessions/{session1.id}/messages",
            headers=headers1,
            json={"content": f"Hello {i}"},
        )
        assert res.status_code == 200, f"Call {i+1} failed: {res.get_json()}"

    # 7th call from User 1 must be blocked with 429
    res7 = client.post(
        f"/api/chat/sessions/{session1.id}/messages",
        headers=headers1,
        json={"content": "Blocked message"},
    )
    assert res7.status_code == 429
    data = res7.get_json()
    assert data["error"]["code"] == "RATE_LIMITED"

    # User 2 is independent and must NOT be blocked by User 1's usage
    res_u2 = client.post(
        f"/api/chat/sessions/{session2.id}/messages",
        headers=headers2,
        json={"content": "User 2 hello"},
    )
    assert res_u2.status_code == 200


def test_document_upload_per_user_rate_limit(client):
    token, user_id = _create_user_and_token(client, "uploader@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    from app.services.ingestion import IngestionService

    with patch.object(IngestionService, "process"):
        # Upload 10 files (limit is 10/min)
        for i in range(10):
            data = {
                "file": (
                    io.BytesIO(b"%PDF-1.4\nValid minimal pdf content test\n%%EOF"),
                    f"doc_{i}.pdf",
                )
            }
            res = client.post(
                "/api/documents",
                headers=headers,
                data=data,
                content_type="multipart/form-data",
            )
            assert res.status_code == 202, f"Upload {i+1} failed: {res.get_json()}"

        # 11th upload must be blocked with 429
        data_blocked = {
            "file": (
                io.BytesIO(b"%PDF-1.4\nValid minimal pdf content test\n%%EOF"),
                "doc_blocked.pdf",
            )
        }
        res11 = client.post(
            "/api/documents",
            headers=headers,
            data=data_blocked,
            content_type="multipart/form-data",
        )
        assert res11.status_code == 429
        assert res11.get_json()["error"]["code"] == "RATE_LIMITED"


def test_global_llm_throttle_shared_across_multiple_users():
    """Verify that multiple users together cannot exceed LLM_GLOBAL_RPM."""
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Fake answer"))]
    )

    # Set a small global RPM for test: 4 total RPM
    settings = Settings(ALLOW_PAID_MODELS=True, LLM_MODEL="free:free", LLM_GLOBAL_RPM=4)

    # User A service instance
    service_user_a = LLMService(client=fake_client, settings=settings)
    # User B service instance
    service_user_b = LLMService(client=fake_client, settings=settings)

    # User A makes 2 calls
    service_user_a.answer("Q1 from A", [])
    service_user_a.answer("Q2 from A", [])

    # User B makes 2 calls (total 4 reached)
    service_user_b.answer("Q1 from B", [])
    service_user_b.answer("Q2 from B", [])

    # Next call from User A or User B must hit global throttle
    from app.errors import AppError

    with pytest.raises(AppError) as exc_info:
        service_user_a.answer("Q3 from A (should fail)", [])

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "RATE_LIMITED"
