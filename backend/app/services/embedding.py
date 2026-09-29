from __future__ import annotations

from typing import Any, Optional


class EmbeddingService:
    _instance: Optional["EmbeddingService"] = None
    _model: Optional[tuple[str, Any]] = None

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
    def model(self) -> tuple[str, Any]:
        if self._model is None:
            try:
                # FastEmbed: CPU-optimized ONNX runtime, NO PyTorch (~30MB vs ~2GB)
                from fastembed import TextEmbedding  # noqa: PLC0415

                self._model = ("fastembed", TextEmbedding(model_name=self.model_name))
            except ImportError:
                # Fallback to SentenceTransformer if installed
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415

                self._model = ("sentence_transformers", SentenceTransformer(self.model_name))
        return self._model

    def embed(self, texts: list[str], batch_size: int = 64) -> list[list[float]]:
        if not texts:
            return []
        model_type, model_obj = self.model
        if model_type == "fastembed":
            # fastembed yields numpy arrays; convert to float lists
            raw = list(model_obj.embed(texts, batch_size=batch_size))
            return [vec.tolist() for vec in raw]
        else:
            embeddings = model_obj.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embeddings.tolist()


