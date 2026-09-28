import tempfile

import numpy as np
import pytest

from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore

# --- M3-T1: EmbeddingService Tests ---


def test_embedding_service_dimensions_and_consistency():
    service = EmbeddingService.get_instance()

    texts = [
        "The quick brown fox jumps over the lazy dog.",
        "The quick brown fox jumps over the lazy dog.",
        "A fast auburn canine leaps above an inactive hound.",
        "Quantum computing relies on qubits and superposition.",
    ]

    embeddings = service.embed(texts)

    # 1. Output length and dimension (384 for all-MiniLM-L6-v2)
    assert len(embeddings) == 4
    for vec in embeddings:
        assert len(vec) == 384
        assert isinstance(vec[0], float)

    # 2. Identical text gives identical vector
    v1 = np.array(embeddings[0])
    v2 = np.array(embeddings[1])
    assert np.allclose(v1, v2, atol=1e-5)

    # 3. Similar sentences score higher cosine similarity than unrelated ones
    v3 = np.array(embeddings[2])  # paraphrase of fox
    v4 = np.array(embeddings[3])  # quantum computing

    sim_similar = float(np.dot(v1, v3))
    sim_unrelated = float(np.dot(v1, v4))

    assert sim_similar > sim_unrelated
    assert sim_similar > 0.5  # strongly semantic match


def test_embedding_service_empty():
    service = EmbeddingService.get_instance()
    assert service.embed([]) == []


# --- M3-T2: VectorStore Tests ---


def test_vector_store_upsert_query_delete():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = VectorStore(persist_dir=tmp_dir, collection_name="test_collection")
        try:
            embed_service = EmbeddingService.get_instance()

            chunks_data = [
                {
                    "chunk_id": 1,
                    "document_id": 10,
                    "text": "Apples and oranges are delicious fruits.",
                    "page": 1,
                    "filename": "fruits.txt",
                },
                {
                    "chunk_id": 2,
                    "document_id": 10,
                    "text": "Bananas and grapes grow in warm climates.",
                    "page": 2,
                    "filename": "fruits.txt",
                },
                {
                    "chunk_id": 3,
                    "document_id": 10,
                    "text": "Strawberries are bright red berries.",
                    "page": 3,
                    "filename": "fruits.txt",
                },
                {
                    "chunk_id": 4,
                    "document_id": 20,
                    "text": "Automobiles require regular oil changes.",
                    "page": 1,
                    "filename": "cars.txt",
                },
                {
                    "chunk_id": 5,
                    "document_id": 20,
                    "text": "Electric cars run on lithium battery packs.",
                    "page": 2,
                    "filename": "cars.txt",
                },
            ]

            texts = [c["text"] for c in chunks_data]
            vectors = embed_service.embed(texts)

            chunks_to_upsert = []
            for i, c in enumerate(chunks_data):
                chunks_to_upsert.append(
                    {
                        "chunk_id": c["chunk_id"],
                        "user_id": 100,
                        "document_id": c["document_id"],
                        "chunk_index": i,
                        "page": c["page"],
                        "filename": c["filename"],
                        "text": c["text"],
                        "embedding": vectors[i],
                    }
                )

            # Upsert 5 chunks
            store.upsert(chunks_to_upsert)
            assert store.count() == 5
            assert store.count(user_id=100) == 5

            # Query fruit-related topic
            query_vec = embed_service.embed(["Fresh citrus fruit salad"])[0]
            results = store.query(query_vec, user_id=100, top_k=3)

            assert len(results) == 3
            # Nearest should be one of the fruit chunks (doc 10)
            assert results[0]["document_id"] == 10
            assert results[0]["distance"] < 0.6

            # Scoped query to document 20 only
            scoped_results = store.query(query_vec, user_id=100, top_k=3, document_id=20)
            assert len(scoped_results) == 2
            for r in scoped_results:
                assert r["document_id"] == 20

            # Delete document 10
            store.delete_document(document_id=10)
            assert store.count(user_id=100) == 2

            # Verify only doc 20 remains
            remaining = store.query(query_vec, user_id=100, top_k=5)
            assert len(remaining) == 2
            for r in remaining:
                assert r["document_id"] == 20
        finally:
            store.close()


# --- M3-T3: Defensive Isolation Tests ---


def test_vector_store_isolation_guards():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        store = VectorStore(persist_dir=tmp_dir, collection_name="test_isolation")
        try:
            embed_service = EmbeddingService.get_instance()

            # 1. Guard check: query without user_id raises ValueError
            dummy_vec = [0.1] * 384
            with pytest.raises(ValueError, match="user_id is required"):
                store.query(dummy_vec, user_id=0)

            with pytest.raises(ValueError, match="user_id is required"):
                store.query(dummy_vec, user_id=None)  # type: ignore

            # 2. Cross-user isolation check: User A and User B chunks
            text_a = "Secret project code name Pegasus for User A"
            text_b = "Secret project code name Apollo for User B"

            vecs = embed_service.embed([text_a, text_b])

            store.upsert(
                [
                    {
                        "chunk_id": 101,
                        "user_id": 1,
                        "document_id": 1,
                        "chunk_index": 0,
                        "page": 1,
                        "filename": "user_a.txt",
                        "text": text_a,
                        "embedding": vecs[0],
                    },
                    {
                        "chunk_id": 102,
                        "user_id": 2,
                        "document_id": 2,
                        "chunk_index": 0,
                        "page": 1,
                        "filename": "user_b.txt",
                        "text": text_b,
                        "embedding": vecs[1],
                    },
                ]
            )

            assert store.count(user_id=1) == 1
            assert store.count(user_id=2) == 1

            # User 1 queries for User B's exact topic
            query_apollo = embed_service.embed(["Apollo project secret"])[0]
            results_user_1 = store.query(query_apollo, user_id=1, top_k=5)

            # User 1 must NEVER see User 2's chunk
            for item in results_user_1:
                assert item["chunk_id"] != 102
                assert "Apollo" not in item["text"]

            # User 2 queries for User A's exact topic
            query_pegasus = embed_service.embed(["Pegasus project secret"])[0]
            results_user_2 = store.query(query_pegasus, user_id=2, top_k=5)

            # User 2 must NEVER see User 1's chunk
            for item in results_user_2:
                assert item["chunk_id"] != 101
                assert "Pegasus" not in item["text"]
        finally:
            store.close()
