import logging
from datetime import datetime, timezone
from typing import Any, Optional

from flask import current_app

from app.extensions import db
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.parsing import NoTextError, ParsingService
from app.services.vector_store import VectorStore
from app.utils.files import get_safe_storage_path

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        parsing_service: Optional[ParsingService] = None,
        chunking_service: Optional[ChunkingService] = None,
    ):
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._parsing_service = parsing_service or ParsingService()
        self._chunking_service = chunking_service

    def _get_vector_store(self) -> VectorStore:
        if self._vector_store is not None:
            return self._vector_store
        chroma_dir = current_app.config.get("CHROMA_DIR", "./storage/chroma")
        return VectorStore(persist_dir=chroma_dir)

    def _get_embedding_service(self) -> EmbeddingService:
        if self._embedding_service is not None:
            return self._embedding_service
        return EmbeddingService.get_instance()

    def _get_chunking_service(self) -> ChunkingService:
        if self._chunking_service is not None:
            return self._chunking_service
        settings = current_app.config.get("DOCCHAT_SETTINGS")
        chunk_size = settings.CHUNK_SIZE if settings else 800
        chunk_overlap = settings.CHUNK_OVERLAP if settings else 150
        return ChunkingService(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def process(self, document_id: int) -> bool:
        """
        Execute document ingestion pipeline:
        1. Set status='processing'
        2. Idempotent cleanup of old chunks & vectors
        3. Parse pages
        4. Chunk pages
        5. Insert DB chunks
        6. Batch embed chunk texts
        7. Upsert vectors to ChromaDB
        8. Set status='ready'
        On exception: rollback DB, clean vectors, delete chunks, set status='failed'.
        """
        vector_store = self._get_vector_store()
        doc = db.session.get(Document, document_id)
        if not doc:
            logger.warning("Document with id %s not found for processing", document_id)
            return False

        try:
            # 1. Update status to processing
            doc.status = "processing"
            doc.error_message = None
            doc.updated_at = datetime.now(timezone.utc)
            db.session.commit()

            # 2. Idempotency cleanup
            vector_store.delete_document(document_id)
            Chunk.query.filter_by(document_id=document_id).delete()
            db.session.commit()

            # 3. Locate file & parse
            upload_dir = current_app.config.get("UPLOAD_DIR", "./storage/uploads")
            file_path = get_safe_storage_path(upload_dir, doc.stored_name)
            pages = self._parsing_service.parse(file_path, doc.filename)

            # 4. Chunk
            chunking_service = self._get_chunking_service()
            chunks_data = chunking_service.chunk_pages(pages)
            if not chunks_data:
                raise NoTextError("Document contains insufficient readable text for chunking.")

            # 5. Insert chunks into DB
            db_chunks: list[Chunk] = []
            for c in chunks_data:
                db_chunk = Chunk(
                    document_id=doc.id,
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    text=c.text,
                    char_count=c.char_count,
                )
                db_chunks.append(db_chunk)

            db.session.add_all(db_chunks)
            db.session.flush()

            # 6. Embed chunk texts
            embedding_service = self._get_embedding_service()
            texts = [c.text for c in db_chunks]
            embeddings = embedding_service.embed(texts, batch_size=64)

            # 7. Upsert to ChromaDB
            upsert_items: list[dict[str, Any]] = []
            for i, c in enumerate(db_chunks):
                upsert_items.append(
                    {
                        "chunk_id": c.id,
                        "user_id": doc.user_id,
                        "document_id": doc.id,
                        "chunk_index": c.chunk_index,
                        "page": c.page_number or 1,
                        "filename": doc.filename,
                        "text": c.text,
                        "embedding": embeddings[i],
                    }
                )

            vector_store.upsert(upsert_items)

            # 8. Mark ready
            doc.page_count = len(pages)
            doc.chunk_count = len(db_chunks)
            doc.status = "ready"
            doc.error_message = None
            doc.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return True

        except Exception as exc:
            logger.exception("Ingestion failed for document %s: %s", document_id, exc)
            db.session.rollback()

            # Clean Chroma
            try:
                vector_store.delete_document(document_id)
            except Exception as cv_err:
                logger.warning(
                    "Failed to clean up Chroma vectors for document %s: %s", document_id, cv_err
                )

            # Update document to failed state and remove DB chunks
            try:
                Chunk.query.filter_by(document_id=document_id).delete()
                failed_doc = db.session.get(Document, document_id)
                if failed_doc:
                    failed_doc.status = "failed"
                    failed_doc.error_message = str(exc)
                    failed_doc.updated_at = datetime.now(timezone.utc)
                    db.session.commit()
            except Exception as db_err:
                logger.exception("Failed to mark document %s as failed: %s", document_id, db_err)
                db.session.rollback()

            return False
