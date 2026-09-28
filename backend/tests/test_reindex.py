import os
import shutil
import sys
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config import Config, Settings
from app.extensions import db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.services.vector_store import VectorStore
from scripts.reindex import reindex


@pytest.fixture
def temp_chroma_dir():
    temp_dir = tempfile.mkdtemp(prefix="test_reindex_chroma_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_reindex_with_ready_documents(app, temp_chroma_dir):
    """Test reindexing MySQL chunks into Chroma vector store."""
    with app.app_context():
        # Setup user and documents
        user = User(email="reindex_user@example.com", password_hash="hashed_pw")
        db.session.add(user)
        db.session.commit()

        # Doc 1: ready with 2 chunks
        doc1 = Document(
            user_id=user.id,
            filename="research_paper.pdf",
            stored_name="stored_1.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            page_count=2,
            chunk_count=2,
            status="ready",
        )
        # Doc 2: failed with 1 chunk (should not be indexed)
        doc2 = Document(
            user_id=user.id,
            filename="failed_doc.pdf",
            stored_name="stored_2.pdf",
            mime_type="application/pdf",
            size_bytes=512,
            page_count=1,
            chunk_count=1,
            status="failed",
        )
        db.session.add_all([doc1, doc2])
        db.session.commit()

        chunk1 = Chunk(
            document_id=doc1.id,
            chunk_index=0,
            page_number=1,
            text="Quantum computing leverages superposition and entanglement.",
            char_count=60,
        )
        chunk2 = Chunk(
            document_id=doc1.id,
            chunk_index=1,
            page_number=2,
            text="Qubits can represent exponentially large computational spaces.",
            char_count=62,
        )
        chunk3 = Chunk(
            document_id=doc2.id,
            chunk_index=0,
            page_number=1,
            text="This chunk belongs to a failed document and must not be indexed.",
            char_count=65,
        )
        db.session.add_all([chunk1, chunk2, chunk3])
        db.session.commit()

        # Run reindex pointing to our temporary chroma path
        # Override settings for the duration
        custom_settings = Settings(
            DATABASE_URL=app.config["SQLALCHEMY_DATABASE_URI"],
            CHROMA_DIR=temp_chroma_dir,
        )

        from unittest.mock import patch
        with patch("scripts.reindex.Settings", return_value=custom_settings):
            exit_code = reindex(batch_size=1, chroma_path=temp_chroma_dir, app=app)

        assert exit_code == 0

        # Verify VectorStore count
        store = VectorStore(persist_dir=temp_chroma_dir)
        assert store.count() == 2  # Only the 2 ready chunks indexed!

        # Query vector store
        from app.services.embedding import EmbeddingService
        emb_service = EmbeddingService(model_name="sentence-transformers/all-MiniLM-L6-v2")
        query_emb = emb_service.embed(["quantum computing"])[0]
        results = store.query(query_emb, user_id=user.id, top_k=2)

        assert len(results) == 2
        assert any("superposition" in r["text"] for r in results)
