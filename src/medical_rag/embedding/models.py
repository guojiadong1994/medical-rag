from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkEmbeddingRef(BaseModel):
    """Links one embedding row to the exact chunk text that produced it."""

    chunk_id: str
    text_sha256: str


class EmbeddingManifest(BaseModel):
    """Metadata required to safely reuse a dense embedding matrix."""

    document_id: str
    source_file: str
    model_name: str
    dimension: int
    normalized: bool = True
    dtype: str = "float32"
    chunk_count: int
    refs: list[ChunkEmbeddingRef] = Field(default_factory=list)


class EmbeddingReport(BaseModel):
    """Diagnostics emitted after embedding generation."""

    document_id: str
    source_file: str
    model_name: str
    device: str
    chunk_count: int
    dimension: int
    normalized: bool
    dtype: str
    finite: bool
    empty_embedding_text_count: int
    norm_min: float
    norm_mean: float
    norm_max: float
    elapsed_seconds: float
    batch_size: int
    max_seq_length: int | None = None
