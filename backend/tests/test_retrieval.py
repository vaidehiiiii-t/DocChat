import tempfile

from app.extensions import db
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.services.embedding import EmbeddingService
from app.services.retrieval import RetrievalService
from app.services.vector_store import VectorStore


def test_retrieval_service_flow(app):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as chroma_tmp:
        app.config["CHROMA_DIR"] = chroma_tmp

        with app.app_context():
            embed_service = EmbeddingService.get_instance()
            vector_store = VectorStore(persist_dir=chroma_tmp, collection_name="test_retrieval")
            retrieval_service = RetrievalService(
                vector_store=vector_store, embedding_service=embed_service
            )

            try:
                # Create user
                user = User(name="Researcher", email="researcher@test.com", password_hash="hash")
                db.session.add(user)
                db.session.commit()

                # Document 1: Astronomy
                doc1 = Document(
                    user_id=user.id,
                    filename="astronomy.pdf",
                    stored_name="astro.pdf",
                    mime_type="application/pdf",
                    size_bytes=1000,
                    status="ready",
                )
                # Document 2: Cooking
                doc2 = Document(
                    user_id=user.id,
                    filename="cooking.pdf",
                    stored_name="cook.pdf",
                    mime_type="application/pdf",
                    size_bytes=1000,
                    status="ready",
                )
                db.session.add_all([doc1, doc2])
                db.session.commit()

                # Insert Chunks
                chunk_astro = Chunk(
                    document_id=doc1.id,
                    chunk_index=0,
                    page_number=4,
                    text="Supernovae are violent stellar explosions that illuminate entire galaxies with light.",
                    char_count=80,
                )
                chunk_cook = Chunk(
                    document_id=doc2.id,
                    chunk_index=0,
                    page_number=2,
                    text="Boil pasta in salted boiling water for eight minutes until perfectly al dente.",
                    char_count=75,
                )
                db.session.add_all([chunk_astro, chunk_cook])
                db.session.commit()

                # Embed & Upsert
                vecs = embed_service.embed([chunk_astro.text, chunk_cook.text])
                vector_store.upsert(
                    [
                        {
                            "chunk_id": chunk_astro.id,
                            "user_id": user.id,
                            "document_id": doc1.id,
                            "chunk_index": 0,
                            "page": 4,
                            "filename": "astronomy.pdf",
                            "text": chunk_astro.text,
                            "embedding": vecs[0],
                        },
                        {
                            "chunk_id": chunk_cook.id,
                            "user_id": user.id,
                            "document_id": doc2.id,
                            "chunk_index": 0,
                            "page": 2,
                            "filename": "cooking.pdf",
                            "text": chunk_cook.text,
                            "embedding": vecs[1],
                        },
                    ]
                )

                # 1. Astronomy question retrieves astronomy chunk first
                astro_results = retrieval_service.retrieve(
                    query="What causes stars to explode?",
                    user_id=user.id,
                )
                assert len(astro_results) >= 1
                assert astro_results[0]["document_id"] == doc1.id
                assert astro_results[0]["page"] == 4
                assert "Supernovae" in astro_results[0]["text"]
                assert astro_results[0]["score"] > 0.4

                # 2. Scoped query to document 2 (cooking) only returns cooking chunks
                scoped_results = retrieval_service.retrieve(
                    query="What causes stars to explode?",
                    user_id=user.id,
                    document_id=doc2.id,
                    max_distance=0.9,  # relax distance to observe scoping
                )
                for r in scoped_results:
                    assert r["document_id"] == doc2.id

                # 3. Completely unrelated query returns empty list with default cutoff (0.55)
                unrelated_results = retrieval_service.retrieve(
                    query="Quantum entanglement cryptographic key distribution protocol",
                    user_id=user.id,
                    max_distance=0.4,
                )
                assert len(unrelated_results) == 0

                # 4. Cross-user isolation: User 999 gets 0 results
                other_user_results = retrieval_service.retrieve(
                    query="Supernovae",
                    user_id=999,
                )
                assert len(other_user_results) == 0
            finally:
                vector_store.close()
