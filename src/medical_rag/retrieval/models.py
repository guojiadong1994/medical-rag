from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from medical_rag.chunking.models import ChunkContentType


RetrievalMethod = Literal["dense", "bm25", "hybrid_rrf", "hybrid_rerank"]


class SearchHit(BaseModel):
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
    retrieval_method: RetrievalMethod


class DenseSearchHit(SearchHit):
    retrieval_method: Literal["dense"] = "dense"


class BM25SearchHit(SearchHit):
    retrieval_method: Literal["bm25"] = "bm25"


class HybridSearchHit(SearchHit):
    retrieval_method: Literal["hybrid_rrf"] = "hybrid_rrf"
    dense_rank: int | None = None
    dense_score: float | None = None
    bm25_rank: int | None = None
    bm25_score: float | None = None


class RerankedHybridSearchHit(SearchHit):
    retrieval_method: Literal["hybrid_rerank"] = "hybrid_rerank"
    reranker_score: float
    pre_rerank_rank: int
    rrf_score: float
    dense_rank: int | None = None
    dense_score: float | None = None
    bm25_rank: int | None = None
    bm25_score: float | None = None


class DenseSearchResponse(BaseModel):
    query: str
    model_name: str
    top_k: int
    hits: list[DenseSearchHit] = Field(default_factory=list)


class BM25SearchResponse(BaseModel):
    query: str
    tokenizer_name: str
    top_k: int
    hits: list[BM25SearchHit] = Field(default_factory=list)


class HybridSearchResponse(BaseModel):
    query: str
    method: Literal["hybrid_rrf"] = "hybrid_rrf"
    top_k: int
    candidate_k: int
    rrf_k: int
    hits: list[HybridSearchHit] = Field(default_factory=list)


class RerankedHybridSearchResponse(BaseModel):
    query: str
    method: Literal["hybrid_rerank"] = "hybrid_rerank"
    top_k: int
    candidate_k: int
    rrf_k: int
    rerank_k: int
    reranker_model: str
    reranker_device: str
    hits: list[RerankedHybridSearchHit] = Field(default_factory=list)
