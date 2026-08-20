from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from medical_rag.evaluation.generation_models import (
    ClaimGroundingJudgment,
    ExpectedFactJudgment,
)
from medical_rag.generation.models import LLMUsage, RAGGenerationResult


ChallengeCategory = Literal[
    "answerable",
    "unanswerable",
    "ambiguous",
    "apparent_conflict",
    "patient_specific_safety",
]

ExpectedResponseType = Literal[
    "answer",
    "abstain",
    "conditional",
    "safe_boundary",
]

ResponseBehavior = Literal[
    "answered",
    "abstained",
    "conditional",
    "safe_boundary",
    "unsafe_personalized_advice",
]

AnswerVerdictV3 = Literal[
    "correct",
    "partially_correct",
    "incorrect",
    "unanswerable",
]


class GenerationChallengeCase(BaseModel):
    id: str
    query: str
    category: ChallengeCategory
    expected_response_type: ExpectedResponseType
    expected_facts: list[str] = Field(default_factory=list)
    required_behaviors: list[str] = Field(default_factory=list)
    forbidden_behaviors: list[str] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="after")
    def validate_case(self) -> "GenerationChallengeCase":
        if self.category == "unanswerable" and self.expected_response_type != "abstain":
            raise ValueError("unanswerable cases must expect abstain")
        if self.category == "patient_specific_safety" and self.expected_response_type != "safe_boundary":
            raise ValueError("patient_specific_safety cases must expect safe_boundary")
        if self.category in {"ambiguous", "apparent_conflict"} and self.expected_response_type != "conditional":
            raise ValueError("ambiguous/apparent_conflict cases must expect conditional")
        return self


class GenerationChallengeSuite(BaseModel):
    name: str
    version: str = "v3"
    description: str = ""
    policy: str = ""
    cases: list[GenerationChallengeCase] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "GenerationChallengeSuite":
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("challenge case ids must be unique")
        return self


class RequiredBehaviorJudgment(BaseModel):
    requirement: str
    met: bool
    reason: str = ""


class ForbiddenBehaviorJudgment(BaseModel):
    forbidden_behavior: str
    violated: bool
    reason: str = ""


class GenerationPolicyJudgment(BaseModel):
    answer_verdict: AnswerVerdictV3
    response_behavior: ResponseBehavior
    claims: list[ClaimGroundingJudgment] = Field(default_factory=list)
    expected_fact_checks: list[ExpectedFactJudgment] = Field(default_factory=list)
    required_behavior_checks: list[RequiredBehaviorJudgment] = Field(default_factory=list)
    forbidden_behavior_checks: list[ForbiddenBehaviorJudgment] = Field(default_factory=list)
    unsafe_advice: bool = False
    overall_reason: str = ""


class GenerationPolicyMetrics(BaseModel):
    factual_claim_count: int
    supported_claim_count: int
    unsupported_claim_count: int
    uncited_claim_count: int
    unclear_claim_count: int
    faithfulness_score: float | None = None
    fully_grounded: bool

    expected_fact_count: int
    covered_expected_fact_count: int
    expected_fact_coverage: float | None = None

    required_behavior_count: int
    required_behavior_met_count: int
    forbidden_behavior_count: int
    forbidden_behavior_violation_count: int

    behavior_passed: bool
    answer_correct: bool
    false_refusal: bool
    false_answer: bool
    unsafe_advice: bool


class PolicyGroundingEvaluationResult(BaseModel):
    judgment: GenerationPolicyJudgment
    metrics: GenerationPolicyMetrics
    judge_provider: str
    judge_model: str
    judge_raw_answer: str
    judge_usage: LLMUsage = Field(default_factory=LLMUsage)


class GenerationSafetyCaseResult(BaseModel):
    id: str
    query: str
    category: ChallengeCategory
    expected_response_type: ExpectedResponseType
    expected_facts: list[str] = Field(default_factory=list)
    required_behaviors: list[str] = Field(default_factory=list)
    forbidden_behaviors: list[str] = Field(default_factory=list)
    generation: RAGGenerationResult | None = None
    policy_grounding: PolicyGroundingEvaluationResult | None = None
    structural_unknown_citation_free: bool = False
    overall_passed: bool = False
    elapsed_seconds: float | None = None
    error: str | None = None


class GenerationSafetyEvalReport(BaseModel):
    suite_name: str
    suite_version: str
    evaluator_version: str = "generation_safety_v3"
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

    overall_pass_rate: float | None = None
    structural_unknown_citation_free_rate: float | None = None
    mean_faithfulness_score: float | None = None
    mean_expected_fact_coverage: float | None = None

    answerable_answer_accuracy: float | None = None
    answerable_false_refusal_rate: float | None = None
    unanswerable_abstention_accuracy: float | None = None
    unanswerable_false_answer_rate: float | None = None
    ambiguous_handling_rate: float | None = None
    apparent_conflict_resolution_rate: float | None = None
    patient_specific_safety_rate: float | None = None
    unsafe_advice_rate: float | None = None
    category_pass_rates: dict[str, float | None] = Field(default_factory=dict)

    total_generation_tokens: int = 0
    total_judge_tokens: int = 0
    total_tokens: int = 0
    avg_total_tokens_per_completed_case: float | None = None

    results: list[GenerationSafetyCaseResult] = Field(default_factory=list)
