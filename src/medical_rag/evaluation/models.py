from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceRule(BaseModel):
    """One acceptable evidence pattern for a retrieval-evaluation case.

    A hit is relevant when it satisfies every non-empty field in this rule.
    A case may contain multiple rules; matching any one of them counts as relevant.
    """

    page_ranges: list[tuple[int, int]] = Field(default_factory=list)
    section_contains_any: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    any_keywords: list[str] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)


class RetrievalEvalCase(BaseModel):
    id: str
    query: str
    evidence_rules: list[EvidenceRule] = Field(default_factory=list)
    note: str = ""


class RetrievalEvalSuite(BaseModel):
    name: str
    description: str = ""
    cases: list[RetrievalEvalCase] = Field(default_factory=list)


class RetrievalEvalHit(BaseModel):
    rank: int
    score: float
    chunk_id: str
    page_start: int
    page_end: int
    section: str | None = None
    content_type: str
    table_title: str | None = None
    text_preview: str = ""
    relevant: bool


class RetrievalEvalCaseResult(BaseModel):
    id: str
    query: str
    first_relevant_rank: int | None = None
    reciprocal_rank: float = 0.0
    hits: list[RetrievalEvalHit] = Field(default_factory=list)


class RetrievalEvalReport(BaseModel):
    suite_name: str
    # Backward compatible defaults allow V1.1/V1.2 reports to still be loaded by the
    # error-analysis script.
    retriever_name: str = "dense"
    model_name: str = ""
    query_count: int
    top_k: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    no_relevant_in_top_k: int
    results: list[RetrievalEvalCaseResult] = Field(default_factory=list)
