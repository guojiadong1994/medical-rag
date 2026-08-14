from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from medical_rag.chunking.models import ChunkedDocument, DocumentChunk
from medical_rag.chunking.section_detector import SectionDetector
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
    """Structure-aware V1 chunker for cleaned medical documents.

    Strategy:
    - keep section hierarchy as metadata;
    - prefer block/paragraph boundaries;
    - split oversized paragraphs by sentence boundaries;
    - allow chunks to cross page boundaries while preserving page_start/page_end;
    - keep each ordinary table as an independent table chunk;
    - provide an ``embedding_text`` field with section context prepended.
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
            elements = self._page_elements(page.blocks, page.tables)
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

                heading = self.section_detector.detect(block)
                if heading is not None:
                    flush_buffer()
                    state.update(heading.level, heading.title)
                    buffer_section = state.current
                    buffer_path = state.path
                    if heading.body:
                        buffer.append(_Segment(text=heading.body, page=page.page))
                    continue

                current_path = state.path
                current_section = state.current
                if buffer and (current_section != buffer_section or current_path != buffer_path):
                    flush_buffer()

                buffer_section = current_section
                buffer_path = current_path
                for piece in self._split_oversized_text(text):
                    buffer.append(_Segment(text=piece, page=page.page))

        flush_buffer()

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

    def _page_elements(
        self,
        blocks: list[TextBlock],
        tables: list[TableBlock],
    ) -> list[tuple[str, TextBlock | TableBlock]]:
        """Merge narrative blocks and tables into an approximate page reading order."""
        ordered_blocks = sorted(blocks, key=lambda block: block.reading_order)
        elements: list[tuple[str, TextBlock | TableBlock]] = [
            ("text", block) for block in ordered_blocks
        ]

        for table in sorted(tables, key=lambda item: (item.bbox[1], item.bbox[0])):
            insert_at = len(elements)
            for idx, (_, element) in enumerate(elements):
                if not isinstance(element, TextBlock):
                    continue
                # A table is normally consumed after the nearest text block above it.
                if element.bbox[1] > table.bbox[1]:
                    insert_at = idx
                    break
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
            else:
                selected.append(_Segment(text=text[-remaining:], page=segment.page))
                remaining = 0
        selected.reverse()
        return selected

    def _split_oversized_text(self, text: str) -> list[str]:
        text = text.strip()
        if len(text) <= self.max_chars:
            return [text]

        sentences = [item.strip() for item in self._SENTENCE_SPLIT_RE.split(text) if item.strip()]
        if len(sentences) <= 1:
            return self._hard_split(text)

        pieces: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = sentence if not current else current + sentence
            if len(candidate) <= self.max_chars:
                current = candidate
                continue
            if current:
                pieces.append(current)
            if len(sentence) <= self.max_chars:
                current = sentence
            else:
                hard = self._hard_split(sentence)
                pieces.extend(hard[:-1])
                current = hard[-1]
        if current:
            pieces.append(current)
        return pieces

    def _hard_split(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]
        step = max(1, self.max_chars - self.overlap_chars)
        return [text[start : start + self.max_chars] for start in range(0, len(text), step)]

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
        text = table.search_text.strip() or table.markdown.strip()
        if not text:
            text = table.title or f"表格 {table.table_no + 1}"
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
            metadata=dict(metadata),
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
        # A page break is a physical boundary, not a semantic one. If the previous page
        # ends mid-sentence, continue directly on the next page.
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
