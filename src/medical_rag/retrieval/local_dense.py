from __future__ import annotations

from pathlib import Path

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.base import TextEmbedder
from medical_rag.embedding.io import (
    load_chunks,
    load_embedding_matrix,
    load_manifest,
    validate_chunks_against_manifest,
)
from medical_rag.embedding.models import EmbeddingManifest
from medical_rag.retrieval.models import DenseSearchHit, DenseSearchResponse


class LocalDenseIndex:
    """Small local dense index used to verify embedding quality before Milvus."""

    def __init__(
        self,
        *,
        chunks: list[DocumentChunk],
        embeddings: np.ndarray,
        manifest: EmbeddingManifest,
    ) -> None:
        validate_chunks_against_manifest(chunks, manifest)
        matrix = np.asarray(embeddings, dtype=np.float32)
        expected = (manifest.chunk_count, manifest.dimension)
        if matrix.shape != expected:
            raise ValueError(f"expected embedding matrix {expected}, got {matrix.shape}")
        if not np.isfinite(matrix).all():
            raise ValueError("embedding matrix contains NaN or infinity")

        self.chunks = chunks
        self.embeddings = np.ascontiguousarray(matrix)
        self.manifest = manifest

    @classmethod
    def load(
        cls,
        *,
        chunks_path: Path,
        embeddings_path: Path,
        manifest_path: Path,
    ) -> "LocalDenseIndex":
        chunks = load_chunks(chunks_path)
        manifest = load_manifest(manifest_path)
        validate_chunks_against_manifest(chunks, manifest)
        embeddings = load_embedding_matrix(embeddings_path, manifest)
        return cls(chunks=chunks, embeddings=embeddings, manifest=manifest)

    def search(
        self,
        query: str,
        *,
        embedder: TextEmbedder,
        top_k: int = 5,
    ) -> DenseSearchResponse:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not self.chunks:
            return DenseSearchResponse(
                query=query,
                model_name=self.manifest.model_name,
                top_k=top_k,
                hits=[],
            )
        if embedder.model_name != self.manifest.model_name:
            raise ValueError(
                "query model does not match document embedding model: "
                f"{embedder.model_name!r} != {self.manifest.model_name!r}"
            )
        if embedder.dimension != self.manifest.dimension:
            raise ValueError(
                "query embedding dimension does not match index: "
                f"{embedder.dimension} != {self.manifest.dimension}"
            )

        query_vector = np.asarray(embedder.encode_query(query), dtype=np.float32)
        if query_vector.shape != (self.manifest.dimension,):
            raise ValueError(
                f"expected query vector shape {(self.manifest.dimension,)}, got {query_vector.shape}"
            )
        if not np.isfinite(query_vector).all():
            raise ValueError("query vector contains NaN or infinity")

        # The embedding pipeline stores L2-normalized vectors, therefore dot
        # product is cosine similarity. This is also the form we can later map
        # directly to an IP/COSINE-style vector index in Milvus.
        if self.manifest.normalized:
            norm = float(np.linalg.norm(query_vector))
            if norm <= 0:
                raise ValueError("query vector has zero norm")
            query_vector = query_vector / norm

        scores = self.embeddings @ query_vector
        count = min(top_k, len(self.chunks))
        if count == len(self.chunks):
            candidate_indices = np.arange(len(self.chunks))
        else:
            candidate_indices = np.argpartition(scores, -count)[-count:]
        ordered = candidate_indices[np.argsort(scores[candidate_indices])[::-1]]

        hits: list[DenseSearchHit] = []
        for rank, index in enumerate(ordered, start=1):
            chunk = self.chunks[int(index)]
            hits.append(
                DenseSearchHit(
                    rank=rank,
                    score=round(float(scores[int(index)]), 6),
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_file=chunk.source_file,
                    content_type=chunk.content_type,
                    section=chunk.section,
                    section_path=list(chunk.section_path),
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    text=chunk.text,
                    table_title=chunk.table_title,
                    table_no=chunk.table_no,
                )
            )

        return DenseSearchResponse(
            query=query,
            model_name=self.manifest.model_name,
            top_k=top_k,
            hits=hits,
        )
