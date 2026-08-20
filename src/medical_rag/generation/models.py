from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from medical_rag.rag.context import CitationValidationResult, RAGContext
from medical_rag.rag.prompt import RAGPrompt


class LLMUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMRawResponse(BaseModel):
    provider: str = "openai_compatible"
    model: str
    answer: str
    finish_reason: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    response_id: str | None = None


class GroundingCheck(BaseModel):
    status: Literal[
        "passed",
        "no_evidence",
        "missing_citation",
        "unknown_citation",
    ]
    passed: bool
    reason: str


class RAGGenerationResult(BaseModel):
    query: str
    answer: str
    model: str
    provider: str
    llm_called: bool
    context: RAGContext
    prompt: RAGPrompt
    citation_validation: CitationValidationResult
    grounding_check: GroundingCheck
    finish_reason: str | None = None
    usage: LLMUsage = Field(default_factory=LLMUsage)
    response_id: str | None = None
