from __future__ import annotations

import re
from collections import Counter

from medical_rag.parsing.models import (
    CleanedDocument,
    CleanedPage,
    ParsedDocument,
    TableBlock,
    TextBlock,
)


class DocumentCleaner:
    """Clean parser output without destroying medically meaningful content."""

    _PAGE_NUMBER_RE = re.compile(r"^[·•\-–—\s]*\d{1,4}[·•\-–—\s]*$")
    _WHITESPACE_RE = re.compile(r"[ \t\u3000]+")
    _NOISE_CHARS_RE = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff\ufffe\uffff]")

    def __init__(
        self,
        *,
        top_band_ratio: float = 0.085,
        bottom_band_ratio: float = 0.915,
        repeat_page_ratio: float = 0.25,
        min_repeat_pages: int = 4,
    ) -> None:
        self.top_band_ratio = top_band_ratio
        self.bottom_band_ratio = bottom_band_ratio
        self.repeat_page_ratio = repeat_page_ratio
        self.min_repeat_pages = min_repeat_pages

    def clean(self, document: ParsedDocument) -> CleanedDocument:
        repeated_patterns = self._find_repeated_margin_patterns(document)
        cleaned_pages: list[CleanedPage] = []

        for page in document.pages:
            cleaned_blocks: list[TextBlock] = []
            for block in page.blocks:
                if self._is_margin_noise(block, page.height, repeated_patterns):
                    continue
                text = self.clean_block_text(block.text)
                if not text:
                    continue
                cleaned_blocks.append(block.model_copy(update={"text": text}))

            cleaned_blocks.sort(key=lambda b: b.reading_order)
            cleaned_tables = [self._clean_table(table) for table in page.tables]

            cleaned_pages.append(
                CleanedPage(
                    page=page.page,
                    width=page.width,
                    height=page.height,
                    blocks=cleaned_blocks,
                    tables=cleaned_tables,
                    text=self._render_page_text(cleaned_blocks, page.width),
                )
            )

        return CleanedDocument(
            source_path=document.source_path,
            file_name=document.file_name,
            page_count=document.page_count,
            metadata=document.metadata,
            pages=cleaned_pages,
            repeated_noise_patterns=sorted(repeated_patterns),
        )

    def _clean_table(self, table: TableBlock) -> TableBlock:
        title = self.clean_block_text(table.title) if table.title else None
        headers = [self.clean_block_text(cell) for cell in table.headers]
        rows = [[self.clean_block_text(cell) for cell in row] for row in table.rows]

        markdown = self._table_to_markdown(headers, rows)
        search_text = self._table_to_search_text(title, headers, rows)
        return table.model_copy(
            update={
                "title": title,
                "headers": headers,
                "rows": rows,
                "markdown": markdown,
                "search_text": search_text,
            }
        )

    def clean_block_text(self, text: str) -> str:
        text = self._NOISE_CHARS_RE.sub("", text).replace("\r", "\n")
        lines = [self._WHITESPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
        lines = [line for line in lines if line]
        if not lines:
            return ""

        merged = lines[0]
        for line in lines[1:]:
            merged = self._join_wrapped_line(merged, line)
        merged = re.sub(r"\s+([，。；：！？、）】》])", r"\1", merged)
        merged = re.sub(r"([（【《])\s+", r"\1", merged)
        merged = re.sub(r" {2,}", " ", merged)
        return merged.strip()

    def _render_page_text(self, blocks: list[TextBlock], page_width: float) -> str:
        """Render narrative text only.

        Tables stay in ``CleanedPage.tables`` and are intentionally not flattened into
        page text. ``scripts/parse_pdf.py`` emits a dedicated Markdown table preview.
        """
        if not blocks:
            return ""

        parts: list[str] = [blocks[0].text]
        prev = blocks[0]
        for current in blocks[1:]:
            same_column = self._same_column(prev, current, page_width)
            vertical_step = current.bbox[1] - prev.bbox[1]
            line_height = max(
                8.0,
                min(
                    prev.bbox[3] - prev.bbox[1],
                    current.bbox[3] - current.bbox[1],
                ),
            )
            close_line = -0.4 * line_height <= vertical_step <= 1.5 * line_height
            new_semantic_block = self._looks_like_semantic_boundary(
                current.text, current.is_bold
            )
            paragraph_indent = (
                current.bbox[0] - prev.bbox[0] > 12.0
                and prev.text.rstrip().endswith(("。", "！", "？", ";", "；"))
            )

            if same_column and close_line and not new_semantic_block and not paragraph_indent:
                parts[-1] = self._join_wrapped_line(parts[-1], current.text)
            else:
                parts.append(current.text)
            prev = current

        return "\n\n".join(parts)

    @staticmethod
    def _table_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
        def esc(value: str) -> str:
            return value.replace("|", "\\|").replace("\n", "<br>")

        width = max(len(headers), max((len(row) for row in rows), default=0))
        if width == 0:
            return ""

        effective_headers = headers if any(headers) else [f"列{i + 1}" for i in range(width)]
        effective_headers = effective_headers[:width] + [""] * max(
            0, width - len(effective_headers)
        )
        lines = [
            "| " + " | ".join(esc(cell) for cell in effective_headers) + " |",
            "| " + " | ".join("---" for _ in range(width)) + " |",
        ]
        for row in rows:
            normalized = row[:width] + [""] * max(0, width - len(row))
            lines.append("| " + " | ".join(esc(cell) for cell in normalized) + " |")
        return "\n".join(lines)

    @staticmethod
    def _table_to_search_text(
        title: str | None,
        headers: list[str],
        rows: list[list[str]],
    ) -> str:
        parts: list[str] = []
        if title:
            parts.append(title)

        for row in rows:
            fields: list[str] = []
            for index, cell in enumerate(row):
                if not cell:
                    continue
                header = headers[index] if index < len(headers) else ""
                fields.append(f"{header}: {cell}" if header else cell)
            if fields:
                parts.append("；".join(fields))
        return "\n".join(parts)

    @staticmethod
    def _same_column(left: TextBlock, right: TextBlock, page_width: float) -> bool:
        def side(block: TextBlock) -> str:
            width = block.bbox[2] - block.bbox[0]
            if width >= page_width * 0.58:
                return "wide"
            center = (block.bbox[0] + block.bbox[2]) / 2
            return "left" if center < page_width * 0.5 else "right"

        return side(left) == side(right)

    @staticmethod
    def _looks_like_semantic_boundary(text: str, is_bold: bool) -> bool:
        stripped = text.strip()
        if is_bold and len(stripped) <= 80:
            return True
        if stripped.startswith(("要点", "表", "图")):
            return True
        if re.match(r"^\d+(?:\.\d+){0,4}\s+\S+", stripped):
            return True
        return False

    def _find_repeated_margin_patterns(self, document: ParsedDocument) -> set[str]:
        counts: Counter[str] = Counter()
        for page in document.pages:
            seen_on_page: set[str] = set()
            for block in page.blocks:
                y0, y1 = block.bbox[1], block.bbox[3]
                in_margin = (
                    y1 <= page.height * self.top_band_ratio
                    or y0 >= page.height * self.bottom_band_ratio
                )
                if not in_margin:
                    continue
                signature = self._noise_signature(block.text)
                if signature:
                    seen_on_page.add(signature)
            counts.update(seen_on_page)

        threshold = max(
            self.min_repeat_pages,
            int(document.page_count * self.repeat_page_ratio + 0.999),
        )
        return {signature for signature, count in counts.items() if count >= threshold}

    def _is_margin_noise(
        self,
        block: TextBlock,
        page_height: float,
        repeated_patterns: set[str],
    ) -> bool:
        y0, y1 = block.bbox[1], block.bbox[3]
        in_margin = (
            y1 <= page_height * self.top_band_ratio
            or y0 >= page_height * self.bottom_band_ratio
        )
        if not in_margin:
            return False
        clean_text = self.clean_block_text(block.text)
        if self._PAGE_NUMBER_RE.fullmatch(clean_text):
            return True
        return self._noise_signature(block.text) in repeated_patterns

    @staticmethod
    def _noise_signature(text: str) -> str:
        text = text.lower()
        text = re.sub(r"\d+", "#", text)
        text = re.sub(r"\s+", "", text)
        text = re.sub(r"[·•|—–\-_,.;:：，。()（）\[\]【】 ]", "", text)
        return text[:180]

    @staticmethod
    def _join_wrapped_line(previous: str, current: str) -> str:
        if not previous:
            return current
        if previous.endswith("-") and current[:1].isascii() and current[:1].isalpha():
            return previous[:-1] + current
        prev_char = previous[-1]
        curr_char = current[0]
        prev_ascii_word = prev_char.isascii() and (prev_char.isalnum() or prev_char in ")]")
        curr_ascii_word = curr_char.isascii() and (curr_char.isalnum() or curr_char in "([")
        separator = " " if prev_ascii_word and curr_ascii_word else ""
        return previous + separator + current
