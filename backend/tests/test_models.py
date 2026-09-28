import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ChatSession, Chunk, Document, Message, User


def test_models_crud_basic(app):
    with app.app_context():
        # 1. Create User
        user = User(
            name="Alice",
            email="alice@example.com",
            password_hash="hashed_pw_alice",
        )
        db.session.add(user)
        db.session.commit()
        assert user.id is not None
        assert user.name == "Alice"

        # 2. Create Document
        doc = Document(
            user_id=user.id,
            filename="report.pdf",
            stored_name="abc-123.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            page_count=2,
            chunk_count=2,
            status="ready",
        )
        db.session.add(doc)
        db.session.commit()
        assert doc.id is not None
        assert doc.status == "ready"

        # 3. Create Chunks
        c1 = Chunk(
            document_id=doc.id,
            chunk_index=0,
            page_number=1,
            text="First chunk text",
            char_count=16,
        )
        c2 = Chunk(
            document_id=doc.id,
            chunk_index=1,
            page_number=2,
            text="Second chunk text",
            char_count=17,
        )
        db.session.add_all([c1, c2])
        db.session.commit()
        assert c1.id is not None
        assert c2.id is not None

        # 4. Create ChatSession
        session = ChatSession(
            user_id=user.id,
            document_id=doc.id,
            title="Chat about report",
        )
        db.session.add(session)
        db.session.commit()
        assert session.id is not None
        assert session.document_id == doc.id

        # 5. Create Messages
        m1 = Message(
            session_id=session.id,
            role="user",
            content="What is in the report?",
        )
        m2 = Message(
            session_id=session.id,
            role="assistant",
            content="Here is what is in the report.",
            sources_json=[{"chunk_id": c1.id, "page": 1, "filename": "report.pdf"}],
        )
        db.session.add_all([m1, m2])
        db.session.commit()
        assert m1.id is not None
        assert m2.id is not None
        assert len(session.messages) == 2


def test_unique_document_chunk_index_constraint(app):
    with app.app_context():
        user = User(name="Bob", email="bob@example.com", password_hash="hash")
        db.session.add(user)
        db.session.commit()

        doc = Document(
            user_id=user.id,
            filename="test.txt",
            stored_name="uuid.txt",
            mime_type="text/plain",
            size_bytes=100,
        )
        db.session.add(doc)
        db.session.commit()

        c1 = Chunk(document_id=doc.id, chunk_index=0, text="one", char_count=3)
        c2 = Chunk(document_id=doc.id, chunk_index=0, text="duplicate index", char_count=15)
        db.session.add(c1)
        db.session.commit()

        db.session.add(c2)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_cascade_delete_user_removes_everything(app):
    with app.app_context():
        user = User(name="Charlie", email="charlie@example.com", password_hash="hash")
        db.session.add(user)
        db.session.commit()

        doc = Document(
            user_id=user.id,
            filename="c.pdf",
            stored_name="c.pdf",
            mime_type="application/pdf",
            size_bytes=50,
        )
        db.session.add(doc)
        db.session.commit()

        chunk = Chunk(document_id=doc.id, chunk_index=0, text="data", char_count=4)
        session = ChatSession(user_id=user.id, document_id=doc.id, title="Session")
        db.session.add_all([chunk, session])
        db.session.commit()

        msg = Message(session_id=session.id, role="user", content="hello")
        db.session.add(msg)
        db.session.commit()

        user_id = user.id
        doc_id = doc.id
        chunk_id = chunk.id
        session_id = session.id
        msg_id = msg.id

        # Delete user
        db.session.delete(user)
        db.session.commit()

        assert db.session.get(User, user_id) is None
        assert db.session.get(Document, doc_id) is None
        assert db.session.get(Chunk, chunk_id) is None
        assert db.session.get(ChatSession, session_id) is None
        assert db.session.get(Message, msg_id) is None


def test_delete_document_sets_session_document_id_null(app):
    with app.app_context():
        user = User(name="David", email="david@example.com", password_hash="hash")
        db.session.add(user)
        db.session.commit()

        doc = Document(
            user_id=user.id,
            filename="d.pdf",
            stored_name="d.pdf",
            mime_type="application/pdf",
            size_bytes=50,
        )
        db.session.add(doc)
        db.session.commit()

        session = ChatSession(user_id=user.id, document_id=doc.id, title="Session")
        db.session.add(session)
        db.session.commit()

        assert session.document_id == doc.id

        # Delete document
        db.session.delete(doc)
        db.session.commit()

        # Session should still exist, but document_id should be NULL
        reloaded_session = db.session.get(ChatSession, session.id)
        assert reloaded_session is not None
        assert reloaded_session.document_id is None
