from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from pydantic import BaseModel, Field

from medical_rag.retrieval.models import RerankedHybridSearchHit, RerankedHybridSearchResponse


_CITATION_RE = re.compile(r"\[(S\d+)\]")
_WHITESPACE_RE = re.compile(r"\s+")


class RAGCitation(BaseModel):
    citation_id: str
    retrieval_rank: int
    chunk_id: str
    document_id: str
    source_file: str
    page_start: int
    page_end: int
    section: str | None = None
    section_path: list[str] = Field(default_factory=list)
    content_type: str
    table_title: str | None = None
    reranker_score: float
    pre_rerank_rank: int

    @property
    def page_label(self) -> str:
        if self.page_start == self.page_end:
            return str(self.page_start)
        return f"{self.page_start}-{self.page_end}"


class RAGContextSource(BaseModel):
    citation: RAGCitation
    text: str
    rendered_text: str
    truncated: bool = False


class RAGContext(BaseModel):
    query: str
    context_text: str
    sources: list[RAGContextSource] = Field(default_factory=list)
    requested_top_k: int
    selected_source_count: int
    max_context_chars: int
    used_context_chars: int
    exact_duplicate_skipped: int = 0
    budget_skipped: int = 0
    truncated_source_count: int = 0

    @property
    def citation_ids(self) -> list[str]:
        return [source.citation.citation_id for source in self.sources]


class CitationValidationResult(BaseModel):
    cited_ids: list[str] = Field(default_factory=list)
    unknown_ids: list[str] = Field(default_factory=list)
    valid: bool


@dataclass(frozen=True)
class ContextBuilderConfig:
    top_k: int = 5
    max_context_chars: int = 6000
    min_truncated_text_chars: int = 120

    def __post_init__(self) -> None:
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if self.max_context_chars <= 0:
            raise ValueError("max_context_chars must be positive")
        if self.min_truncated_text_chars <= 0:
            raise ValueError("min_truncated_text_chars must be positive")


def _normalize_for_dedup(text: str) -> str:
    return _WHITESPACE_RE.sub("", text).strip().lower()


def _source_header(citation: RAGCitation) -> str:
    lines = [
        f"[{citation.citation_id}]",
        f"来源文件：{citation.source_file}",
        f"页码：{citation.page_label}",
    ]
    if citation.section:
        lines.append(f"章节：{citation.section}")
    if citation.table_title:
        lines.append(f"表格：{citation.table_title}")
    lines.append(f"内容类型：{citation.content_type}")
    return "\n".join(lines)


def _make_citation(hit: RerankedHybridSearchHit, citation_id: str) -> RAGCitation:
    return RAGCitation(
        citation_id=citation_id,
        retrieval_rank=hit.rank,
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        source_file=hit.source_file,
        page_start=hit.page_start,
        page_end=hit.page_end,
        section=hit.section,
        section_path=list(hit.section_path),
        content_type=hit.content_type,
        table_title=hit.table_title,
        reranker_score=hit.reranker_score,
        pre_rerank_rank=hit.pre_rerank_rank,
    )


def _render_source(citation: RAGCitation, text: str) -> str:
    return f"{_source_header(citation)}\n证据内容：\n{text.strip()}"


class RAGContextBuilder:
    """Convert reranked retrieval hits into bounded, traceable LLM context.

    The builder is intentionally deterministic: retrieval decides relevance; this
    layer only assigns stable per-answer citation IDs, removes exact duplicates,
    and enforces a context budget without silently changing source order.
    """

    def __init__(self, config: ContextBuilderConfig | None = None) -> None:
        self.config = config or ContextBuilderConfig()

    def build(self, response: RerankedHybridSearchResponse) -> RAGContext:
        seen_texts: set[str] = set()
        sources: list[RAGContextSource] = []
        used = 0
        duplicate_skipped = 0
        budget_skipped = 0
        truncated_count = 0

        for hit in response.hits[: self.config.top_k]:
            normalized = _normalize_for_dedup(hit.text)
            if normalized and normalized in seen_texts:
                duplicate_skipped += 1
                continue
            if normalized:
                seen_texts.add(normalized)

            citation_id = f"S{len(sources) + 1}"
            citation = _make_citation(hit, citation_id)
            full_rendered = _render_source(citation, hit.text)
            separator_cost = 2 if sources else 0
            remaining = self.config.max_context_chars - used - separator_cost

            if remaining <= 0:
                budget_skipped += 1
                continue

            if len(full_rendered) <= remaining:
                rendered = full_rendered
                source_text = hit.text.strip()
                truncated = False
            else:
                header = _source_header(citation) + "\n证据内容：\n"
                available_text = remaining - len(header) - len("…[上下文预算截断]")
                if available_text < self.config.min_truncated_text_chars:
                    budget_skipped += 1
                    continue
                source_text = hit.text.strip()[:available_text].rstrip()
                rendered = f"{header}{source_text}…[上下文预算截断]"
                truncated = True
                truncated_count += 1

            if sources:
                used += 2
            used += len(rendered)
            sources.append(
                RAGContextSource(
                    citation=citation,
                    text=source_text,
                    rendered_text=rendered,
                    truncated=truncated,
                )
            )

        context_text = "\n\n".join(source.rendered_text for source in sources)
        return RAGContext(
            query=response.query,
            context_text=context_text,
            sources=sources,
            requested_top_k=self.config.top_k,
            selected_source_count=len(sources),
            max_context_chars=self.config.max_context_chars,
            used_context_chars=len(context_text),
            exact_duplicate_skipped=duplicate_skipped,
            budget_skipped=budget_skipped,
            truncated_source_count=truncated_count,
        )


def validate_answer_citations(answer: str, context: RAGContext) -> CitationValidationResult:
    seen: list[str] = []
    for citation_id in _CITATION_RE.findall(answer):
        if citation_id not in seen:
            seen.append(citation_id)
    allowed = set(context.citation_ids)
    unknown = [citation_id for citation_id in seen if citation_id not in allowed]
    return CitationValidationResult(cited_ids=seen, unknown_ids=unknown, valid=not unknown)


def citation_summary_lines(context: RAGContext) -> Iterable[str]:
    for source in context.sources:
        citation = source.citation
        detail = f"[{citation.citation_id}] {citation.source_file} · P{citation.page_label}"
        if citation.section:
            detail += f" · {citation.section}"
        if citation.table_title:
            detail += f" · {citation.table_title}"
        yield detail
