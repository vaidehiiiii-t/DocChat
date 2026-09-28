import logging
from typing import Any, Optional

from flask import current_app

from app.models.chunk import Chunk
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self._vector_store = vector_store
        self._embedding_service = embedding_service

    def _get_vector_store(self) -> VectorStore:
        if self._vector_store is not None:
            return self._vector_store
        chroma_dir = current_app.config.get("CHROMA_DIR", "./storage/chroma")
        return VectorStore(persist_dir=chroma_dir)

    def _get_embedding_service(self) -> EmbeddingService:
        if self._embedding_service is not None:
            return self._embedding_service
        return EmbeddingService.get_instance()

    def retrieve(
        self,
        query: str,
        user_id: int,
        document_id: Optional[int] = None,
        top_k: Optional[int] = None,
        max_distance: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """
        Embed question -> VectorStore.query (filtered by user_id and optional document_id)
        -> drop results with distance > max_distance -> hydrate with MySQL chunk info.
        """
        if not query or not query.strip():
            return []

        settings = current_app.config.get("DOCCHAT_SETTINGS")
        k = top_k if top_k is not None else (settings.TOP_K if settings else 5)
        cutoff = (
            max_distance
            if max_distance is not None
            else (settings.MAX_DISTANCE if settings else 0.55)
        )

        embedding_service = self._get_embedding_service()
        vector_store = self._get_vector_store()

        query_vectors = embedding_service.embed([query.strip()])
        if not query_vectors:
            return []
        query_vector = query_vectors[0]

        raw_results = vector_store.query(
            embedding=query_vector,
            user_id=user_id,
            top_k=k,
            document_id=document_id,
        )

        # Drop results with distance > cutoff
        filtered = [r for r in raw_results if r["distance"] <= cutoff]
        if not filtered:
            return []

        # Hydrate from MySQL chunks for consistency
        chunk_ids = [r["chunk_id"] for r in filtered]
        db_chunks = {c.id: c for c in Chunk.query.filter(Chunk.id.in_(chunk_ids)).all()}

        retrieved: list[dict[str, Any]] = []
        for r in filtered:
            cid = r["chunk_id"]
            db_chunk = db_chunks.get(cid)
            chunk_text = db_chunk.text if db_chunk else r.get("text", "")
            page_num = (
                db_chunk.page_number
                if db_chunk and db_chunk.page_number is not None
                else r.get("page", 1)
            )

            snippet = chunk_text[:200] + ("..." if len(chunk_text) > 200 else "")
            score = round(1.0 - r["distance"], 2)

            retrieved.append(
                {
                    "chunk_id": cid,
                    "document_id": r["document_id"],
                    "filename": r.get("filename", ""),
                    "page": page_num,
                    "snippet": snippet,
                    "text": chunk_text,
                    "score": score,
                    "distance": r["distance"],
                }
            )

        return retrieved
