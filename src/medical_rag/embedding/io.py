from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.models import ChunkEmbeddingRef, EmbeddingManifest


def load_chunks(path: Path) -> list[DocumentChunk]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"expected chunks.json to contain a list, got {type(payload).__name__}")
    return [DocumentChunk.model_validate(item) for item in payload]


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_refs(chunks: list[DocumentChunk]) -> list[ChunkEmbeddingRef]:
    return [
        ChunkEmbeddingRef(chunk_id=chunk.chunk_id, text_sha256=text_sha256(chunk.embedding_text))
        for chunk in chunks
    ]


def validate_chunks_against_manifest(
    chunks: list[DocumentChunk],
    manifest: EmbeddingManifest,
) -> None:
    if len(chunks) != manifest.chunk_count:
        raise ValueError(
            "chunks.json no longer matches embeddings: "
            f"manifest has {manifest.chunk_count} rows but chunks.json has {len(chunks)} chunks. "
            "Regenerate embeddings."
        )
    if len(manifest.refs) != manifest.chunk_count:
        raise ValueError("embedding manifest is incomplete")

    for index, (chunk, ref) in enumerate(zip(chunks, manifest.refs, strict=True)):
        if chunk.chunk_id != ref.chunk_id:
            raise ValueError(
                f"chunk id mismatch at row {index}: {chunk.chunk_id!r} != {ref.chunk_id!r}. "
                "Regenerate embeddings."
            )
        digest = text_sha256(chunk.embedding_text)
        if digest != ref.text_sha256:
            raise ValueError(
                f"embedding_text changed for {chunk.chunk_id}. Regenerate embeddings before search."
            )


def load_manifest(path: Path) -> EmbeddingManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EmbeddingManifest.model_validate(payload)


def load_embedding_matrix(path: Path, manifest: EmbeddingManifest) -> np.ndarray:
    matrix = np.load(path, allow_pickle=False)
    matrix = np.asarray(matrix, dtype=np.float32)
    expected = (manifest.chunk_count, manifest.dimension)
    if matrix.shape != expected:
        raise ValueError(f"embedding matrix shape mismatch: expected {expected}, got {matrix.shape}")
    if not np.isfinite(matrix).all():
        raise ValueError("embedding matrix contains NaN or infinity")
    return np.ascontiguousarray(matrix)
