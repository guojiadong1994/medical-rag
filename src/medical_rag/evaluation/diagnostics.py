from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from medical_rag.chunking.models import DocumentChunk
from medical_rag.embedding.base import TextEmbedder
from medical_rag.evaluation.models import RetrievalEvalCase, RetrievalEvalSuite
from medical_rag.evaluation.retrieval import is_relevant
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex
from medical_rag.retrieval.models import SearchHit


@dataclass(slots=True)
class MethodEvidenceRank:
    method: str
    first_relevant_rank: int | None
    score: float | None
    chunk_id: str | None


@dataclass(slots=True)
class RecallDiagnosis:
    case_id: str
    query: str
    category: str
    explanation: str
    recommendation: str
    evidence_chunk_count: int
    evidence_chunk_ids: list[str]
    operational_hybrid_rank: int | None
    dense: MethodEvidenceRank
    bm25: MethodEvidenceRank
    deep_hybrid: MethodEvidenceRank
    query_bm25_tokens: list[str]
    evidence_bm25_token_overlap: list[str]
    evidence_preview: str


def _chunk_as_hit(chunk: DocumentChunk, rank: int = 0, score: float = 0.0) -> SearchHit:
    return SearchHit(
        rank=rank,
        score=score,
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        source_file=chunk.source_file,
        content_type=chunk.content_type,
        section=chunk.section,
        section_path=list(chunk.section_path),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        text=chunk.text,
        table_title=chunk.table_title,
        table_no=chunk.table_no,
        retrieval_method="dense",
    )


def _matching_evidence_chunks(case: RetrievalEvalCase, chunks: Iterable[DocumentChunk]) -> list[DocumentChunk]:
    matches: list[DocumentChunk] = []
    for chunk in chunks:
        if is_relevant(_chunk_as_hit(chunk), case.evidence_rules):
            matches.append(chunk)
    return matches


def _first_relevant(hits: Iterable[SearchHit], case: RetrievalEvalCase, method: str) -> MethodEvidenceRank:
    for hit in hits:
        if is_relevant(hit, case.evidence_rules):
            return MethodEvidenceRank(
                method=method,
                first_relevant_rank=hit.rank,
                score=float(hit.score),
                chunk_id=hit.chunk_id,
            )
    return MethodEvidenceRank(method=method, first_relevant_rank=None, score=None, chunk_id=None)


def _rank_or_inf(value: int | None) -> int:
    return value if value is not None else 10**9


def _diagnosis_category(
    *,
    evidence_exists: bool,
    operational_rank: int | None,
    dense_rank: int | None,
    bm25_rank: int | None,
    deep_hybrid_rank: int | None,
    top_k: int,
    candidate_k: int,
) -> tuple[str, str, str]:
    if not evidence_exists:
        return (
            "EVIDENCE_MISSING_FROM_CHUNKS",
            "按当前人工证据规则，在 chunks.json 中找不到任何合格证据块。此时不是检索器排序问题，而是上游解析/Chunk 或评测标注需要核对。",
            "先检查原始 PDF → cleaned_document → chunks 的证据是否丢失；同时复核评测规则的页码、章节与关键词是否过严。",
        )

    if operational_rank is not None and operational_rank <= top_k:
        return (
            "HIT",
            f"Hybrid 在 Top-{top_k} 内已经召回正确证据（rank={operational_rank}）。",
            "无需修召回；若正确证据不是 Top-1，后续交给 Reranker 优化排序。",
        )

    dense = _rank_or_inf(dense_rank)
    bm25 = _rank_or_inf(bm25_rank)
    deep_hybrid = _rank_or_inf(deep_hybrid_rank)

    if dense <= top_k or bm25 <= top_k:
        return (
            "FUSION_RANKING_LOSS",
            "至少一路检索器已经把正确证据放进 Top-K，但 RRF 融合后掉出了 Top-K，属于融合排序损失。",
            "检查 RRF 权重、去重与候选排名；可做 dense_weight/bm25_weight 小范围 A/B，而不是继续改 Chunk。",
        )

    if dense <= candidate_k or bm25 <= candidate_k:
        return (
            "FUSION_TOPK_LOSS",
            "正确证据进入了 RRF 的候选池，但融合后没有进入最终 Top-K。",
            "优先分析 RRF 排名与两路支持强度；若大量出现，可调权重或在融合后加 Reranker。",
        )

    if deep_hybrid <= top_k:
        return (
            "CANDIDATE_POOL_BOTTLENECK",
            "扩大候选池后正确证据可进入 Hybrid Top-K，说明当前 candidate_k 太小，候选截断发生在融合之前。",
            "提高 candidate_k（例如 30→50/100）并重新评测 Recall@K；注意候选越大，后续 Reranker 成本越高。",
        )

    best = min(dense, bm25)
    if best <= max(candidate_k * 2, top_k * 5):
        return (
            "WEAK_RECALL_NEAR_CANDIDATE_BOUNDARY",
            "正确证据存在，但 Dense/BM25 的原始排名都不够靠前，接近候选池边界。",
            "先尝试 Query normalization/rewrite、扩大 candidate_k，并检查精确数字/术语是否被 tokenizer 或 Chunk 表达破坏。",
        )

    return (
        "WEAK_RECALL",
        "正确证据存在于 Chunk 中，但 Dense 和 BM25 都把它排得很靠后，属于真正的召回能力不足。",
        "不要先上 Reranker，因为正确证据尚未进入候选集；应检查 Query 表达、Embedding、BM25 分词、Chunk 语义以及 metadata/filter 策略。",
    )


def diagnose_recall(
    suite: RetrievalEvalSuite,
    *,
    dense_index: LocalDenseIndex,
    bm25_index: LocalBM25Index,
    embedder: TextEmbedder,
    top_k: int = 10,
    candidate_k: int = 50,
    deep_k: int | None = None,
    rrf_k: int = 60,
    dense_weight: float = 1.0,
    bm25_weight: float = 1.0,
) -> list[RecallDiagnosis]:
    """Deep-diagnose where relevant evidence goes missing in the retrieval pipeline.

    The function intentionally separates three questions:
    1. Does a chunk satisfying the human evidence rule exist at all?
    2. Where does that evidence rank in Dense and BM25 before fusion?
    3. Does candidate truncation or RRF fusion itself lose the evidence?

    This distinction prevents us from "fixing" a retrieval problem by blindly changing
    Chunking when the real bottleneck is ranking, candidate size, or even the labels.
    """

    if top_k <= 0 or candidate_k <= 0:
        raise ValueError("top_k and candidate_k must be positive")
    if [chunk.chunk_id for chunk in dense_index.chunks] != [
        chunk.chunk_id for chunk in bm25_index.chunks
    ]:
        raise ValueError("dense and BM25 indexes must use the same chunks")

    total_chunks = len(dense_index.chunks)
    deep_k = total_chunks if deep_k is None else min(max(deep_k, top_k), total_chunks)

    operational_hybrid = ReciprocalRankFusionIndex(
        dense_index=dense_index,
        bm25_index=bm25_index,
        embedder=embedder,
        candidate_k=candidate_k,
        rrf_k=rrf_k,
        dense_weight=dense_weight,
        bm25_weight=bm25_weight,
    )
    deep_hybrid_index = ReciprocalRankFusionIndex(
        dense_index=dense_index,
        bm25_index=bm25_index,
        embedder=embedder,
        candidate_k=deep_k,
        rrf_k=rrf_k,
        dense_weight=dense_weight,
        bm25_weight=bm25_weight,
    )

    diagnoses: list[RecallDiagnosis] = []
    for case in suite.cases:
        evidence_chunks = _matching_evidence_chunks(case, dense_index.chunks)

        dense_hits = dense_index.search(case.query, embedder=embedder, top_k=deep_k).hits
        bm25_hits = bm25_index.search(case.query, top_k=deep_k).hits
        operational_hits = operational_hybrid.search(case.query, top_k=top_k).hits
        deep_hybrid_hits = deep_hybrid_index.search(case.query, top_k=deep_k).hits

        dense_rank = _first_relevant(dense_hits, case, "dense")
        bm25_rank = _first_relevant(bm25_hits, case, "bm25")
        hybrid_rank = _first_relevant(deep_hybrid_hits, case, "hybrid_rrf_deep")
        operational_rank = _first_relevant(operational_hits, case, "hybrid_rrf").first_relevant_rank

        category, explanation, recommendation = _diagnosis_category(
            evidence_exists=bool(evidence_chunks),
            operational_rank=operational_rank,
            dense_rank=dense_rank.first_relevant_rank,
            bm25_rank=bm25_rank.first_relevant_rank,
            deep_hybrid_rank=hybrid_rank.first_relevant_rank,
            top_k=top_k,
            candidate_k=candidate_k,
        )

        query_tokens = sorted(set(bm25_index.tokenizer.tokenize(case.query)))
        overlap: list[str] = []
        preview = ""
        if evidence_chunks:
            # Use the evidence chunk with the best observed raw rank so the diagnostic
            # describes the most retrievable ground-truth representation.
            rank_by_id: dict[str, int] = {}
            for hit in dense_hits:
                rank_by_id[hit.chunk_id] = min(rank_by_id.get(hit.chunk_id, 10**9), hit.rank)
            for hit in bm25_hits:
                rank_by_id[hit.chunk_id] = min(rank_by_id.get(hit.chunk_id, 10**9), hit.rank)
            chosen = min(evidence_chunks, key=lambda chunk: rank_by_id.get(chunk.chunk_id, 10**9))
            evidence_tokens = set(bm25_index.tokenizer.tokenize(chosen.embedding_text))
            overlap = sorted(set(query_tokens) & evidence_tokens)
            preview = chosen.text[:500].replace("\n", " ")

        diagnoses.append(
            RecallDiagnosis(
                case_id=case.id,
                query=case.query,
                category=category,
                explanation=explanation,
                recommendation=recommendation,
                evidence_chunk_count=len(evidence_chunks),
                evidence_chunk_ids=[chunk.chunk_id for chunk in evidence_chunks[:10]],
                operational_hybrid_rank=operational_rank,
                dense=dense_rank,
                bm25=bm25_rank,
                deep_hybrid=hybrid_rank,
                query_bm25_tokens=query_tokens,
                evidence_bm25_token_overlap=overlap,
                evidence_preview=preview,
            )
        )

    return diagnoses
