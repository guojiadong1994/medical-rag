from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class KeywordProximityRule(BaseModel):
    """Require several keywords to occur within a compact character window.

    The evaluator normalizes whitespace and Unicode before checking the window, so
    ``24 h`` and ``24h`` behave consistently. This is useful for evidence-level
    relevance where merely having two facts somewhere in a long chunk is not enough.
    """

    keywords: list[str] = Field(default_factory=list)
    max_chars: int = 80

    @model_validator(mode="after")
    def validate_rule(self) -> "KeywordProximityRule":
        if len(self.keywords) < 2:
            raise ValueError("proximity rule requires at least two keywords")
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")
        return self


class EvidenceRule(BaseModel):
    """One acceptable evidence pattern for a retrieval-evaluation case.

    Evaluation V2 is evidence-level and multi-positive: a case may contain multiple
    acceptable rules, and matching *any* rule counts as relevant. Rules can describe
    narrative evidence, table evidence, alternative guideline sections, or repeated
    definitions without hard-coding unstable chunk IDs.
    """

    rule_id: str = ""
    description: str = ""

    page_ranges: list[tuple[int, int]] = Field(default_factory=list)
    section_contains_any: list[str] = Field(default_factory=list)
    table_title_contains_any: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    any_keywords: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(default_factory=list)
    proximity_groups: list[KeywordProximityRule] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)


class RetrievalEvalCase(BaseModel):
    id: str
    query: str
    expected_facts: list[str] = Field(default_factory=list)
    evidence_rules: list[EvidenceRule] = Field(default_factory=list)
    note: str = ""


class RetrievalEvalSuite(BaseModel):
    name: str
    description: str = ""
    version: str = "v1"
    labeling_policy: str = ""
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
    matched_rule_ids: list[str] = Field(default_factory=list)


class RetrievalEvalCaseResult(BaseModel):
    id: str
    query: str
    first_relevant_rank: int | None = None
    reciprocal_rank: float = 0.0
    relevant_hit_count: int = 0
    hits: list[RetrievalEvalHit] = Field(default_factory=list)


class RetrievalEvalReport(BaseModel):
    suite_name: str
    suite_version: str = "v1"
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
