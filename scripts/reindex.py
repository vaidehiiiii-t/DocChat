#!/usr/bin/env python3
"""
DocChat - Vector Store Reindexer
Rebuilds the Chroma vector store directly from MySQL/TiDB `chunks` table.

Usage:
    python scripts/reindex.py [--batch-size 50] [--storage-path ./storage/chroma]
"""

import argparse
import logging
import os
import sys

# Ensure backend package can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app import create_app
from app.config import Config, Settings
from app.extensions import db
from app.models.chunk import Chunk
from app.models.document import Document
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reindexer")


def reindex(batch_size: int = 50, chroma_path: str = None, app=None) -> int:
    settings = Settings()
    persist_dir = chroma_path or settings.CHROMA_DIR

    if app is None:
        app = create_app(Config(settings))
    with app.app_context():
        logger.info(f"Connecting to database and inspecting chunks...")
        
        # 1. Fetch ready documents and their chunks
        ready_docs = Document.query.filter_by(status="ready").all()
        ready_doc_ids = [d.id for d in ready_docs]
        doc_map = {d.id: d for d in ready_docs}

        if not ready_doc_ids:
            logger.info("No documents with status='ready' found in database. Nothing to reindex.")
            # Ensure Chroma collection is initialized and empty
            vector_store = VectorStore(persist_dir=persist_dir)
            logger.info(f"Vector store initialized at {persist_dir}. Chunks in Chroma: {vector_store.count()}")
            return 0

        total_chunks = Chunk.query.filter(Chunk.document_id.in_(ready_doc_ids)).count()
        logger.info(f"Found {len(ready_docs)} ready documents containing {total_chunks} total chunks.")

        # 2. Initialize Chroma and reset/recreate collection
        logger.info(f"Initializing Chroma store at: {persist_dir}")
        vector_store = VectorStore(persist_dir=persist_dir)
        try:
            vector_store.client.delete_collection(vector_store.collection_name)
            logger.info(f"Existing collection '{vector_store.collection_name}' deleted.")
        except Exception:
            pass

        # Recreate fresh collection
        vector_store.collection = vector_store.client.get_or_create_collection(
            name=vector_store.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        # 3. Load embedding service
        logger.info("Initializing embedding model (sentence-transformers)...")
        embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)

        # 4. Stream and process chunks in batches
        logger.info(f"Beginning reindexing in batches of {batch_size}...")
        offset = 0
        indexed_count = 0

        while True:
            chunks = (
                Chunk.query.filter(Chunk.document_id.in_(ready_doc_ids))
                .order_by(Chunk.id.asc())
                .offset(offset)
                .limit(batch_size)
                .all()
            )
            if not chunks:
                break

            texts = [c.text for c in chunks]
            embeddings = embedding_service.embed(texts)

            items_to_upsert = []
            for chunk, emb in zip(chunks, embeddings):
                doc = doc_map.get(chunk.document_id)
                items_to_upsert.append({
                    "chunk_id": chunk.id,
                    "text": chunk.text,
                    "embedding": emb,
                    "user_id": doc.user_id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "page": chunk.page_number or 1,
                    "filename": doc.filename,
                })

            vector_store.upsert(items_to_upsert)
            indexed_count += len(items_to_upsert)
            offset += batch_size
            logger.info(f"Indexed {indexed_count}/{total_chunks} chunks ({indexed_count * 100 // total_chunks}%)")

        final_count = vector_store.count()
        logger.info(f"Reindexing complete! Total chunks in Chroma: {final_count} (expected: {total_chunks})")

        if final_count != total_chunks:
            logger.error(f"Mismatch: Chroma has {final_count} chunks but MySQL has {total_chunks}!")
            return 1

        logger.info("SUCCESS: Vector store perfectly synchronized with MySQL chunks.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Reindex Chroma vector store from MySQL chunks table.")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for embeddings and upsert.")
    parser.add_argument("--storage-path", type=str, default=None, help="Custom Chroma persist directory.")
    args = parser.parse_args()

    sys.exit(reindex(batch_size=args.batch_size, chroma_path=args.storage_path))


if __name__ == "__main__":
    main()
