from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from medical_rag.chunking.models import ChunkedDocument, DocumentChunk
from medical_rag.chunking.paragraph_assembler import ParagraphAssembler
from medical_rag.chunking.section_detector import SectionDetector
from medical_rag.chunking.table_retrieval_text import TableRetrievalTextBuilder
from medical_rag.parsing.models import CleanedDocument, TableBlock, TextBlock


@dataclass(slots=True)
class _Segment:
    text: str
    page: int


@dataclass(slots=True)
class _SectionState:
    stack: dict[int, str] = field(default_factory=dict)

    def update(self, level: int, title: str) -> None:
        self.stack = {key: value for key, value in self.stack.items() if key < level}
        self.stack[level] = title

    @property
    def path(self) -> list[str]:
        return [self.stack[key] for key in sorted(self.stack)]

    @property
    def current(self) -> str | None:
        path = self.path
        return path[-1] if path else None


class StructureAwareChunker:
    """Stable structure-aware chunker for cleaned medical documents.

    Strategy:
    - rebuild paragraph-like units from PDF visual-line blocks;
    - keep section hierarchy as metadata;
    - use target size as a soft boundary and max size as the hard boundary;
    - split oversized paragraphs by sentence boundaries before any hard split;
    - build overlap from complete semantic tails instead of raw character slicing;
    - allow chunks to cross page boundaries while preserving page_start/page_end;
    - keep each ordinary table as an independent table chunk;
    - provide an ``embedding_text`` field with section context prepended;
    - drop only obvious one-token extraction noise; do not aggressively merge short chunks.

    This stable version intentionally keeps the finer V1.1 retrieval granularity while
    retaining the safer V1.2 section rules. Short chunks are not merged merely to make
    the document look cleaner, because our retrieval A/B test showed that aggressive
    merging diluted dense-retrieval semantics.
    """

    _SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?；;])")
    _TABLE_CAPTION_RE = re.compile(r"^\s*(?:表|Table)\s*\d+", re.IGNORECASE)

    def __init__(
        self,
        *,
        target_chars: int = 800,
        max_chars: int = 1200,
        min_chars: int = 180,
        overlap_chars: int = 120,
    ) -> None:
        if not (0 < min_chars <= target_chars <= max_chars):
            raise ValueError("Expected 0 < min_chars <= target_chars <= max_chars")
        if overlap_chars < 0 or overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be >= 0 and smaller than max_chars")

        self.target_chars = target_chars
        self.max_chars = max_chars
        self.min_chars = min_chars
        self.overlap_chars = overlap_chars
        self.section_detector = SectionDetector()
        self.table_text_builder = TableRetrievalTextBuilder()
        self.paragraph_assembler = ParagraphAssembler()

    def chunk(self, document: CleanedDocument) -> ChunkedDocument:
        document_id = self._document_id(document)
        source_file = document.file_name
        state = _SectionState()
        chunks: list[DocumentChunk] = []
        buffer: list[_Segment] = []
        buffer_section: str | None = None
        buffer_path: list[str] = []

        def flush_buffer() -> None:
            nonlocal buffer, buffer_section, buffer_path
            if not buffer:
                return
            for group in self._pack_segments(buffer):
                chunks.append(
                    self._narrative_chunk(
                        document_id=document_id,
                        source_file=source_file,
                        section=buffer_section,
                        section_path=buffer_path,
                        segments=group,
                        index=len(chunks),
                        metadata=document.metadata,
                    )
                )
            buffer = []

        for page in document.pages:
            elements = self._semantic_page_elements(
                page.blocks,
                page.tables,
                page.width,
            )
            page_table_titles = {
                self._caption_key(table.title)
                for table in page.tables
                if table.title
            }

            for kind, item in elements:
                if kind == "table":
                    flush_buffer()
                    table = item
                    assert isinstance(table, TableBlock)
                    chunks.append(
                        self._table_chunk(
                            document_id=document_id,
                            source_file=source_file,
                            table=table,
                            section=state.current,
                            section_path=state.path,
                            index=len(chunks),
                            metadata=document.metadata,
                        )
                    )
                    continue

                block = item
                assert isinstance(block, TextBlock)
                text = block.text.strip()
                if not text:
                    continue

                if self._is_duplicate_table_caption(text, page_table_titles):
                    continue

                # Recover an occasional extraction artifact such as:
                # ``……非随机对照研究1 我国人群高血压流行及防控现状``.
                embedded = self.section_detector.detect_trailing_embedded(block)
                if embedded is not None:
                    current_path = state.path
                    current_section = state.current
                    if buffer and (
                        current_section != buffer_section or current_path != buffer_path
                    ):
                        flush_buffer()
                    buffer_section = current_section
                    buffer_path = current_path
                    for piece in self._split_oversized_text(embedded.prefix):
                        buffer.append(_Segment(text=piece, page=page.page))
                    flush_buffer()

                    state.update(embedded.heading.level, embedded.heading.title)
                    buffer_section = state.current
                    buffer_path = state.path
                    if embedded.heading.body:
                        for piece in self._split_oversized_text(embedded.heading.body):
                            buffer.append(_Segment(text=piece, page=page.page))
                    continue

                heading = self.section_detector.detect(block)
                if heading is not None:
                    flush_buffer()
                    state.update(heading.level, heading.title)
                    buffer_section = state.current
                    buffer_path = state.path
                    if heading.body:
                        for piece in self._split_oversized_text(heading.body):
                            buffer.append(_Segment(text=piece, page=page.page))
                    continue

                current_path = state.path
                current_section = state.current
                if buffer and (
                    current_section != buffer_section or current_path != buffer_path
                ):
                    flush_buffer()

                buffer_section = current_section
                buffer_path = current_path
                for piece in self._split_oversized_text(text):
                    buffer.append(_Segment(text=piece, page=page.page))

        flush_buffer()

        # Safety-only post processing: remove obvious extraction artifacts but preserve
        # V1.1-like retrieval granularity. In V1.2, aggressively merging all short
        # chunks reduced Recall@3/Recall@5, so stable chunking deliberately avoids that.
        chunks = [
            chunk
            for chunk in chunks
            if not (
                chunk.content_type == "narrative"
                and self._is_obvious_noise(chunk.text)
            )
        ]

        # Reassign deterministic sequential IDs after all chunks are assembled.
        chunks = [
            chunk.model_copy(
                update={
                    "chunk_id": self._chunk_id(document_id, index, chunk.content_type),
                }
            )
            for index, chunk in enumerate(chunks)
        ]

        return ChunkedDocument(
            document_id=document_id,
            source_file=source_file,
            chunks=chunks,
        )

    def _semantic_page_elements(
        self,
        blocks: list[TextBlock],
        tables: list[TableBlock],
        page_width: float,
    ) -> list[tuple[str, TextBlock | TableBlock]]:
        """Interleave tables and paragraph-like narrative units in reading order."""

        raw = self._page_elements(blocks, tables, page_width)
        result: list[tuple[str, TextBlock | TableBlock]] = []
        text_run: list[TextBlock] = []

        def flush_text_run() -> None:
            nonlocal text_run
            if not text_run:
                return
            for paragraph in self.paragraph_assembler.assemble(text_run, page_width):
                result.append(("text", paragraph))
            text_run = []

        for kind, item in raw:
            if kind == "table":
                flush_text_run()
                result.append((kind, item))
            else:
                assert isinstance(item, TextBlock)
                text_run.append(item)
        flush_text_run()
        return result

    def _page_elements(
        self,
        blocks: list[TextBlock],
        tables: list[TableBlock],
        page_width: float,
    ) -> list[tuple[str, TextBlock | TableBlock]]:
        """Merge narrative blocks and tables in column-aware reading order.

        A table's detected bbox is not always a trustworthy reading-order anchor for
        borderless two-column PDFs: a virtual table can become wider than the real
        table.  ``caption_bbox`` is therefore preferred, and insertion is performed
        relative to text blocks in the *same column*.  This prevents a right-column
        table from inheriting the last section seen in the left column.
        """

        ordered_blocks = sorted(blocks, key=lambda block: block.reading_order)
        elements: list[tuple[str, TextBlock | TableBlock]] = [
            ("text", block) for block in ordered_blocks
        ]

        def side(bbox: tuple[float, float, float, float]) -> str:
            width = bbox[2] - bbox[0]
            midpoint = page_width * 0.5
            if width >= page_width * 0.58 or (bbox[0] < midpoint < bbox[2]):
                return "wide"
            center = (bbox[0] + bbox[2]) / 2
            return "left" if center < midpoint else "right"

        def text_side(element: TextBlock) -> str:
            return side(element.bbox)

        def fallback_insert(anchor: tuple[float, float, float, float]) -> int:
            for idx, (_, element) in enumerate(elements):
                if isinstance(element, TextBlock) and element.bbox[1] > anchor[1]:
                    return idx
            return len(elements)

        sorted_tables = sorted(
            tables,
            key=lambda item: (
                (item.caption_bbox or item.bbox)[1],
                (item.caption_bbox or item.bbox)[0],
            ),
        )
        for table in sorted_tables:
            anchor = table.caption_bbox or table.bbox
            table_side = side(anchor)

            if table_side == "wide":
                insert_at = fallback_insert(anchor)
                elements.insert(insert_at, ("table", table))
                continue

            same_side_indices = [
                idx
                for idx, (_, element) in enumerate(elements)
                if isinstance(element, TextBlock) and text_side(element) == table_side
            ]
            if not same_side_indices:
                elements.insert(fallback_insert(anchor), ("table", table))
                continue

            insert_at: int | None = None
            for idx in same_side_indices:
                element = elements[idx][1]
                assert isinstance(element, TextBlock)
                if element.bbox[1] > anchor[1]:
                    insert_at = idx
                    break

            if insert_at is None:
                # Put the table immediately after the final text block in its column,
                # which still keeps it before the next column in two-column reading
                # order.
                insert_at = same_side_indices[-1] + 1
            elements.insert(insert_at, ("table", table))

        return elements


    def _pack_segments(self, segments: list[_Segment]) -> list[list[_Segment]]:
        if not segments:
            return []

        groups: list[list[_Segment]] = []
        current: list[_Segment] = []
        current_len = 0

        for segment in segments:
            length = len(segment.text)
            separator = 2 if current else 0
            projected = current_len + separator + length

            # target_chars is deliberately soft: only flush at a semantic segment
            # boundary. max_chars remains the hard bound.
            should_flush = bool(
                current
                and (
                    projected > self.max_chars
                    or (current_len >= self.target_chars and projected > self.target_chars)
                )
            )
            if should_flush:
                groups.append(current)
                current = self._overlap_tail(current)
                current_len = self._segments_length(current)
                if current and current_len + 2 + length > self.max_chars:
                    current = []
                    current_len = 0

            current.append(segment)
            current_len = self._segments_length(current)

        if current:
            if groups and self._segments_length(current) < self.min_chars:
                merged = groups[-1] + [seg for seg in current if seg not in groups[-1]]
                if self._segments_length(merged) <= self.max_chars:
                    groups[-1] = merged
                else:
                    groups.append(current)
            else:
                groups.append(current)
        return groups

    def _overlap_tail(self, segments: list[_Segment]) -> list[_Segment]:
        """Build overlap from complete paragraphs/sentences, never raw character tails."""

        if self.overlap_chars <= 0 or not segments:
            return []

        selected: list[_Segment] = []
        remaining = self.overlap_chars
        for segment in reversed(segments):
            if remaining <= 0:
                break
            text = segment.text.strip()
            if not text:
                continue

            if len(text) <= remaining:
                selected.append(_Segment(text=text, page=segment.page))
                remaining -= len(text)
                continue

            tail = self._semantic_tail(text, remaining)
            if tail:
                selected.append(_Segment(text=tail, page=segment.page))
                remaining -= len(tail)
            break

        selected.reverse()
        return selected

    def _semantic_tail(self, text: str, budget: int) -> str:
        if budget <= 0:
            return ""
        units = self._sentence_units(text)
        if not units:
            return ""

        selected: list[str] = []
        used = 0
        for unit in reversed(units):
            length = len(unit)
            if length + used <= budget:
                selected.append(unit)
                used += length
                continue
            break

        selected.reverse()
        return self._concat_units(selected).strip()

    def _split_oversized_text(self, text: str) -> list[str]:
        text = self._normalize_text(text)
        if len(text) <= self.max_chars:
            return [text] if text else []

        sentences = self._sentence_units(text)
        if len(sentences) <= 1:
            return self._hard_split(text)

        pieces: list[str] = []
        current: list[str] = []
        current_len = 0
        for sentence in sentences:
            separator = self._unit_separator(current[-1] if current else "", sentence)
            projected = current_len + len(separator) + len(sentence)
            if current and projected > self.max_chars:
                pieces.append(self._concat_units(current).strip())
                current = []
                current_len = 0

            if len(sentence) <= self.max_chars:
                if current:
                    current_len += len(self._unit_separator(current[-1], sentence))
                current.append(sentence)
                current_len += len(sentence)
            else:
                hard = self._hard_split(sentence)
                if current:
                    pieces.append(self._concat_units(current).strip())
                    current = []
                    current_len = 0
                pieces.extend(hard)

        if current:
            pieces.append(self._concat_units(current).strip())
        return [piece for piece in pieces if piece]

    def _hard_split(self, text: str) -> list[str]:
        """Last-resort split for a single extremely long sentence.

        Prefer a comma/colon/whitespace near the hard limit instead of blindly cutting a
        medical term or numeric expression in the middle.
        """

        text = text.strip()
        if len(text) <= self.max_chars:
            return [text]

        pieces: list[str] = []
        remaining = text
        while len(remaining) > self.max_chars:
            lower = max(int(self.max_chars * 0.65), 1)
            window = remaining[lower : self.max_chars + 1]
            cut = -1
            for token in ("，", ",", "、", "：", ":", " "):
                pos = window.rfind(token)
                if pos >= 0:
                    cut = max(cut, lower + pos + 1)
            if cut <= 0:
                cut = self.max_chars
            pieces.append(remaining[:cut].strip())
            remaining = remaining[cut:].strip()

        if remaining:
            pieces.append(remaining)
        return pieces


    @staticmethod
    def _is_obvious_noise(text: str) -> bool:
        """Return True only for tiny standalone layout artifacts.

        ``min_chars`` remains a soft size target. We do not delete short medical
        statements merely because they are short. This filter is intentionally narrow.
        """

        value = re.sub(r"[\s\-—_=：:·•.,，。;；()（）]+", "", text or "")
        return value in {"", "表", "图", "注", "页"}

    def _narrative_chunk(
        self,
        *,
        document_id: str,
        source_file: str,
        section: str | None,
        section_path: list[str],
        segments: list[_Segment],
        index: int,
        metadata: dict[str, str],
    ) -> DocumentChunk:
        text = self._render_segments_text(segments)
        pages = [segment.page for segment in segments]
        embedding_text = self._embedding_text(section_path, text)
        return DocumentChunk(
            chunk_id=self._chunk_id(document_id, index, "narrative"),
            document_id=document_id,
            source_file=source_file,
            content_type="narrative",
            section=section,
            section_path=list(section_path),
            page_start=min(pages),
            page_end=max(pages),
            text=text,
            embedding_text=embedding_text,
            char_count=len(text),
            metadata=dict(metadata),
        )

    def _table_chunk(
        self,
        *,
        document_id: str,
        source_file: str,
        table: TableBlock,
        section: str | None,
        section_path: list[str],
        index: int,
        metadata: dict[str, str],
    ) -> DocumentChunk:
        retrieval = self.table_text_builder.build(table)
        text = retrieval.text
        context = list(section_path)
        if table.title and (not context or context[-1] != table.title):
            context.append(table.title)
        return DocumentChunk(
            chunk_id=self._chunk_id(document_id, index, "table"),
            document_id=document_id,
            source_file=source_file,
            content_type="table",
            section=section,
            section_path=list(section_path),
            page_start=table.page,
            page_end=table.page,
            text=text,
            embedding_text=self._embedding_text(context, text),
            char_count=len(text),
            table_title=table.title,
            table_no=table.table_no,
            metadata={
                **dict(metadata),
                "table_retrieval_strategy": retrieval.strategy,
                "table_raw_fallback_used": str(retrieval.used_raw_fallback).lower(),
                "table_missing_numeric_tokens": ",".join(retrieval.missing_numeric_tokens),
                "table_extraction_strategy": table.extraction_strategy,
                "table_quality_flags": ",".join(table.quality_flags),
            },
        )

    @classmethod
    def _render_segments_text(cls, segments: list[_Segment]) -> str:
        clean = [segment for segment in segments if segment.text.strip()]
        if not clean:
            return ""
        result = clean[0].text.strip()
        previous = clean[0]
        for current in clean[1:]:
            current_text = current.text.strip()
            if current.page != previous.page and cls._should_join_page_boundary(
                previous.text.strip(), current_text
            ):
                result = cls._join_page_boundary(result, current_text)
            else:
                result += "\n\n" + current_text
            previous = current
        return result

    @staticmethod
    def _should_join_page_boundary(previous: str, current: str) -> bool:
        if not previous or not current:
            return False
        if previous.endswith(("。", "！", "？", "!", "?", "；", ";")):
            return False
        return True

    @staticmethod
    def _join_page_boundary(previous: str, current: str) -> str:
        if previous.endswith("-") and current[:1].isascii() and current[:1].isalpha():
            return previous[:-1] + current
        left = previous[-1]
        right = current[0]
        if left.isascii() and right.isascii() and left.isalnum() and right.isalnum():
            return previous + " " + current
        return previous + current

    @classmethod
    def _sentence_units(cls, text: str) -> list[str]:
        return [item.strip() for item in cls._SENTENCE_SPLIT_RE.split(text) if item.strip()]

    @classmethod
    def _concat_units(cls, units: list[str]) -> str:
        if not units:
            return ""
        result = units[0]
        for unit in units[1:]:
            result += cls._unit_separator(result, unit) + unit
        return result

    @staticmethod
    def _unit_separator(previous: str, current: str) -> str:
        if not previous or not current:
            return ""
        left = previous[-1]
        right = current[0]
        if left.isascii() and right.isascii() and left.isalnum() and right.isalnum():
            return " "
        return ""

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\r", "\n")
        text = re.sub(r"[\t\u3000]+", " ", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    @staticmethod
    def _embedding_text(section_path: list[str], text: str) -> str:
        if not section_path:
            return text
        return "章节：" + " > ".join(section_path) + "\n\n" + text

    @staticmethod
    def _segments_length(segments: list[_Segment]) -> int:
        if not segments:
            return 0
        return sum(len(segment.text) for segment in segments) + 2 * (len(segments) - 1)

    @classmethod
    def _is_duplicate_table_caption(cls, text: str, table_keys: set[str]) -> bool:
        if not cls._TABLE_CAPTION_RE.match(text):
            return False
        return cls._caption_key(text) in table_keys

    @staticmethod
    def _caption_key(text: str | None) -> str:
        if not text:
            return ""
        first = text.splitlines()[0]
        return re.sub(r"\s+", "", first).lower()[:80]

    @staticmethod
    def _document_id(document: CleanedDocument) -> str:
        stem = Path(document.file_name).stem
        normalized = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", stem).strip("_")
        digest = hashlib.sha1(document.file_name.encode("utf-8")).hexdigest()[:8]
        prefix = normalized[:48] or "document"
        return f"{prefix}_{digest}"

    @staticmethod
    def _chunk_id(document_id: str, index: int, content_type: str) -> str:
        short_type = "txt" if content_type == "narrative" else "tbl"
        return f"{document_id}_{short_type}_{index:05d}"
