from __future__ import annotations

from fastapi.testclient import TestClient

from medical_rag.api.app import app
from medical_rag.core.config import Settings
from medical_rag.generation import GroundedAnswerGenerator, LLMRawResponse, LLMUsage
from medical_rag.rag.context import ContextBuilderConfig, RAGContextBuilder
from medical_rag.rag.pipeline import MedicalRAGPipeline, RAGRequest
from medical_rag.rag.prompt import DEFAULT_GROUNDED_SYSTEM_PROMPT
from medical_rag.retrieval.models import RerankedHybridSearchHit, RerankedHybridSearchResponse


class FakeRetriever:
    def search(self, query: str, *, top_k: int = 5) -> RerankedHybridSearchResponse:
        hit = RerankedHybridSearchHit(
            rank=1,
            score=8.0,
            chunk_id="c1",
            document_id="d1",
            source_file="guide.pdf",
            content_type="narrative",
            section="血压分级",
            section_path=["血压分级"],
            page_start=10,
            page_end=10,
            text="2级高血压收缩压160~179 mmHg和/或舒张压100~109 mmHg。",
            reranker_score=8.0,
            pre_rerank_rank=1,
            rrf_score=0.03,
            dense_rank=1,
            dense_score=0.9,
            bm25_rank=1,
            bm25_score=10.0,
        )
        return RerankedHybridSearchResponse(
            query=query,
            top_k=top_k,
            candidate_k=50,
            rrf_k=60,
            rerank_k=20,
            reranker_model="fake-reranker",
            reranker_device="cpu",
            hits=[hit],
        )


class FakeLLM:
    provider_name = "fake"

    def generate(self, prompt):
        return LLMRawResponse(
            provider="fake",
            model="fake-llm",
            answer="2级高血压收缩压为160~179 mmHg，和/或舒张压为100~109 mmHg。[S1]",
            usage=LLMUsage(prompt_tokens=100, completion_tokens=30, total_tokens=130),
        )


class FakePipelineForAPI:
    async def run(self, request: RAGRequest):
        settings = Settings(
            rag_dense_backend="local",
            rag_context_top_k=5,
            medical_rag_llm_base_url="http://example/v1",
            medical_rag_llm_model="fake",
        )
        pipeline = MedicalRAGPipeline(
            settings=settings,
            retriever=FakeRetriever(),
            context_builder=RAGContextBuilder(ContextBuilderConfig(top_k=5, max_context_chars=6000)),
            generator=GroundedAnswerGenerator(FakeLLM()),
            embedding_model_name="fake-embed",
            reranker_model_name="fake-reranker",
        )
        return pipeline.ask(request)


def test_product_prompt_has_evidence_bounded_safety_rule():
    assert "停药后果" in DEFAULT_GROUNDED_SYSTEM_PROMPT
    assert "模型自身医学知识" in DEFAULT_GROUNDED_SYSTEM_PROMPT
    assert "证据能够支持的层级" in DEFAULT_GROUNDED_SYSTEM_PROMPT


def test_product_pipeline_returns_answer_sources_and_diagnostics():
    settings = Settings(
        rag_dense_backend="local",
        rag_context_top_k=5,
        medical_rag_llm_base_url="http://example/v1",
        medical_rag_llm_model="fake",
    )
    pipeline = MedicalRAGPipeline(
        settings=settings,
        retriever=FakeRetriever(),
        context_builder=RAGContextBuilder(ContextBuilderConfig(top_k=5, max_context_chars=6000)),
        generator=GroundedAnswerGenerator(FakeLLM()),
        embedding_model_name="fake-embed",
        reranker_model_name="fake-reranker",
    )

    result = pipeline.ask("2级高血压范围是多少？")

    assert result.abstained is False
    assert result.sources[0].citation_id == "S1"
    assert result.sources[0].used_in_answer is True
    assert result.diagnostics.grounding_passed is True
    assert result.diagnostics.total_tokens == 130
    assert result.diagnostics.dense_backend == "local"


def test_product_api_ask_endpoint_returns_pipeline_result(monkeypatch):
    import medical_rag.api.routes.rag as rag_route

    monkeypatch.setattr(rag_route, "get_pipeline", lambda: FakePipelineForAPI())
    client = TestClient(app)
    response = client.post(
        "/api/v1/rag/ask",
        headers={"Authorization": "Bearer medical-rag-doctor-session"},
        json={"question": "2级高血压范围是多少？"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"][0]["citation_id"] == "S1"
    assert payload["diagnostics"]["grounding_passed"] is True


def test_demo_page_is_available_without_frontend_build():
    client = TestClient(app)
    response = client.get("/rag-demo")
    assert response.status_code == 200
    assert "医疗知识库问答 V1.0" in response.text


def test_health_exposes_rag_runtime_state():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "1.1.0"
    assert "rag" in payload
    assert "dense_backend" in payload["rag"]
