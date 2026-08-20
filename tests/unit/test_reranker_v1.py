from __future__ import annotations

from medical_rag.reranking import HybridRerankerIndex, build_reranker_passage
from medical_rag.retrieval.models import HybridSearchHit, HybridSearchResponse


def _hit(rank: int, chunk_id: str, text: str, *, section: str = "血压分类") -> HybridSearchHit:
    return HybridSearchHit(
        rank=rank,
        score=1.0 / (60 + rank),
        chunk_id=chunk_id,
        document_id="doc",
        source_file="guide.pdf",
        content_type="narrative",
        section=section,
        section_path=[section],
        page_start=10,
        page_end=10,
        text=text,
        dense_rank=rank,
        dense_score=0.5,
        bm25_rank=rank,
        bm25_score=1.0,
    )


class StubHybridIndex:
    def __init__(self) -> None:
        self.hits = [
            _hit(1, "c1", "高血压患者应限制钠盐摄入。"),
            _hit(2, "c2", "2级高血压舒张压为100~109 mmHg。"),
            _hit(3, "c3", "家庭血压诊断标准为135/85 mmHg。"),
        ]

    def search(self, query: str, *, top_k: int = 5) -> HybridSearchResponse:
        return HybridSearchResponse(
            query=query,
            top_k=top_k,
            candidate_k=50,
            rrf_k=60,
            hits=self.hits[:top_k],
        )


class FakeReranker:
    model_name = "fake-reranker"
    device = "cpu"

    def score(self, query: str, documents) -> list[float]:
        assert "2级高血压舒张压" in query
        # Promote the second RRF candidate to rank 1.
        return [0.1, 0.95, 0.2][: len(documents)]


def test_reranker_can_promote_a_lower_rrf_candidate() -> None:
    index = HybridRerankerIndex(
        hybrid_index=StubHybridIndex(),  # type: ignore[arg-type]
        reranker=FakeReranker(),
        rerank_k=3,
    )
    response = index.search("2级高血压舒张压是多少？", top_k=2)

    assert response.hits[0].chunk_id == "c2"
    assert response.hits[0].pre_rerank_rank == 2
    assert response.hits[0].rank == 1
    assert response.hits[0].reranker_score == 0.95
    assert response.candidate_k == 50
    assert response.reranker_model == "fake-reranker"


def test_build_reranker_passage_preserves_section_context() -> None:
    hit = _hit(1, "c1", "收缩压≥140且舒张压<90。", section="4.5.1 按血压水平分类和分级")
    passage = build_reranker_passage(hit)
    assert "章节：4.5.1 按血压水平分类和分级" in passage
    assert "收缩压≥140" in passage
