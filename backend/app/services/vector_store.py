from typing import Any, Optional


class VectorStore:
    def __init__(
        self,
        persist_dir: str = "./storage/chroma",
        collection_name: str = "doc_chunks",
        api_key: Optional[str] = None,
        tenant: Optional[str] = None,
        database: Optional[str] = None,
    ):
        import os
        import chromadb  # noqa: PLC0415
        from chromadb.config import Settings as ChromaSettings  # noqa: PLC0415
        from flask import current_app  # noqa: PLC0415

        self.persist_dir = persist_dir
        self.collection_name = collection_name

        resolved_api_key = api_key
        resolved_tenant = tenant
        resolved_database = database

        if current_app:
            settings = current_app.config.get("DOCCHAT_SETTINGS")
            if settings:
                resolved_api_key = resolved_api_key or getattr(settings, "CHROMA_API_KEY", "")
                resolved_tenant = resolved_tenant or getattr(settings, "CHROMA_TENANT", "")
                resolved_database = resolved_database or getattr(settings, "CHROMA_DATABASE", "")
            else:
                resolved_api_key = resolved_api_key or current_app.config.get("CHROMA_API_KEY", "")
                resolved_tenant = resolved_tenant or current_app.config.get("CHROMA_TENANT", "")
                resolved_database = resolved_database or current_app.config.get("CHROMA_DATABASE", "")

        resolved_api_key = (resolved_api_key or os.environ.get("CHROMA_API_KEY", "")).strip()
        resolved_tenant = (resolved_tenant or os.environ.get("CHROMA_TENANT", "")).strip()
        resolved_database = (resolved_database or os.environ.get("CHROMA_DATABASE", "Docchat")).strip()

        if resolved_api_key and resolved_tenant:
            self.client = chromadb.CloudClient(
                api_key=resolved_api_key,
                tenant=resolved_tenant,
                database=resolved_database or "Docchat",
            )
        else:
            self.client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: list[dict[str, Any]]) -> None:
        """
        Upsert chunks into ChromaDB.
        Each chunk item should have:
        - chunk_id: int or str
        - text: str
        - embedding: list[float]
        - user_id: int
        - document_id: int
        - chunk_index: int
        - page: int
        - filename: str
        """
        if not chunks:
            return

        ids = [str(c["chunk_id"]) for c in chunks]
        embeddings = [c["embedding"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "user_id": int(c["user_id"]),
                "document_id": int(c["document_id"]),
                "chunk_index": int(c["chunk_index"]),
                "page": int(c.get("page") or 1),
                "filename": str(c["filename"]),
            }
            for c in chunks
        ]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        embedding: list[float],
        user_id: int,
        top_k: int = 5,
        document_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Query nearest chunks strictly isolated by user_id.
        Raises ValueError if user_id is omitted or invalid.
        """
        if not user_id:
            raise ValueError("user_id is required for query isolation")

        if document_id is not None:
            where_filter = {
                "$and": [
                    {"user_id": int(user_id)},
                    {"document_id": int(document_id)},
                ]
            }
        else:
            where_filter = {"user_id": int(user_id)}

        # Perform query in Chroma
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        output: list[dict[str, Any]] = []
        if not results or not results["ids"] or not results["ids"][0]:
            return output

        ids = results["ids"][0]
        docs = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        for i in range(len(ids)):
            meta = metas[i] if i < len(metas) else {}
            output.append(
                {
                    "chunk_id": int(ids[i]),
                    "document_id": meta.get("document_id"),
                    "chunk_index": meta.get("chunk_index"),
                    "page": meta.get("page"),
                    "filename": meta.get("filename"),
                    "text": docs[i] if i < len(docs) else "",
                    "distance": float(distances[i]) if i < len(distances) else 0.0,
                }
            )

        return output

    def delete_document(self, document_id: int) -> None:
        """
        Delete all chunks associated with a document_id.
        """
        self.collection.delete(where={"document_id": int(document_id)})

    def count(self, user_id: Optional[int] = None) -> int:
        """
        Count vectors in the collection.
        If user_id is specified, returns count of chunks for that user.
        """
        if user_id is None:
            return self.collection.count()
        matched = self.collection.get(where={"user_id": int(user_id)}, include=[])
        return len(matched["ids"]) if matched and "ids" in matched else 0

    def close(self) -> None:
        """
        Stop Chroma background components and release resources.
        """
        try:
            if hasattr(self.client, "close"):
                self.client.close()
        except Exception:
            pass
