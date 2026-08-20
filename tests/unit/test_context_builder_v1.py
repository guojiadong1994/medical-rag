from __future__ import annotations

from medical_rag.rag import (
    ContextBuilderConfig,
    GroundedPromptBuilder,
    RAGContextBuilder,
    validate_answer_citations,
)
from medical_rag.retrieval.models import RerankedHybridSearchHit, RerankedHybridSearchResponse


def _hit(rank: int, chunk_id: str, text: str, *, page: int = 10) -> RerankedHybridSearchHit:
    return RerankedHybridSearchHit(
        rank=rank,
        score=5.0 - rank,
        chunk_id=chunk_id,
        document_id="doc",
        source_file="guide.pdf",
        content_type="narrative",
        section="4.5.1 按血压水平分类和分级",
        section_path=["要点4", "4.5.1 按血压水平分类和分级"],
        page_start=page,
        page_end=page,
        text=text,
        reranker_score=5.0 - rank,
        pre_rerank_rank=rank + 1,
        rrf_score=0.03,
        dense_rank=rank,
        dense_score=0.7,
        bm25_rank=rank + 2,
        bm25_score=1.2,
    )


def _response(*hits: RerankedHybridSearchHit) -> RerankedHybridSearchResponse:
    return RerankedHybridSearchResponse(
        query="2级高血压的范围是多少？",
        top_k=len(hits),
        candidate_k=50,
        rrf_k=60,
        rerank_k=20,
        reranker_model="fake",
        reranker_device="cpu",
        hits=list(hits),
    )


def test_context_builder_assigns_stable_citations_in_rank_order() -> None:
    context = RAGContextBuilder(ContextBuilderConfig(top_k=2, max_context_chars=2000)).build(
        _response(
            _hit(1, "c1", "2级高血压收缩压160~179 mmHg。"),
            _hit(2, "c2", "2级高血压舒张压100~109 mmHg。", page=11),
        )
    )
    assert context.citation_ids == ["S1", "S2"]
    assert "[S1]" in context.context_text
    assert "[S2]" in context.context_text
    assert "guide.pdf" in context.context_text
    assert context.sources[0].citation.retrieval_rank == 1


def test_context_builder_skips_exact_duplicate_text() -> None:
    text = "家庭血压≥135/85 mmHg可诊断高血压。"
    context = RAGContextBuilder(ContextBuilderConfig(top_k=3, max_context_chars=2000)).build(
        _response(_hit(1, "c1", text), _hit(2, "c2", "  家庭血压≥135/85 mmHg可诊断高血压。  "))
    )
    assert context.selected_source_count == 1
    assert context.exact_duplicate_skipped == 1
    assert context.citation_ids == ["S1"]


def test_context_builder_enforces_budget_and_records_truncation() -> None:
    context = RAGContextBuilder(
        ContextBuilderConfig(top_k=1, max_context_chars=360, min_truncated_text_chars=50)
    ).build(_response(_hit(1, "c1", "高血压证据。" * 100)))
    assert context.used_context_chars <= 360
    assert context.truncated_source_count == 1
    assert context.sources[0].truncated is True
    assert "上下文预算截断" in context.context_text


def test_prompt_requires_grounding_and_citations() -> None:
    context = RAGContextBuilder(ContextBuilderConfig(top_k=1, max_context_chars=2000)).build(
        _response(_hit(1, "c1", "诊室血压≥140/90 mmHg可诊断高血压。"))
    )
    prompt = GroundedPromptBuilder().build(context)
    assert "只使用给定证据" in prompt.system_prompt
    assert "[S1]" in prompt.user_prompt
    assert context.query in prompt.user_prompt


def test_validate_answer_citations_rejects_unknown_source_id() -> None:
    context = RAGContextBuilder(ContextBuilderConfig(top_k=1, max_context_chars=2000)).build(
        _response(_hit(1, "c1", "夜间血压≥120/70 mmHg。"))
    )
    ok = validate_answer_citations("夜间血压阈值为120/70 mmHg。[S1]", context)
    bad = validate_answer_citations("夜间血压阈值为120/70 mmHg。[S9]", context)
    assert ok.valid is True
    assert ok.cited_ids == ["S1"]
    assert bad.valid is False
    assert bad.unknown_ids == ["S9"]
