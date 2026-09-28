from unittest.mock import patch

from app.extensions import db
from app.models.chat import Message
from app.models.document import Document
from app.models.user import User


def get_token(client, email="chat_user@test.com"):
    client.post(
        "/api/auth/register",
        json={"name": "Chat User", "email": email, "password": "Password123!"},
    )
    res = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return res.get_json()["access_token"]


def test_chat_session_crud_and_isolation(client, app):
    token_a = get_token(client, "user_chat_a@test.com")
    token_b = get_token(client, "user_chat_b@test.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    with app.app_context():
        user_a = User.query.filter_by(email="user_chat_a@test.com").first()
        doc_a = Document(
            user_id=user_a.id,
            filename="a.pdf",
            stored_name="a.pdf",
            mime_type="application/pdf",
            size_bytes=100,
            status="ready",
        )
        doc_pending = Document(
            user_id=user_a.id,
            filename="pending.pdf",
            stored_name="pending.pdf",
            mime_type="application/pdf",
            size_bytes=100,
            status="pending",
        )
        db.session.add_all([doc_a, doc_pending])
        db.session.commit()
        doc_a_id = doc_a.id
        doc_pending_id = doc_pending.id

    # 1. User B tries to scope session to User A's document -> 404
    res = client.post(
        "/api/chat/sessions",
        headers=headers_b,
        json={"document_id": doc_a_id, "title": "Sneak attempt"},
    )
    assert res.status_code == 404

    # 2. User A scopes to pending document -> 400
    res = client.post(
        "/api/chat/sessions",
        headers=headers_a,
        json={"document_id": doc_pending_id},
    )
    assert res.status_code == 400

    # 3. User A creates valid scoped session
    res = client.post(
        "/api/chat/sessions",
        headers=headers_a,
        json={"document_id": doc_a_id, "title": "My Analysis"},
    )
    assert res.status_code == 201
    session_id = res.get_json()["id"]

    # 4. User B tries to get or delete User A's session -> 404
    assert (
        client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers_b).status_code
        == 404
    )
    assert client.delete(f"/api/chat/sessions/{session_id}", headers=headers_b).status_code == 404

    # 5. User A lists sessions -> contains session_id
    list_res = client.get("/api/chat/sessions", headers=headers_a)
    assert list_res.status_code == 200
    ids = [s["id"] for s in list_res.get_json()]
    assert session_id in ids

    # 6. User A deletes session -> 200
    del_res = client.delete(f"/api/chat/sessions/{session_id}", headers=headers_a)
    assert del_res.status_code == 200
    assert (
        client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers_a).status_code
        == 404
    )


def test_post_message_short_circuit_when_no_retrieval(client, app):
    token = get_token(client, "short_circuit@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create session
    create_res = client.post("/api/chat/sessions", headers=headers, json={})
    session_id = create_res.get_json()["id"]

    # Mock RetrievalService to return empty list
    with patch("app.api.chat.RetrievalService.retrieve", return_value=[]):
        with patch("app.api.chat.LLMService.answer") as mock_llm_answer:
            res = client.post(
                f"/api/chat/sessions/{session_id}/messages",
                headers=headers,
                json={"content": "What is the capital of Mars?"},
            )

            assert res.status_code == 200
            data = res.get_json()
            assert data["assistant_message"]["content"] == "I couldn't find this in your documents."
            assert data["assistant_message"]["sources"] == []
            # Decision D4: LLM must NOT be called!
            mock_llm_answer.assert_not_called()

            # Auto-title check: session title set from first message
            session_check = client.get("/api/chat/sessions", headers=headers).get_json()[0]
            assert "What is the capital of Mars?" in session_check["title"]


def test_post_message_grounded_success_and_sources(client, app):
    token = get_token(client, "grounded_user@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/chat/sessions", headers=headers, json={})
    session_id = create_res.get_json()["id"]

    fake_sources = [
        {
            "chunk_id": 501,
            "document_id": 10,
            "filename": "quarterly.pdf",
            "page": 3,
            "snippet": "Revenue grew by 24% year over year.",
            "text": "Full paragraph: Revenue grew by 24% year over year.",
            "score": 0.88,
        }
    ]

    with patch("app.api.chat.RetrievalService.retrieve", return_value=fake_sources):
        with patch(
            "app.api.chat.LLMService.answer",
            return_value=("According to [1], revenue grew by 24%.", "test-model"),
        ):
            res = client.post(
                f"/api/chat/sessions/{session_id}/messages",
                headers=headers,
                json={"content": "How much did revenue grow?"},
            )

            assert res.status_code == 200
            data = res.get_json()
            assert "revenue grew by 24%" in data["assistant_message"]["content"]
            assert len(data["assistant_message"]["sources"]) == 1
            src = data["assistant_message"]["sources"][0]
            assert src["chunk_id"] == 501
            assert src["filename"] == "quarterly.pdf"
            assert src["score"] == 0.88


def test_message_validation_and_llm_failure(client, app):
    token = get_token(client, "validation_user@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/api/chat/sessions", headers=headers, json={})
    session_id = create_res.get_json()["id"]

    # 1. Empty message -> 400
    res_empty = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "   "},
    )
    assert res_empty.status_code == 400

    # 2. Exceeding 2000 chars -> 400
    res_long = client.post(
        f"/api/chat/sessions/{session_id}/messages",
        headers=headers,
        json={"content": "A" * 2001},
    )
    assert res_long.status_code == 400

    # 3. LLM failure (e.g. 503) -> user message saved, no assistant message saved
    fake_sources = [
        {
            "chunk_id": 1,
            "document_id": 1,
            "filename": "f.txt",
            "page": 1,
            "snippet": "s",
            "text": "t",
            "score": 0.8,
        }
    ]
    from app.errors import AppError

    with patch("app.api.chat.RetrievalService.retrieve", return_value=fake_sources):
        with patch(
            "app.api.chat.LLMService.answer",
            side_effect=AppError("The AI model is busy.", code="LLM_UNAVAILABLE", status_code=503),
        ):
            res_fail = client.post(
                f"/api/chat/sessions/{session_id}/messages",
                headers=headers,
                json={"content": "Valid question that will encounter LLM error"},
            )
            assert res_fail.status_code == 503
            assert res_fail.get_json()["error"]["code"] == "LLM_UNAVAILABLE"

            # Check messages in DB: user message is preserved, no assistant message
            with app.app_context():
                messages = Message.query.filter_by(session_id=session_id).all()
                assert len(messages) == 1
                assert messages[0].role == "user"


def parse_sse_events(raw_text: str) -> list[tuple[str, str]]:
    """Parse raw SSE text into list of (event_type, data_payload) tuples."""
    events = []
    current_event = "message"
    for block in raw_text.strip().split("\n\n"):
        lines = block.strip().split("\n")
        event_name = current_event
        data_lines = []
        for line in lines:
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        if data_lines:
            events.append((event_name, "\n".join(data_lines)))
    return events


def test_stream_message_grounded_success_event_order(client, app):
    token = get_token(client, "stream_user@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    sess_res = client.post("/api/chat/sessions", headers=headers, json={"title": "Stream Test"})
    session_id = sess_res.get_json()["id"]

    fake_sources = [
        {
            "chunk_id": 10,
            "document_id": 5,
            "filename": "doc.pdf",
            "page": 2,
            "snippet": "Artificial intelligence document excerpt.",
            "text": "Artificial intelligence document excerpt.",
            "score": 0.88,
        }
    ]

    def fake_stream(query, sources, history=None):
        yield "AI "
        yield "is "
        yield "grounded."

    with patch("app.api.chat.RetrievalService.retrieve", return_value=fake_sources):
        with patch("app.api.chat.LLMService.stream_answer", side_effect=fake_stream):
            res = client.post(
                f"/api/chat/sessions/{session_id}/messages/stream",
                headers=headers,
                json={"content": "What is AI?"},
            )
            assert res.status_code == 200
            assert "text/event-stream" in res.headers["Content-Type"]

            events = parse_sse_events(res.get_data(as_text=True))
            assert len(events) >= 3

            # Event 1: sources
            assert events[0][0] == "sources"
            import json

            sources_data = json.loads(events[0][1])
            assert len(sources_data) == 1
            assert sources_data[0]["filename"] == "doc.pdf"

            # Tokens in order
            token_events = [e for e in events if e[0] == "token"]
            assert len(token_events) == 3
            tokens = [json.loads(e[1])["token"] for e in token_events]
            assert "".join(tokens) == "AI is grounded."

            # Last Event: done
            assert events[-1][0] == "done"
            done_data = json.loads(events[-1][1])
            assert "assistant_message_id" in done_data
            assert "user_message_id" in done_data

            # Verify exactly 1 user message and 1 assistant message in DB
            with app.app_context():
                msgs = (
                    Message.query.filter_by(session_id=session_id).order_by(Message.id.asc()).all()
                )
                assert len(msgs) == 2
                assert msgs[0].role == "user"
                assert msgs[0].content == "What is AI?"
                assert msgs[1].role == "assistant"
                assert msgs[1].content == "AI is grounded."
                assert len(msgs[1].sources_json) == 1


def test_stream_message_short_circuit_no_retrieval(client, app):
    token = get_token(client, "stream_no_chunks@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    sess_res = client.post(
        "/api/chat/sessions", headers=headers, json={"title": "Short Circuit Stream"}
    )
    session_id = sess_res.get_json()["id"]

    with patch("app.api.chat.RetrievalService.retrieve", return_value=[]):
        with patch("app.api.chat.LLMService.stream_answer") as mock_stream:
            res = client.post(
                f"/api/chat/sessions/{session_id}/messages/stream",
                headers=headers,
                json={"content": "Irrelevant query without any matches"},
            )
            assert res.status_code == 200
            # LLM stream must NOT be invoked
            mock_stream.assert_not_called()

            events = parse_sse_events(res.get_data(as_text=True))
            # sources event
            assert events[0][0] == "sources"
            assert events[0][1] == "[]"

            # token event
            import json

            assert events[1][0] == "token"
            assert "couldn't find this" in json.loads(events[1][1])["token"]

            # done event
            assert events[2][0] == "done"


def test_stream_message_error_event_on_failure(client, app):
    token = get_token(client, "stream_err_user@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    sess_res = client.post("/api/chat/sessions", headers=headers, json={"title": "Error Stream"})
    session_id = sess_res.get_json()["id"]

    fake_sources = [
        {
            "chunk_id": 1,
            "document_id": 1,
            "filename": "x.txt",
            "page": 1,
            "snippet": "s",
            "score": 0.9,
        }
    ]

    def failing_stream(query, sources, history=None):
        raise RuntimeError("Network drop during stream")

    with patch("app.api.chat.RetrievalService.retrieve", return_value=fake_sources):
        with patch("app.api.chat.LLMService.stream_answer", side_effect=failing_stream):
            res = client.post(
                f"/api/chat/sessions/{session_id}/messages/stream",
                headers=headers,
                json={"content": "Will trigger streaming error"},
            )
            assert res.status_code == 200
            events = parse_sse_events(res.get_data(as_text=True))

            # Error event emitted
            error_events = [e for e in events if e[0] == "error"]
            assert len(error_events) == 1

            # Decision D11: on stream abort/error, no partial assistant message is saved
            with app.app_context():
                msgs = Message.query.filter_by(session_id=session_id).all()
                assert len(msgs) == 1
                assert msgs[0].role == "user"
