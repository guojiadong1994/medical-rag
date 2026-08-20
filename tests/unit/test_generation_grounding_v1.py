from __future__ import annotations

import json

from medical_rag.evaluation import (
    EvidenceGroundingJudge,
    build_generation_eval_report,
    case_overall_passed,
)
from medical_rag.evaluation.generation_models import GenerationEvalCaseResult
from medical_rag.generation import GroundedAnswerGenerator, LLMRawResponse
from medical_rag.rag import ContextBuilderConfig, RAGContextBuilder
from medical_rag.retrieval.models import RerankedHybridSearchHit, RerankedHybridSearchResponse


def _context():
    hit = RerankedHybridSearchHit(
        rank=1,
        score=3.0,
        chunk_id="c1",
        document_id="d1",
        source_file="guide.pdf",
        content_type="table",
        section="4.5.1",
        section_path=["4.5.1"],
        page_start=10,
        page_end=10,
        text="2级高血压(中度) 160~179 和/或 100~109 mmHg",
        table_title="表6",
        reranker_score=3.0,
        pre_rerank_rank=2,
        rrf_score=0.03,
        dense_rank=3,
        dense_score=0.7,
        bm25_rank=1,
        bm25_score=8.0,
    )
    response = RerankedHybridSearchResponse(
        query="2级高血压的收缩压和舒张压范围是多少？",
        top_k=5,
        candidate_k=50,
        rrf_k=60,
        rerank_k=20,
        reranker_model="fake",
        reranker_device="cpu",
        hits=[hit],
    )
    return RAGContextBuilder(ContextBuilderConfig()).build(response)


class FakeClient:
    provider_name = "fake"

    def __init__(self, answer: str, model: str = "fake-model"):
        self.answer = answer
        self.model = model

    def generate(self, prompt):
        return LLMRawResponse(provider="fake", model=self.model, answer=self.answer)


def _generation(answer: str):
    return GroundedAnswerGenerator(FakeClient(answer)).generate(_context())


def test_supported_claim_and_all_expected_facts_pass():
    generation = _generation("2级高血压收缩压160~179 mmHg，舒张压100~109 mmHg。[S1]")
    judge_payload = {
        "answer_verdict": "correct",
        "claims": [
            {
                "claim": "2级高血压收缩压160~179 mmHg，舒张压100~109 mmHg",
                "citation_ids": ["S1"],
                "verdict": "supported",
                "reason": "S1直接给出范围",
            }
        ],
        "expected_fact_checks": [
            {"expected_fact": "收缩压160~179 mmHg", "covered": True, "reason": "已回答"},
            {"expected_fact": "舒张压100~109 mmHg", "covered": True, "reason": "已回答"},
        ],
        "overall_reason": "完整且有证据",
    }
    result = EvidenceGroundingJudge(FakeClient(json.dumps(judge_payload, ensure_ascii=False), "judge")).judge(
        generation, ["收缩压160~179 mmHg", "舒张压100~109 mmHg"]
    )
    assert result.metrics.faithfulness_score == 1.0
    assert result.metrics.expected_fact_coverage == 1.0
    assert result.metrics.fully_grounded is True
    assert result.metrics.answer_correct is True
    assert case_overall_passed(generation, result) is True


def test_valid_citation_but_wrong_claim_fails_semantic_grounding():
    generation = _generation("2级高血压为≥180/110 mmHg。[S1]")
    payload = {
        "answer_verdict": "incorrect",
        "claims": [
            {
                "claim": "2级高血压为≥180/110 mmHg",
                "citation_ids": ["S1"],
                "verdict": "unsupported",
                "reason": "S1给出的是160~179/100~109",
            }
        ],
        "expected_fact_checks": [
            {"expected_fact": "收缩压160~179 mmHg", "covered": False, "reason": "回答错误"}
        ],
        "overall_reason": "引用存在但不支持答案",
    }
    result = EvidenceGroundingJudge(FakeClient(json.dumps(payload, ensure_ascii=False))).judge(
        generation, ["收缩压160~179 mmHg"]
    )
    assert generation.grounding_check.passed is True  # V1 structural check alone would pass.
    assert result.metrics.faithfulness_score == 0.0
    assert result.metrics.fully_grounded is False
    assert result.metrics.answer_correct is False
    assert case_overall_passed(generation, result) is False


def test_uncited_claim_is_not_faithful():
    generation = _generation("2级高血压为160~179/100~109 mmHg。[S1]")
    payload = {
        "answer_verdict": "correct",
        "claims": [
            {"claim": "范围正确", "citation_ids": [], "verdict": "uncited", "reason": "没有绑定来源"}
        ],
        "expected_fact_checks": [
            {"expected_fact": "范围", "covered": True, "reason": "内容出现"}
        ],
        "overall_reason": "内容正确但claim未引用",
    }
    result = EvidenceGroundingJudge(FakeClient(json.dumps(payload, ensure_ascii=False))).judge(generation, ["范围"])
    assert result.metrics.uncited_claim_count == 1
    assert result.metrics.faithfulness_score == 0.0
    assert result.metrics.fully_grounded is False


def test_judge_parser_accepts_json_code_fence():
    generation = _generation("答案。[S1]")
    payload = {
        "answer_verdict": "partially_correct",
        "claims": [],
        "expected_fact_checks": [],
        "overall_reason": "test",
    }
    result = EvidenceGroundingJudge(FakeClient("```json\n" + json.dumps(payload) + "\n```")) .judge(
        generation, ["fact-a"]
    )
    assert result.judgment.expected_fact_checks[0].expected_fact == "fact-a"
    assert result.judgment.expected_fact_checks[0].covered is False


def test_aggregate_report_separates_structural_and_semantic_metrics():
    generation = _generation("答案。[S1]")
    payload = {
        "answer_verdict": "correct",
        "claims": [
            {"claim": "fact", "citation_ids": ["S1"], "verdict": "supported", "reason": "ok"}
        ],
        "expected_fact_checks": [
            {"expected_fact": "fact", "covered": True, "reason": "ok"}
        ],
        "overall_reason": "ok",
    }
    semantic = EvidenceGroundingJudge(FakeClient(json.dumps(payload))).judge(generation, ["fact"])
    item = GenerationEvalCaseResult(
        id="q1",
        query="q",
        expected_facts=["fact"],
        generation=generation,
        semantic_grounding=semantic,
        structural_citation_passed=True,
        overall_passed=True,
    )
    report = build_generation_eval_report(
        suite_name="suite",
        suite_version="v2",
        expected_query_count=1,
        generation_model="gen",
        judge_model="judge",
        context_top_k=5,
        max_context_chars=6000,
        candidate_k=50,
        rerank_k=20,
        rrf_k=60,
        results=[item],
    )
    assert report.structural_citation_pass_rate == 1.0
    assert report.answer_correct_rate == 1.0
    assert report.fully_grounded_rate == 1.0
    assert report.overall_pass_rate == 1.0
