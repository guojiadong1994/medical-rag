from __future__ import annotations

import re
import unicodedata

from medical_rag.embedding.base import TextEmbedder
from medical_rag.evaluation.models import (
    EvidenceRule,
    RetrievalEvalCaseResult,
    RetrievalEvalHit,
    RetrievalEvalReport,
    RetrievalEvalSuite,
)
from medical_rag.retrieval import LocalDenseIndex
from medical_rag.retrieval.models import DenseSearchHit


def _norm(text: str | None) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = value.replace("～", "~").replace("−", "-").replace("—", "-")
    value = re.sub(r"\s+", "", value)
    return value.lower()


def _page_matches(hit: DenseSearchHit, rule: EvidenceRule) -> bool:
    if not rule.page_ranges:
        return True
    for start, end in rule.page_ranges:
        if hit.page_start <= end and hit.page_end >= start:
            return True
    return False


def _rule_matches(hit: DenseSearchHit, rule: EvidenceRule) -> bool:
    if not _page_matches(hit, rule):
        return False

    if rule.content_types and hit.content_type not in rule.content_types:
        return False

    section = _norm(hit.section)
    if rule.section_contains_any:
        if not any(_norm(value) in section for value in rule.section_contains_any):
            return False

    haystack = _norm("\n".join(filter(None, [hit.section, hit.table_title, hit.text])))
    if rule.required_keywords:
        if not all(_norm(keyword) in haystack for keyword in rule.required_keywords):
            return False
    if rule.any_keywords:
        if not any(_norm(keyword) in haystack for keyword in rule.any_keywords):
            return False
    return True


def is_relevant(hit: DenseSearchHit, rules: list[EvidenceRule]) -> bool:
    if not rules:
        return False
    return any(_rule_matches(hit, rule) for rule in rules)


class DenseRetrievalEvaluator:
    """Evaluate local dense retrieval with manually defined evidence rules."""

    def __init__(self, *, index: LocalDenseIndex, embedder: TextEmbedder) -> None:
        self.index = index
        self.embedder = embedder

    def evaluate(self, suite: RetrievalEvalSuite, *, top_k: int = 10) -> RetrievalEvalReport:
        if top_k < 5:
            raise ValueError("top_k must be >= 5 so Recall@1/@3/@5 can all be computed")
        if not suite.cases:
            raise ValueError("evaluation suite contains no cases")

        results: list[RetrievalEvalCaseResult] = []
        first_ranks: list[int | None] = []

        for case in suite.cases:
            response = self.index.search(case.query, embedder=self.embedder, top_k=top_k)
            eval_hits: list[RetrievalEvalHit] = []
            first_rank: int | None = None

            for hit in response.hits:
                relevant = is_relevant(hit, case.evidence_rules)
                if relevant and first_rank is None:
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
                        relevant=relevant,
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
            model_name=self.index.manifest.model_name,
            query_count=total,
            top_k=top_k,
            recall_at_1=recall_at(1),
            recall_at_3=recall_at(3),
            recall_at_5=recall_at(5),
            mrr=round(mrr, 6),
            no_relevant_in_top_k=sum(rank is None for rank in first_ranks),
            results=results,
        )
