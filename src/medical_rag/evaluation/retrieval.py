from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable

from medical_rag.embedding.base import TextEmbedder
from medical_rag.evaluation.models import (
    EvidenceRule,
    KeywordProximityRule,
    RetrievalEvalCaseResult,
    RetrievalEvalHit,
    RetrievalEvalReport,
    RetrievalEvalSuite,
)
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex
from medical_rag.retrieval.models import SearchHit


def _norm(text: str | None) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = value.replace("～", "~").replace("−", "-").replace("—", "-")
    value = re.sub(r"\s+", "", value)
    return value.lower()


def _page_matches(hit: SearchHit, rule: EvidenceRule) -> bool:
    if not rule.page_ranges:
        return True
    for start, end in rule.page_ranges:
        if hit.page_start <= end and hit.page_end >= start:
            return True
    return False


def _all_occurrences(haystack: str, needle: str) -> list[int]:
    if not needle:
        return []
    positions: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx < 0:
            break
        positions.append(idx)
        start = idx + 1
    return positions


def _proximity_matches(haystack: str, rule: KeywordProximityRule) -> bool:
    keywords = [_norm(keyword) for keyword in rule.keywords if _norm(keyword)]
    if len(keywords) < 2:
        return False

    positions_by_keyword = [_all_occurrences(haystack, keyword) for keyword in keywords]
    if any(not positions for positions in positions_by_keyword):
        return False

    # The rules are intentionally small (normally 2-4 keywords), so a recursive
    # search is simple and deterministic. Stop as soon as one compact span is found.
    def search(index: int, chosen: list[int]) -> bool:
        if index == len(positions_by_keyword):
            return max(chosen) - min(chosen) <= rule.max_chars
        for position in positions_by_keyword[index]:
            if chosen:
                lower = min(min(chosen), position)
                upper = max(max(chosen), position)
                if upper - lower > rule.max_chars:
                    continue
            if search(index + 1, [*chosen, position]):
                return True
        return False

    return search(0, [])


def _rule_matches(hit: SearchHit, rule: EvidenceRule) -> bool:
    if not _page_matches(hit, rule):
        return False

    if rule.content_types and hit.content_type not in rule.content_types:
        return False

    section = _norm(hit.section)
    if rule.section_contains_any:
        if not any(_norm(value) in section for value in rule.section_contains_any):
            return False

    table_title = _norm(hit.table_title)
    if rule.table_title_contains_any:
        if not any(_norm(value) in table_title for value in rule.table_title_contains_any):
            return False

    haystack = _norm("\n".join(filter(None, [hit.section, hit.table_title, hit.text])))
    if rule.required_keywords:
        if not all(_norm(keyword) in haystack for keyword in rule.required_keywords):
            return False
    if rule.any_keywords:
        if not any(_norm(keyword) in haystack for keyword in rule.any_keywords):
            return False
    if rule.excluded_keywords:
        if any(_norm(keyword) in haystack for keyword in rule.excluded_keywords):
            return False
    if rule.proximity_groups:
        if not all(_proximity_matches(haystack, group) for group in rule.proximity_groups):
            return False
    return True


def matching_rule_ids(hit: SearchHit, rules: list[EvidenceRule]) -> list[str]:
    matched: list[str] = []
    for index, rule in enumerate(rules, start=1):
        if _rule_matches(hit, rule):
            matched.append(rule.rule_id or f"rule_{index}")
    return matched


def is_relevant(hit: SearchHit, rules: list[EvidenceRule]) -> bool:
    if not rules:
        return False
    return bool(matching_rule_ids(hit, rules))


def evaluate_retriever(
    suite: RetrievalEvalSuite,
    *,
    search: Callable[[str, int], list[SearchHit]],
    retriever_name: str,
    model_name: str = "",
    top_k: int = 10,
) -> RetrievalEvalReport:
    """Evaluate any retrieval method with exactly the same evidence-level labels."""

    if top_k < 5:
        raise ValueError("top_k must be >= 5 so Recall@1/@3/@5 can all be computed")
    if not suite.cases:
        raise ValueError("evaluation suite contains no cases")

    results: list[RetrievalEvalCaseResult] = []
    first_ranks: list[int | None] = []

    for case in suite.cases:
        hits = search(case.query, top_k)
        eval_hits: list[RetrievalEvalHit] = []
        first_rank: int | None = None
        relevant_hit_count = 0

        for hit in hits:
            matched_rule_ids = matching_rule_ids(hit, case.evidence_rules)
            relevant = bool(matched_rule_ids)
            if relevant:
                relevant_hit_count += 1
                if first_rank is None:
                    first_rank = hit.rank
            eval_hits.append(
                RetrievalEvalHit(
                    rank=hit.rank,
                    score=hit.score,
                    chunk_id=hit.chunk_id,
                    page_start=hit.page_start,
                    page_end=hit.page_end,
                    section=hit.section,
                    content_type=hit.content_type,
                    table_title=hit.table_title,
                    text_preview=hit.text[:360].replace("\n", " "),
                    relevant=relevant,
                    matched_rule_ids=matched_rule_ids,
                )
            )

        first_ranks.append(first_rank)
        reciprocal_rank = 0.0 if first_rank is None else 1.0 / first_rank
        results.append(
            RetrievalEvalCaseResult(
                id=case.id,
                query=case.query,
                first_relevant_rank=first_rank,
                reciprocal_rank=round(reciprocal_rank, 6),
                relevant_hit_count=relevant_hit_count,
                hits=eval_hits,
            )
        )

    total = len(first_ranks)

    def recall_at(k: int) -> float:
        value = sum(rank is not None and rank <= k for rank in first_ranks) / total
        return round(value, 6)

    mrr = sum(0.0 if rank is None else 1.0 / rank for rank in first_ranks) / total
    return RetrievalEvalReport(
        suite_name=suite.name,
        suite_version=suite.version,
        retriever_name=retriever_name,
        model_name=model_name,
        query_count=total,
        top_k=top_k,
        recall_at_1=recall_at(1),
        recall_at_3=recall_at(3),
        recall_at_5=recall_at(5),
        mrr=round(mrr, 6),
        no_relevant_in_top_k=sum(rank is None for rank in first_ranks),
        results=results,
    )


class DenseRetrievalEvaluator:
    """Evaluate local dense retrieval with manually defined evidence rules."""

    def __init__(self, *, index: LocalDenseIndex, embedder: TextEmbedder) -> None:
        self.index = index
        self.embedder = embedder

    def evaluate(self, suite: RetrievalEvalSuite, *, top_k: int = 10) -> RetrievalEvalReport:
        return evaluate_retriever(
            suite,
            search=lambda query, k: self.index.search(
                query, embedder=self.embedder, top_k=k
            ).hits,
            retriever_name="dense",
            model_name=self.index.manifest.model_name,
            top_k=top_k,
        )


class BM25RetrievalEvaluator:
    def __init__(self, *, index: LocalBM25Index) -> None:
        self.index = index

    def evaluate(self, suite: RetrievalEvalSuite, *, top_k: int = 10) -> RetrievalEvalReport:
        return evaluate_retriever(
            suite,
            search=lambda query, k: self.index.search(query, top_k=k).hits,
            retriever_name="bm25",
            model_name=self.index.tokenizer.name,
            top_k=top_k,
        )


class HybridRetrievalEvaluator:
    def __init__(self, *, index: ReciprocalRankFusionIndex) -> None:
        self.index = index

    def evaluate(self, suite: RetrievalEvalSuite, *, top_k: int = 10) -> RetrievalEvalReport:
        return evaluate_retriever(
            suite,
            search=lambda query, k: self.index.search(query, top_k=k).hits,
            retriever_name="hybrid_rrf",
            model_name=(
                f"{self.index.dense_index.manifest.model_name}+"
                f"{self.index.bm25_index.tokenizer.name}"
            ),
            top_k=top_k,
        )


class RerankedHybridRetrievalEvaluator:
    def __init__(self, *, index) -> None:
        self.index = index

    def evaluate(self, suite: RetrievalEvalSuite, *, top_k: int = 10) -> RetrievalEvalReport:
        return evaluate_retriever(
            suite,
            search=lambda query, k: self.index.search(query, top_k=k).hits,
            retriever_name="hybrid_rerank",
            model_name=(
                f"{self.index.hybrid_index.dense_index.manifest.model_name}+"
                f"{self.index.hybrid_index.bm25_index.tokenizer.name}+"
                f"{self.index.reranker.model_name}"
            ),
            top_k=top_k,
        )
