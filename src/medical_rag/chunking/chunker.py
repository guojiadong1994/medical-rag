from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from medical_rag.chunking.models import ChunkedDocument, DocumentChunk
from medical_rag.chunking.paragraph_assembler import ParagraphAssembler
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
    """Structure-aware V1.2 chunker for cleaned medical documents.

    Strategy:
    - rebuild paragraph-like units from PDF visual-line blocks;
    - keep section hierarchy as metadata;
    - use target size as a soft boundary and max size as the hard boundary;
    - split oversized paragraphs by sentence boundaries before any hard split;
    - build overlap from complete semantic tails instead of raw character slicing;
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

        # V1.2 removes obvious one-character extraction noise and merges adjacent
        # undersized narrative chunks only when they share the same section and the
        # merged text still respects the narrative hard limit. Table chunks remain
        # intact because preserving row/column context is more important than the
        # narrative max_chars setting.
        chunks = self._postprocess_chunks(chunks)

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

        raw = self._page_elements(blocks, tables)
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

    def _postprocess_chunks(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """Clean tiny extraction artifacts and merge safe short narrative chunks.

        ``min_chars`` is a soft target, not a deletion threshold. A short chunk may be
        medically meaningful, so V1.2 only drops a tiny explicit noise set and only
        merges adjacent narrative chunks when section metadata matches exactly.
        """

        filtered = [
            chunk
            for chunk in chunks
            if not (
                chunk.content_type == "narrative"
                and self._is_obvious_noise(chunk.text)
            )
        ]
        if not filtered:
            return []

        # Forward pass: first try to merge a short chunk into the next chunk. This helps
        # the first chunk of a section without crossing a section/table boundary.
        forward: list[DocumentChunk] = []
        idx = 0
        while idx < len(filtered):
            current = filtered[idx]
            if (
                current.content_type == "narrative"
                and current.char_count < self.min_chars
                and idx + 1 < len(filtered)
            ):
                nxt = filtered[idx + 1]
                if self._can_merge_narrative(current, nxt):
                    forward.append(self._merge_narrative_chunks(current, nxt))
                    idx += 2
                    continue
            forward.append(current)
            idx += 1

        # Backward-safe pass: merge any remaining short chunk into its immediate
        # previous narrative sibling when possible.
        result: list[DocumentChunk] = []
        for current in forward:
            if (
                current.content_type == "narrative"
                and current.char_count < self.min_chars
                and result
                and self._can_merge_narrative(result[-1], current)
            ):
                result[-1] = self._merge_narrative_chunks(result[-1], current)
            else:
                result.append(current)
        return result

    def _can_merge_narrative(self, left: DocumentChunk, right: DocumentChunk) -> bool:
        if left.content_type != "narrative" or right.content_type != "narrative":
            return False
        if left.section_path != right.section_path or left.section != right.section:
            return False
        if right.page_start > left.page_end + 1:
            return False
        merged_text = self._merge_text_without_duplicate_overlap(left.text, right.text)
        return len(merged_text) <= self.max_chars

    def _merge_narrative_chunks(
        self,
        left: DocumentChunk,
        right: DocumentChunk,
    ) -> DocumentChunk:
        text = self._merge_text_without_duplicate_overlap(left.text, right.text)
        section_path = list(left.section_path)
        return left.model_copy(
            update={
                "page_start": min(left.page_start, right.page_start),
                "page_end": max(left.page_end, right.page_end),
                "text": text,
                "embedding_text": self._embedding_text(section_path, text),
                "char_count": len(text),
            }
        )

    @staticmethod
    def _merge_text_without_duplicate_overlap(left: str, right: str) -> str:
        left = left.strip()
        right = right.strip()
        if not left:
            return right
        if not right:
            return left

        # Chunk overlap is exact text copied from the semantic tail. Remove the longest
        # exact duplicated prefix/suffix before joining two chunks back together.
        max_overlap = min(len(left), len(right), 300)
        overlap = 0
        for size in range(max_overlap, 19, -1):
            if left[-size:] == right[:size]:
                overlap = size
                break
        right_tail = right[overlap:].lstrip()
        if not right_tail:
            return left
        if left.endswith(("\n", " ")):
            return left + right_tail
        return left + "\n\n" + right_tail

    @staticmethod
    def _is_obvious_noise(text: str) -> bool:
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
