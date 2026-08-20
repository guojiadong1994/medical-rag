from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from medical_rag.generation.models import RAGGenerationResult


ClaimVerdict = Literal["supported", "unsupported", "uncited", "unclear"]
AnswerVerdict = Literal["correct", "partially_correct", "incorrect", "unanswerable"]


class ClaimGroundingJudgment(BaseModel):
    claim: str
    citation_ids: list[str] = Field(default_factory=list)
    verdict: ClaimVerdict
    reason: str = ""


class ExpectedFactJudgment(BaseModel):
    expected_fact: str
    covered: bool
    reason: str = ""


class SemanticGroundingJudgment(BaseModel):
    """Semantic judge output for one generated answer.

    The judge is constrained to the retrieved context and the manually-authored
    expected facts. It is not allowed to repair missing evidence with outside
    medical knowledge.
    """

    answer_verdict: AnswerVerdict
    claims: list[ClaimGroundingJudgment] = Field(default_factory=list)
    expected_fact_checks: list[ExpectedFactJudgment] = Field(default_factory=list)
    overall_reason: str = ""


class SemanticGroundingMetrics(BaseModel):
    factual_claim_count: int
    supported_claim_count: int
    unsupported_claim_count: int
    uncited_claim_count: int
    unclear_claim_count: int
    faithfulness_score: float | None = None
    expected_fact_count: int
    covered_expected_fact_count: int
    expected_fact_coverage: float | None = None
    fully_grounded: bool
    answer_correct: bool


class GroundingEvaluationResult(BaseModel):
    judgment: SemanticGroundingJudgment
    metrics: SemanticGroundingMetrics
    judge_provider: str
    judge_model: str
    judge_raw_answer: str


class GenerationEvalCaseResult(BaseModel):
    id: str
    query: str
    expected_facts: list[str] = Field(default_factory=list)
    generation: RAGGenerationResult | None = None
    semantic_grounding: GroundingEvaluationResult | None = None
    structural_citation_passed: bool = False
    overall_passed: bool = False
    elapsed_seconds: float | None = None
    error: str | None = None


class GenerationEvalReport(BaseModel):
    suite_name: str
    suite_version: str
    evaluator_version: str = "generation_grounding_v1"
    query_count: int
    completed_count: int
    error_count: int
    generation_model: str
    judge_model: str
    context_top_k: int
    max_context_chars: int
    candidate_k: int
    rerank_k: int
    rrf_k: int

    structural_citation_pass_rate: float | None = None
    answer_correct_rate: float | None = None
    answer_at_least_partial_rate: float | None = None
    fully_grounded_rate: float | None = None
    overall_pass_rate: float | None = None
    mean_faithfulness_score: float | None = None
    mean_expected_fact_coverage: float | None = None

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_generation_tokens: int = 0
    avg_generation_tokens_per_completed_case: float | None = None

    results: list[GenerationEvalCaseResult] = Field(default_factory=list)
