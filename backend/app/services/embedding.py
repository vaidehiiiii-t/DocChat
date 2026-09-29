from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingService:
    _instance: Optional["EmbeddingService"] = None
    _model: Optional["SentenceTransformer"] = None

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name

    @classmethod
    def get_instance(
        cls, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = cls(model_name=model_name)
        return cls._instance

    @property
    def model(self) -> "SentenceTransformer":
        if self._model is None:
            # Lazy import: torch/sentence_transformers load only on first
            # embedding request, NOT at Flask startup. Fixes OOM on free tier.
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

