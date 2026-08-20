from __future__ import annotations

import json
import re
from collections.abc import Iterable

from medical_rag.evaluation.generation_models import (
    ClaimGroundingJudgment,
    ExpectedFactJudgment,
    GenerationEvalCaseResult,
    GenerationEvalReport,
    GroundingEvaluationResult,
    SemanticGroundingJudgment,
    SemanticGroundingMetrics,
)
from medical_rag.generation.models import LLMRawResponse, RAGGenerationResult
from medical_rag.rag.prompt import RAGPrompt


_JUDGE_SYSTEM_PROMPT = """你是医疗RAG评测器。你不是医疗问答助手，而是严格的证据审计员。

你只能依据：
1. 用户问题；
2. 人工标注的 expected_facts；
3. 本次RAG检索上下文中的 [S1]、[S2]...；
4. 待评测答案。

禁止使用外部医学知识补全、纠正或猜测。

任务：
A. 从答案中提取有实际医学含义的事实性 claim。寒暄、格式标题、纯连接词不要算 claim。
B. 对每个 claim 检查它实际引用的 [Sx] 是否支持该 claim：
   - supported：claim 的关键事实被至少一个实际引用的证据直接支持；
   - unsupported：有引用，但引用证据与 claim 矛盾，或没有支持 claim 的关键部分；
   - uncited：claim 是医学事实，但没有引用任何 [Sx]；
   - unclear：证据本身截断、歧义或不足，无法判断。
C. 检查 expected_facts 是否被答案正确覆盖。仅仅数字出现不代表覆盖，必须保留对象、条件和关系。
D. 给出 answer_verdict：
   - correct：expected_facts 全部被正确覆盖，且没有实质性错误；
   - partially_correct：覆盖部分 expected_facts，但有遗漏，且没有颠覆性错误；
   - incorrect：存在关键错误、矛盾或答案没有回答问题；
   - unanswerable：提供的证据不足以判断 expected_facts，而答案明确拒答或无法回答。

特别注意：引用编号“存在”不等于语义支持。必须检查 claim 与对应引用证据的内容关系。

只输出一个 JSON 对象，不要 Markdown，不要代码块，不要额外解释。JSON schema：
{
  "answer_verdict": "correct|partially_correct|incorrect|unanswerable",
  "claims": [
    {
      "claim": "答案中的一个事实性断言",
      "citation_ids": ["S1"],
      "verdict": "supported|unsupported|uncited|unclear",
      "reason": "简短原因"
    }
  ],
  "expected_fact_checks": [
    {
      "expected_fact": "与输入 expected_facts 中对应的原文保持一致",
      "covered": true,
      "reason": "简短原因"
    }
  ],
  "overall_reason": "一句话总结"
}"""


class JudgeClientProtocol:
    provider_name: str

    def generate(self, prompt: RAGPrompt) -> LLMRawResponse: ...


def _strip_code_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    return value.strip()


def _extract_json_object(text: str) -> str:
    value = _strip_code_fence(text)
    try:
        json.loads(value)
        return value
    except json.JSONDecodeError:
        pass

    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        candidate = value[start : end + 1]
        json.loads(candidate)
        return candidate
    raise ValueError("judge response does not contain a valid JSON object")


def _normalize_expected_fact_checks(
    judgment: SemanticGroundingJudgment,
    expected_facts: list[str],
) -> SemanticGroundingJudgment:
    """Make expected-fact scoring deterministic even if the judge omits a row.

    Matching is primarily by the exact expected_fact string required by the prompt.
    Missing expected facts are conservatively counted as not covered. Extra rows are
    discarded so the denominator always equals the manually authored evaluation set.
    """

    by_fact = {item.expected_fact.strip(): item for item in judgment.expected_fact_checks}
    normalized: list[ExpectedFactJudgment] = []
    for fact in expected_facts:
        matched = by_fact.get(fact.strip())
        if matched is None:
            normalized.append(
                ExpectedFactJudgment(
                    expected_fact=fact,
                    covered=False,
                    reason="Judge output omitted this expected fact; counted as not covered.",
                )
            )
        else:
            normalized.append(
                ExpectedFactJudgment(
                    expected_fact=fact,
                    covered=matched.covered,
                    reason=matched.reason,
                )
            )
    return judgment.model_copy(update={"expected_fact_checks": normalized})


def compute_semantic_metrics(
    judgment: SemanticGroundingJudgment,
    expected_facts: list[str],
) -> SemanticGroundingMetrics:
    claims = judgment.claims
    supported = sum(item.verdict == "supported" for item in claims)
    unsupported = sum(item.verdict == "unsupported" for item in claims)
    uncited = sum(item.verdict == "uncited" for item in claims)
    unclear = sum(item.verdict == "unclear" for item in claims)
    claim_count = len(claims)

    faithfulness = None
    if claim_count:
        faithfulness = round(supported / claim_count, 6)

    checks = judgment.expected_fact_checks
    covered = sum(item.covered for item in checks)
    fact_count = len(expected_facts)
    coverage = None
    if fact_count:
        coverage = round(covered / fact_count, 6)

    fully_grounded = claim_count > 0 and supported == claim_count
    answer_correct = judgment.answer_verdict == "correct" and (
        coverage == 1.0 if fact_count else True
    )

    return SemanticGroundingMetrics(
        factual_claim_count=claim_count,
        supported_claim_count=supported,
        unsupported_claim_count=unsupported,
        uncited_claim_count=uncited,
        unclear_claim_count=unclear,
        faithfulness_score=faithfulness,
        expected_fact_count=fact_count,
        covered_expected_fact_count=covered,
        expected_fact_coverage=coverage,
        fully_grounded=fully_grounded,
        answer_correct=answer_correct,
    )


class EvidenceGroundingJudge:
    """LLM-as-judge for claim-to-evidence support and expected-fact coverage.

    This is a semantic evaluation layer, not a replacement for deterministic
    citation validation. The final report keeps both signals separate.
    """

    def __init__(self, client: JudgeClientProtocol) -> None:
        self.client = client

    def build_prompt(
        self,
        generation: RAGGenerationResult,
        expected_facts: list[str],
    ) -> RAGPrompt:
        facts_json = json.dumps(expected_facts, ensure_ascii=False, indent=2)
        user_prompt = (
            f"用户问题：\n{generation.query}\n\n"
            f"expected_facts：\n{facts_json}\n\n"
            f"检索上下文：\n{generation.context.context_text or '（无检索证据）'}\n\n"
            f"待评测答案：\n{generation.answer}\n\n"
            "请严格按照 system 中的 JSON schema 输出评测结果。"
        )
        return RAGPrompt(system_prompt=_JUDGE_SYSTEM_PROMPT, user_prompt=user_prompt)

    def judge(
        self,
        generation: RAGGenerationResult,
        expected_facts: list[str],
    ) -> GroundingEvaluationResult:
        prompt = self.build_prompt(generation, expected_facts)
        raw = self.client.generate(prompt)
        payload = _extract_json_object(raw.answer)
        judgment = SemanticGroundingJudgment.model_validate_json(payload)
        judgment = _normalize_expected_fact_checks(judgment, expected_facts)
        metrics = compute_semantic_metrics(judgment, expected_facts)
        return GroundingEvaluationResult(
            judgment=judgment,
            metrics=metrics,
            judge_provider=raw.provider,
            judge_model=raw.model,
            judge_raw_answer=raw.answer,
        )


def case_overall_passed(
    generation: RAGGenerationResult,
    semantic: GroundingEvaluationResult,
) -> bool:
    return bool(
        generation.grounding_check.passed
        and generation.citation_validation.valid
        and semantic.metrics.answer_correct
        and semantic.metrics.fully_grounded
    )


def _mean(values: Iterable[float | None]) -> float | None:
    actual = [value for value in values if value is not None]
    if not actual:
        return None
    return round(sum(actual) / len(actual), 6)


def build_generation_eval_report(
    *,
    suite_name: str,
    suite_version: str,
    expected_query_count: int,
    generation_model: str,
    judge_model: str,
    context_top_k: int,
    max_context_chars: int,
    candidate_k: int,
    rerank_k: int,
    rrf_k: int,
    results: list[GenerationEvalCaseResult],
) -> GenerationEvalReport:
    completed = [item for item in results if item.error is None and item.generation and item.semantic_grounding]
    errors = [item for item in results if item.error is not None]
    count = len(completed)

    def rate(predicate) -> float | None:
        if not count:
            return None
        return round(sum(bool(predicate(item)) for item in completed) / count, 6)

    total_prompt = sum((item.generation.usage.prompt_tokens or 0) for item in completed if item.generation)
    total_completion = sum((item.generation.usage.completion_tokens or 0) for item in completed if item.generation)
    total_tokens = sum((item.generation.usage.total_tokens or 0) for item in completed if item.generation)

    return GenerationEvalReport(
        suite_name=suite_name,
        suite_version=suite_version,
        query_count=expected_query_count,
        completed_count=count,
        error_count=len(errors),
        generation_model=generation_model,
        judge_model=judge_model,
        context_top_k=context_top_k,
        max_context_chars=max_context_chars,
        candidate_k=candidate_k,
        rerank_k=rerank_k,
        rrf_k=rrf_k,
        structural_citation_pass_rate=rate(lambda item: item.structural_citation_passed),
        answer_correct_rate=rate(
            lambda item: item.semantic_grounding.metrics.answer_correct  # type: ignore[union-attr]
        ),
        answer_at_least_partial_rate=rate(
            lambda item: item.semantic_grounding.judgment.answer_verdict in {"correct", "partially_correct"}  # type: ignore[union-attr]
        ),
        fully_grounded_rate=rate(
            lambda item: item.semantic_grounding.metrics.fully_grounded  # type: ignore[union-attr]
        ),
        overall_pass_rate=rate(lambda item: item.overall_passed),
        mean_faithfulness_score=_mean(
            item.semantic_grounding.metrics.faithfulness_score  # type: ignore[union-attr]
            for item in completed
        ),
        mean_expected_fact_coverage=_mean(
            item.semantic_grounding.metrics.expected_fact_coverage  # type: ignore[union-attr]
            for item in completed
        ),
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_generation_tokens=total_tokens,
        avg_generation_tokens_per_completed_case=(round(total_tokens / count, 3) if count else None),
        results=results,
    )


def generation_report_markdown(report: GenerationEvalReport) -> str:
    def pct(value: float | None) -> str:
        return "N/A" if value is None else f"{value * 100:.2f}%"

    lines = [
        "# End-to-End RAG Generation Evaluation V1",
        "",
        f"- suite: {report.suite_name} ({report.suite_version})",
        f"- generation_model: {report.generation_model}",
        f"- judge_model: {report.judge_model}",
        f"- query_count: {report.query_count}",
        f"- completed_count: {report.completed_count}",
        f"- error_count: {report.error_count}",
        f"- context_top_k: {report.context_top_k}",
        f"- max_context_chars: {report.max_context_chars}",
        f"- candidate_k: {report.candidate_k}",
        f"- rerank_k: {report.rerank_k}",
        f"- rrf_k: {report.rrf_k}",
        "",
        "## Aggregate metrics",
        "",
        f"- structural_citation_pass_rate: {pct(report.structural_citation_pass_rate)}",
        f"- answer_correct_rate: {pct(report.answer_correct_rate)}",
        f"- answer_at_least_partial_rate: {pct(report.answer_at_least_partial_rate)}",
        f"- fully_grounded_rate: {pct(report.fully_grounded_rate)}",
        f"- overall_pass_rate: {pct(report.overall_pass_rate)}",
        f"- mean_faithfulness_score: {pct(report.mean_faithfulness_score)}",
        f"- mean_expected_fact_coverage: {pct(report.mean_expected_fact_coverage)}",
        f"- total_generation_tokens: {report.total_generation_tokens}",
        f"- avg_generation_tokens_per_completed_case: {report.avg_generation_tokens_per_completed_case}",
        "",
        "## Per-case",
        "",
    ]
    for item in report.results:
        lines.append(f"### {item.id}")
        lines.append("")
        lines.append(f"- query: {item.query}")
        if item.error:
            lines.append(f"- ERROR: {item.error}")
            lines.append("")
            continue
        semantic = item.semantic_grounding
        generation = item.generation
        assert semantic is not None and generation is not None
        lines.extend(
            [
                f"- answer_verdict: {semantic.judgment.answer_verdict}",
                f"- structural_citation_passed: {item.structural_citation_passed}",
                f"- faithfulness_score: {semantic.metrics.faithfulness_score}",
                f"- expected_fact_coverage: {semantic.metrics.expected_fact_coverage}",
                f"- fully_grounded: {semantic.metrics.fully_grounded}",
                f"- overall_passed: {item.overall_passed}",
                f"- cited_ids: {generation.citation_validation.cited_ids}",
                f"- elapsed_seconds: {item.elapsed_seconds}",
                "",
                "**Answer**",
                "",
                generation.answer,
                "",
                "**Claim audit**",
                "",
            ]
        )
        for claim in semantic.judgment.claims:
            lines.append(
                f"- [{claim.verdict}] {claim.claim} | citations={claim.citation_ids} | {claim.reason}"
            )
        lines.extend(["", "**Expected facts**", ""])
        for fact in semantic.judgment.expected_fact_checks:
            lines.append(f"- [{'OK' if fact.covered else 'MISS'}] {fact.expected_fact} | {fact.reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
