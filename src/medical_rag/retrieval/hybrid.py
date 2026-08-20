from __future__ import annotations

from collections import defaultdict

from medical_rag.embedding.base import TextEmbedder
from medical_rag.retrieval.bm25 import LocalBM25Index
from medical_rag.retrieval.local_dense import LocalDenseIndex
from medical_rag.retrieval.models import HybridSearchHit, HybridSearchResponse, SearchHit


class ReciprocalRankFusionIndex:
    """Fuse dense and BM25 rankings with Reciprocal Rank Fusion (RRF).

    RRF intentionally uses ranks rather than raw scores. Dense cosine scores and BM25
    scores live on unrelated scales, so directly adding them is poorly calibrated.
    With RRF, a chunk receives ``weight / (rrf_k + rank)`` from each retrieval channel.
    A chunk returned by both channels is therefore naturally promoted.
    """

    def __init__(
        self,
        *,
        dense_index: LocalDenseIndex,
        bm25_index: LocalBM25Index,
        embedder: TextEmbedder,
        candidate_k: int = 30,
        rrf_k: int = 60,
        dense_weight: float = 1.0,
        bm25_weight: float = 1.0,
    ) -> None:
        if candidate_k <= 0:
            raise ValueError("candidate_k must be positive")
        if rrf_k <= 0:
            raise ValueError("rrf_k must be positive")
        if dense_weight <= 0 or bm25_weight <= 0:
            raise ValueError("fusion weights must be positive")
        if [chunk.chunk_id for chunk in dense_index.chunks] != [
            chunk.chunk_id for chunk in bm25_index.chunks
        ]:
            raise ValueError("dense and BM25 indexes must be built from the same chunks")

        self.dense_index = dense_index
        self.bm25_index = bm25_index
        self.embedder = embedder
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight

    def search(self, query: str, *, top_k: int = 5) -> HybridSearchResponse:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        candidate_k = max(top_k, self.candidate_k)
        dense = self.dense_index.search(
            query,
            embedder=self.embedder,
            top_k=candidate_k,
        )
        sparse = self.bm25_index.search(query, top_k=candidate_k)

        fused_scores: dict[str, float] = defaultdict(float)
        hit_by_id: dict[str, SearchHit] = {}
        dense_meta: dict[str, tuple[int, float]] = {}
        bm25_meta: dict[str, tuple[int, float]] = {}

        for hit in dense.hits:
            hit_by_id[hit.chunk_id] = hit
            dense_meta[hit.chunk_id] = (hit.rank, hit.score)
            fused_scores[hit.chunk_id] += self.dense_weight / (self.rrf_k + hit.rank)

        for hit in sparse.hits:
            hit_by_id.setdefault(hit.chunk_id, hit)
            bm25_meta[hit.chunk_id] = (hit.rank, hit.score)
            fused_scores[hit.chunk_id] += self.bm25_weight / (self.rrf_k + hit.rank)

        ordered_ids = sorted(
            fused_scores,
            key=lambda chunk_id: (
                -fused_scores[chunk_id],
                dense_meta.get(chunk_id, (10**9, 0.0))[0],
                bm25_meta.get(chunk_id, (10**9, 0.0))[0],
                chunk_id,
            ),
        )[:top_k]

        hits: list[HybridSearchHit] = []
        for rank, chunk_id in enumerate(ordered_ids, start=1):
            source = hit_by_id[chunk_id]
            dense_rank, dense_score = dense_meta.get(chunk_id, (None, None))
            bm25_rank, bm25_score = bm25_meta.get(chunk_id, (None, None))
            hits.append(
                HybridSearchHit(
                    rank=rank,
                    score=round(fused_scores[chunk_id], 8),
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
                    dense_rank=dense_rank,
                    dense_score=dense_score,
                    bm25_rank=bm25_rank,
                    bm25_score=bm25_score,
                )
            )

        return HybridSearchResponse(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=self.rrf_k,
            hits=hits,
        )
