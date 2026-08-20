from __future__ import annotations

from typing import Protocol

from medical_rag.generation.models import (
    GroundingCheck,
    LLMRawResponse,
    LLMUsage,
    RAGGenerationResult,
)
from medical_rag.rag import GroundedPromptBuilder, RAGContext, validate_answer_citations
from medical_rag.rag.prompt import RAGPrompt


INSUFFICIENT_EVIDENCE_ANSWER = "现有检索证据不足以回答该问题。"


class ChatGenerator(Protocol):
    provider_name: str

    def generate(self, prompt: RAGPrompt) -> LLMRawResponse: ...


class GroundedAnswerGenerator:
    """Generate an answer from a bounded RAG context and validate citation syntax.

    This V1 performs structural grounding checks only. It can verify that the
    answer cites existing source IDs, but it does not yet prove that each claim is
    semantically entailed by the cited evidence.
    """

    def __init__(
        self,
        client: ChatGenerator,
        *,
        prompt_builder: GroundedPromptBuilder | None = None,
    ) -> None:
        self.client = client
        self.prompt_builder = prompt_builder or GroundedPromptBuilder()

    def generate(self, context: RAGContext) -> RAGGenerationResult:
        prompt = self.prompt_builder.build(context)

        if not context.sources:
            validation = validate_answer_citations(INSUFFICIENT_EVIDENCE_ANSWER, context)
            return RAGGenerationResult(
                query=context.query,
                answer=INSUFFICIENT_EVIDENCE_ANSWER,
                model="not_called",
                provider=self.client.provider_name,
                llm_called=False,
                context=context,
                prompt=prompt,
                citation_validation=validation,
                grounding_check=GroundingCheck(
                    status="no_evidence",
                    passed=True,
                    reason="No context sources were available, so generation abstained without calling the LLM.",
                ),
                usage=LLMUsage(),
            )

        raw = self.client.generate(prompt)
        validation = validate_answer_citations(raw.answer, context)
        grounding = _check_structural_grounding(validation, has_sources=True)

        return RAGGenerationResult(
            query=context.query,
            answer=raw.answer,
            model=raw.model,
            provider=raw.provider,
            llm_called=True,
            context=context,
            prompt=prompt,
            citation_validation=validation,
            grounding_check=grounding,
            finish_reason=raw.finish_reason,
            usage=raw.usage,
            response_id=raw.response_id,
        )


def _check_structural_grounding(validation, *, has_sources: bool) -> GroundingCheck:
    if not has_sources:
        return GroundingCheck(
            status="no_evidence",
            passed=True,
            reason="No evidence was provided.",
        )
    if validation.unknown_ids:
        return GroundingCheck(
            status="unknown_citation",
            passed=False,
            reason=f"Answer cited unknown source IDs: {', '.join(validation.unknown_ids)}",
        )
    if not validation.cited_ids:
        return GroundingCheck(
            status="missing_citation",
            passed=False,
            reason="Evidence was available but the answer contained no [Sx] citation.",
        )
    return GroundingCheck(
        status="passed",
        passed=True,
        reason="All cited source IDs exist in the supplied RAG context.",
    )
