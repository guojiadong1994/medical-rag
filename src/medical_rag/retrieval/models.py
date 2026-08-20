from __future__ import annotations

from pydantic import BaseModel, Field

from medical_rag.chunking.models import ChunkContentType


class DenseSearchHit(BaseModel):
    rank: int
    score: float
    chunk_id: str
    document_id: str
    source_file: str
    content_type: ChunkContentType
    section: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_start: int
    page_end: int
    text: str
    table_title: str | None = None
    table_no: int | None = None


class DenseSearchResponse(BaseModel):
    query: str
    model_name: str
    top_k: int
    hits: list[DenseSearchHit] = Field(default_factory=list)
