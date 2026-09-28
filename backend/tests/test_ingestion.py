import os
import tempfile
from unittest.mock import MagicMock

from app.extensions import db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.services.embedding import EmbeddingService
from app.services.ingestion import IngestionService
from app.services.vector_store import VectorStore


def test_ingestion_happy_path(app):
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as chroma_tmp,
        tempfile.TemporaryDirectory() as upload_tmp,
    ):
        app.config["UPLOAD_DIR"] = upload_tmp
        app.config["CHROMA_DIR"] = chroma_tmp

        with app.app_context():
            # Setup user and document
            user = User(name="Alice", email="alice@test.com", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            stored_filename = "doc1.txt"
            file_path = os.path.join(upload_tmp, stored_filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(
                    "DocChat is a powerful retrieval augmented generation platform. "
                    "It allows users to upload documents and query them using modern large language models. "
                    "Each document is parsed, split into manageable chunks, embedded into semantic vectors, "
                    "and indexed inside ChromaDB for similarity searching."
                )

            doc = Document(
                user_id=user.id,
                filename="docchat_intro.txt",
                stored_name=stored_filename,
                mime_type="text/plain",
                size_bytes=os.path.getsize(file_path),
                status="pending",
            )
            db.session.add(doc)
            db.session.commit()

            vector_store = VectorStore(persist_dir=chroma_tmp, collection_name="test_ingest")
            embed_service = EmbeddingService.get_instance()
            service = IngestionService(vector_store=vector_store, embedding_service=embed_service)

            try:
                success = service.process(doc.id)
                assert success is True

                updated_doc = db.session.get(Document, doc.id)
                assert updated_doc.status == "ready"
                assert updated_doc.chunk_count > 0
                assert updated_doc.error_message is None
                assert updated_doc.page_count == 1

                # MySQL chunks count
                db_chunk_count = Chunk.query.filter_by(document_id=doc.id).count()
                assert db_chunk_count == updated_doc.chunk_count

                # Chroma vectors count
                chroma_count = vector_store.count(user_id=user.id)
                assert chroma_count == db_chunk_count

                # Verify querying returns the chunk
                query_vec = embed_service.embed(["retrieval augmented generation"])[0]
                results = vector_store.query(query_vec, user_id=user.id, top_k=1)
                assert len(results) == 1
                assert results[0]["document_id"] == doc.id
            finally:
                vector_store.close()


def test_ingestion_forced_failure_rollback(app):
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as chroma_tmp,
        tempfile.TemporaryDirectory() as upload_tmp,
    ):
        app.config["UPLOAD_DIR"] = upload_tmp
        app.config["CHROMA_DIR"] = chroma_tmp

        with app.app_context():
            user = User(name="Bob", email="bob@test.com", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            stored_filename = "doc2.txt"
            file_path = os.path.join(upload_tmp, stored_filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("This file is valid but embedding will be forced to fail.")

            doc = Document(
                user_id=user.id,
                filename="failing_doc.txt",
                stored_name=stored_filename,
                mime_type="text/plain",
                size_bytes=os.path.getsize(file_path),
                status="pending",
            )
            db.session.add(doc)
            db.session.commit()

            vector_store = VectorStore(persist_dir=chroma_tmp, collection_name="test_fail")

            # Mock embedding service to raise an exception
            failing_embed_service = MagicMock()
            failing_embed_service.embed.side_effect = RuntimeError(
                "Embedding model GPU out of memory"
            )

            service = IngestionService(
                vector_store=vector_store, embedding_service=failing_embed_service
            )

            try:
                success = service.process(doc.id)
                assert success is False

                updated_doc = db.session.get(Document, doc.id)
                assert updated_doc.status == "failed"
                assert "Embedding model GPU out of memory" in (updated_doc.error_message or "")

                # Zero chunks in MySQL
                db_chunk_count = Chunk.query.filter_by(document_id=doc.id).count()
                assert db_chunk_count == 0

                # Zero vectors in Chroma
                chroma_count = vector_store.count(user_id=user.id)
                assert chroma_count == 0
            finally:
                vector_store.close()


def test_ingestion_idempotency(app):
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as chroma_tmp,
        tempfile.TemporaryDirectory() as upload_tmp,
    ):
        app.config["UPLOAD_DIR"] = upload_tmp
        app.config["CHROMA_DIR"] = chroma_tmp

        with app.app_context():
            user = User(name="Carol", email="carol@test.com", password_hash="hash")
            db.session.add(user)
            db.session.commit()

            stored_filename = "doc3.txt"
            file_path = os.path.join(upload_tmp, stored_filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("A document tested multiple times for idempotent re-ingestion.")

            doc = Document(
                user_id=user.id,
                filename="idempotent.txt",
                stored_name=stored_filename,
                mime_type="text/plain",
                size_bytes=os.path.getsize(file_path),
                status="pending",
            )
            db.session.add(doc)
            db.session.commit()

            vector_store = VectorStore(persist_dir=chroma_tmp, collection_name="test_idempotent")
            embed_service = EmbeddingService.get_instance()
            service = IngestionService(vector_store=vector_store, embedding_service=embed_service)

            try:
                # First run
                assert service.process(doc.id) is True
                first_chunk_count = Chunk.query.filter_by(document_id=doc.id).count()

                # Second run (re-ingest)
                assert service.process(doc.id) is True
                second_chunk_count = Chunk.query.filter_by(document_id=doc.id).count()

                assert first_chunk_count == second_chunk_count
                assert vector_store.count(user_id=user.id) == second_chunk_count
            finally:
                vector_store.close()
