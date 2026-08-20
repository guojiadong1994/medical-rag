from __future__ import annotations

from medical_rag.reranking.base import TextReranker
from medical_rag.retrieval.hybrid import ReciprocalRankFusionIndex
from medical_rag.retrieval.models import (
    HybridSearchHit,
    RerankedHybridSearchHit,
    RerankedHybridSearchResponse,
)


def build_reranker_passage(hit: HybridSearchHit) -> str:
    """Build a compact passage that preserves the most useful structural context."""

    parts: list[str] = []
    if hit.section:
        parts.append(f"章节：{hit.section}")
    if hit.table_title:
        parts.append(f"表格：{hit.table_title}")
    parts.append(hit.text)
    return "\n\n".join(parts)


class HybridRerankerIndex:
    """RRF first-stage retrieval followed by a pairwise neural reranker."""

    def __init__(
        self,
        *,
        hybrid_index: ReciprocalRankFusionIndex,
        reranker: TextReranker,
        rerank_k: int = 20,
    ) -> None:
        if rerank_k <= 0:
            raise ValueError("rerank_k must be positive")
        self.hybrid_index = hybrid_index
        self.reranker = reranker
        self.rerank_k = rerank_k

    def search(self, query: str, *, top_k: int = 5) -> RerankedHybridSearchResponse:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        first_stage_k = max(top_k, self.rerank_k)
        first_stage = self.hybrid_index.search(query, top_k=first_stage_k)
        candidates = first_stage.hits[: self.rerank_k]
        passages = [build_reranker_passage(hit) for hit in candidates]
        rerank_scores = self.reranker.score(query, passages)

        ranked = sorted(
            zip(candidates, rerank_scores, strict=True),
            key=lambda item: (-item[1], item[0].rank, item[0].chunk_id),
        )[:top_k]

        hits: list[RerankedHybridSearchHit] = []
        for rank, (source, reranker_score) in enumerate(ranked, start=1):
            hits.append(
                RerankedHybridSearchHit(
                    rank=rank,
                    score=round(float(reranker_score), 8),
                    chunk_id=source.chunk_id,
                    document_id=source.document_id,
                    source_file=source.source_file,
                    content_type=source.content_type,
                    section=source.section,
                    section_path=list(source.section_path),
                    page_start=source.page_start,
                    page_end=source.page_end,
                    text=source.text,
                    table_title=source.table_title,
                    table_no=source.table_no,
                    reranker_score=round(float(reranker_score), 8),
                    pre_rerank_rank=source.rank,
                    rrf_score=source.score,
                    dense_rank=source.dense_rank,
                    dense_score=source.dense_score,
                    bm25_rank=source.bm25_rank,
                    bm25_score=source.bm25_score,
                )
            )

        return RerankedHybridSearchResponse(
            query=query,
            top_k=top_k,
            candidate_k=first_stage.candidate_k,
            rrf_k=first_stage.rrf_k,
            rerank_k=self.rerank_k,
            reranker_model=self.reranker.model_name,
            reranker_device=self.reranker.device,
            hits=hits,
        )
