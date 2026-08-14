from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ChunkContentType = Literal["narrative", "table"]


class DocumentChunk(BaseModel):
    """A retrieval-ready semantic unit produced from one cleaned document."""

    chunk_id: str
    document_id: str
    source_file: str
    content_type: ChunkContentType

    section: str | None = None
    section_path: list[str] = Field(default_factory=list)

    page_start: int
    page_end: int

    text: str
    embedding_text: str
    char_count: int

    table_title: str | None = None
    table_no: int | None = None

    metadata: dict[str, str] = Field(default_factory=dict)


class ChunkedDocument(BaseModel):
    """Container for all chunks generated from one source document."""

    document_id: str
    source_file: str
    chunks: list[DocumentChunk] = Field(default_factory=list)
