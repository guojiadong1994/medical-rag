from __future__ import annotations

from collections.abc import Sequence

import numpy as np


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


class SentenceTransformerEmbedder:
    """Dense embedder backed by sentence-transformers.

    The dependency is imported lazily so the rest of the project can still be
    imported when the optional ``embedding`` dependencies have not been installed.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        *,
        device: str | None = None,
        batch_size: int = 8,
        normalize_embeddings: bool = True,
        max_seq_length: int | None = 2048,
        show_progress_bar: bool = True,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_seq_length is not None and max_seq_length <= 0:
            raise ValueError("max_seq_length must be positive or None")

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on optional package
            raise RuntimeError(
                "sentence-transformers is not installed. "
                'Run: pip install -e ".[dev,embedding]"'
            ) from exc

        self._model_name = model_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.max_seq_length = max_seq_length
        self.show_progress_bar = show_progress_bar

        # device=None lets SentenceTransformers choose CUDA/MPS/CPU automatically.
        self._model = SentenceTransformer(model_name, device=device)
        if max_seq_length is not None:
            self._model.max_seq_length = max_seq_length

        get_dimension = getattr(self._model, "get_embedding_dimension", None)
        if get_dimension is None:
            get_dimension = self._model.get_sentence_embedding_dimension
        dimension = get_dimension()
        if dimension is None:
            probe = self._model.encode(
                ["dimension probe"],
                batch_size=1,
                convert_to_numpy=True,
                normalize_embeddings=normalize_embeddings,
                show_progress_bar=False,
            )
            dimension = int(np.asarray(probe).shape[1])
        self._dimension = int(dimension)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def device(self) -> str:
        return str(getattr(self._model, "device", "unknown"))

    def encode_documents(self, texts: Sequence[str]) -> np.ndarray:
        clean = self._validate_texts(texts)
        if not clean:
            return np.empty((0, self.dimension), dtype=np.float32)

        # encode_document / encode_query are preferred for retrieval in modern
        # SentenceTransformers. Fall back to encode for older compatible versions.
        method = getattr(self._model, "encode_document", self._model.encode)
        vectors = method(
            clean,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=self.show_progress_bar,
        )
        return self._ensure_matrix(vectors)

    def encode_query(self, text: str) -> np.ndarray:
        clean = text.strip()
        if not clean:
            raise ValueError("query text must not be empty")

        method = getattr(self._model, "encode_query", self._model.encode)
        vectors = method(
            [clean],
            batch_size=1,
            convert_to_numpy=True,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        matrix = self._ensure_matrix(vectors)
        return matrix[0]

    @staticmethod
    def _validate_texts(texts: Sequence[str]) -> list[str]:
        clean: list[str] = []
        for index, text in enumerate(texts):
            value = text.strip()
            if not value:
                raise ValueError(f"embedding text at index {index} is empty")
            clean.append(value)
        return clean

    def _ensure_matrix(self, vectors: object) -> np.ndarray:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2:
            raise ValueError(f"expected a 2-D embedding matrix, got shape={matrix.shape}")
        if matrix.shape[1] != self.dimension:
            raise ValueError(
                f"embedding dimension mismatch: expected {self.dimension}, got {matrix.shape[1]}"
            )
        if not np.isfinite(matrix).all():
            raise ValueError("embedding matrix contains NaN or infinity")
        if self.normalize_embeddings:
            # Re-normalize in float32. This makes cosine similarity equal to a
            # simple inner product and removes small backend-specific drift.
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            if np.any(norms <= 0):
                raise ValueError("embedding matrix contains zero-norm vectors")
            matrix = matrix / norms
        return np.ascontiguousarray(matrix, dtype=np.float32)
