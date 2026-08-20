from __future__ import annotations

import json

import httpx

from medical_rag.generation import (
    GroundedAnswerGenerator,
    LLMRawResponse,
    LLMUsage,
    OpenAICompatibleChatClient,
    OpenAICompatibleConfig,
)
from medical_rag.rag import ContextBuilderConfig, RAGContextBuilder
from medical_rag.retrieval.models import RerankedHybridSearchHit, RerankedHybridSearchResponse


def _context(with_hits: bool = True):
    hits = []
    if with_hits:
        hits.append(
            RerankedHybridSearchHit(
                rank=1,
                score=3.2,
                chunk_id="c1",
                document_id="d1",
                source_file="guide.pdf",
                content_type="table",
                section="4.5.1",
                section_path=["4", "4.5", "4.5.1"],
                page_start=10,
                page_end=10,
                text="2级高血压 160~179 和/或 100~109 mmHg",
                table_title="表6",
                reranker_score=3.2,
                pre_rerank_rank=4,
                rrf_score=0.03,
                dense_rank=5,
                dense_score=0.7,
                bm25_rank=1,
                bm25_score=9.0,
            )
        )
    response = RerankedHybridSearchResponse(
        query="2级高血压范围？",
        top_k=5,
        candidate_k=50,
        rrf_k=60,
        rerank_k=20,
        reranker_model="fake",
        reranker_device="cpu",
        hits=hits,
    )
    return RAGContextBuilder(ContextBuilderConfig(top_k=5, max_context_chars=6000)).build(response)


class FakeClient:
    provider_name = "fake"

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = 0

    def generate(self, prompt):
        self.calls += 1
        return LLMRawResponse(
            provider="fake",
            model="fake-model",
            answer=self.answer,
            usage=LLMUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120),
        )


def test_generation_with_valid_citation_passes():
    client = FakeClient("2级高血压为160~179/100~109 mmHg。[S1]")
    result = GroundedAnswerGenerator(client).generate(_context())
    assert result.llm_called is True
    assert result.grounding_check.passed is True
    assert result.citation_validation.cited_ids == ["S1"]
    assert client.calls == 1


def test_generation_with_unknown_citation_fails_structural_grounding():
    client = FakeClient("答案。[S9]")
    result = GroundedAnswerGenerator(client).generate(_context())
    assert result.grounding_check.status == "unknown_citation"
    assert result.grounding_check.passed is False
    assert result.citation_validation.unknown_ids == ["S9"]


def test_generation_without_citation_fails_when_evidence_exists():
    client = FakeClient("2级高血压为160~179/100~109 mmHg。")
    result = GroundedAnswerGenerator(client).generate(_context())
    assert result.grounding_check.status == "missing_citation"
    assert result.grounding_check.passed is False


def test_no_evidence_abstains_without_llm_call():
    client = FakeClient("should not be used")
    result = GroundedAnswerGenerator(client).generate(_context(with_hits=False))
    assert result.llm_called is False
    assert result.answer == "现有检索证据不足以回答该问题。"
    assert result.grounding_check.status == "no_evidence"
    assert client.calls == 0


def test_openai_compatible_client_builds_request_and_parses_response():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "test-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "答案。[S1]"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 8,
                    "total_tokens": 58,
                },
            },
        )

    config = OpenAICompatibleConfig(
        base_url="http://example.test/v1",
        model="test-model",
        api_key="secret",
    )
    client = OpenAICompatibleChatClient(config, transport=httpx.MockTransport(handler))
    from medical_rag.rag.prompt import RAGPrompt

    result = client.generate(RAGPrompt(system_prompt="system", user_prompt="user"))
    assert seen["url"] == "http://example.test/v1/chat/completions"
    assert seen["auth"] == "Bearer secret"
    assert seen["payload"]["temperature"] == 0.0
    assert result.answer == "答案。[S1]"
    assert result.usage.total_tokens == 58
