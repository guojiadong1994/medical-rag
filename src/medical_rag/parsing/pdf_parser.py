from __future__ import annotations

import asyncio
import re
from pathlib import Path
from statistics import median

import pymupdf

from medical_rag.parsing.models import ParsedDocument, ParsedPage, TableBlock, TextBlock


class PdfParser:
    """Parse born-digital PDFs while preserving page/block geometry.

    Text and tables are parsed separately. Text that belongs to a detected table is
    removed from the ordinary text-block stream so table content is not flattened and
    duplicated. OCR is deliberately not performed here; unusable text-layer pages are
    returned in ``ocr_recommended_pages`` for a later OCR fallback.
    """

    _TABLE_CAPTION_RE = re.compile(r"^\s*(?:表|Table)\s*\d+", re.IGNORECASE)
    _SECTION_RE = re.compile(r"^\s*\d+(?:\.\d+){0,4}\s+\S+")

    def __init__(
        self,
        *,
        min_page_chars: int = 40,
        max_replacement_ratio: float = 0.05,
    ) -> None:
        self.min_page_chars = min_page_chars
        self.max_replacement_ratio = max_replacement_ratio

    async def parse(self, path: Path) -> ParsedDocument:
        return await asyncio.to_thread(self._parse_sync, path)

    def _parse_sync(self, path: Path) -> ParsedDocument:
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"PdfParser only accepts .pdf files: {path}")

        with pymupdf.open(path) as doc:
            pages: list[ParsedPage] = []
            ocr_recommended_pages: list[int] = []

            for page_index, page in enumerate(doc, start=1):
                all_blocks = self._extract_text_blocks(page, page_index)
                raw_char_count = sum(len(block.text) for block in all_blocks)

                tables = self._extract_tables(page, page_index, all_blocks)
                narrative_blocks = self._remove_table_body_blocks(all_blocks, tables)
                table_text_block_count = len(all_blocks) - len(narrative_blocks)
                narrative_blocks = self._order_blocks(
                    narrative_blocks,
                    page.rect.width,
                    page.rect.height,
                )

                text_layer_ok = self._text_layer_is_usable(all_blocks, raw_char_count)
                if not text_layer_ok:
                    ocr_recommended_pages.append(page_index)

                pages.append(
                    ParsedPage(
                        page=page_index,
                        width=round(page.rect.width, 2),
                        height=round(page.rect.height, 2),
                        blocks=narrative_blocks,
                        tables=tables,
                        raw_block_count=len(all_blocks),
                        table_text_block_count=table_text_block_count,
                        raw_char_count=raw_char_count,
                        text_layer_ok=text_layer_ok,
                    )
                )

            metadata = {
                key: str(value or "")
                for key, value in (doc.metadata or {}).items()
                if value is not None
            }

        return ParsedDocument.from_path(
            path,
            page_count=len(pages),
            metadata=metadata,
            pages=pages,
            ocr_recommended_pages=ocr_recommended_pages,
        )

    def _extract_text_blocks(self, page: pymupdf.Page, page_number: int) -> list[TextBlock]:
        page_dict = page.get_text("dict", sort=False)
        result: list[TextBlock] = []

        for block_no, block in enumerate(page_dict.get("blocks", [])):
            if block.get("type") != 0:
                continue

            lines = block.get("lines", [])
            line_texts: list[str] = []
            spans = []

            for line in lines:
                line_spans = line.get("spans", [])
                spans.extend(line_spans)
                line_text = "".join(str(span.get("text", "")) for span in line_spans)
                if line_text.strip():
                    line_texts.append(line_text)

            text = "\n".join(line_texts).strip()
            if not text:
                continue

            bbox = tuple(round(float(v), 2) for v in block.get("bbox", (0, 0, 0, 0)))
            sizes = [float(span.get("size", 0)) for span in spans if span.get("size")]
            font_size = round(median(sizes), 2) if sizes else None
            font_names = [str(span.get("font", "")) for span in spans if span.get("font")]
            font_name = max(set(font_names), key=font_names.count) if font_names else None
            is_bold = any(
                "bold" in str(span.get("font", "")).lower()
                or (int(span.get("flags", 0)) & 16) != 0
                for span in spans
            )

            result.append(
                TextBlock(
                    page=page_number,
                    block_no=block_no,
                    bbox=bbox,  # type: ignore[arg-type]
                    text=text,
                    font_size=font_size,
                    font_name=font_name,
                    is_bold=is_bold,
                )
            )

        return self._merge_same_line_fragments(result, page.rect.width)

    def _extract_tables(
        self,
        page: pymupdf.Page,
        page_number: int,
        text_blocks: list[TextBlock],
    ) -> list[TableBlock]:
        """Extract tables with a high-precision pass plus a caption-guided fallback.

        1. ``lines_strict`` handles ordinary ruled tables with low false positives.
        2. If a caption like ``表6`` has no nearby detected table, a localized ``text``
           strategy is used beneath that caption. This is important for borderless
           medical-guideline tables while avoiding a full-page text-table scan.
        """

        extracted: list[TableBlock] = []

        try:
            finder = page.find_tables(strategy="lines_strict")
            for table in finder.tables:
                block = self._table_to_block(table, page_number, len(extracted), text_blocks)
                if block is not None and not self._is_duplicate_table(block, extracted):
                    extracted.append(block)
        except Exception:
            # Table extraction must not make ordinary PDF text parsing fail.
            pass

        caption_blocks = [
            block for block in text_blocks if self._TABLE_CAPTION_RE.match(block.text.strip())
        ]

        for caption in caption_blocks:
            caption = self._tighten_caption_block(page, caption)
            if self._caption_already_has_table(caption, extracted):
                continue

            clip = self._table_clip_below_caption(page, caption, text_blocks)
            if clip.height <= 20:
                continue

            try:
                finder = page.find_tables(
                    clip=clip,
                    strategy="text",
                    min_words_vertical=2,
                    min_words_horizontal=1,
                )
            except Exception:
                continue

            candidates: list[TableBlock] = []
            for table in finder.tables:
                block = self._table_to_block(table, page_number, len(extracted), text_blocks)
                if block is None:
                    continue
                if block.bbox[1] + 3 < caption.bbox[3]:
                    continue
                candidates.append(block)

            if not candidates:
                continue

            # Prefer the first plausible table directly below the caption.
            candidates.sort(key=lambda item: (item.bbox[1], -(item.bbox[2] - item.bbox[0])))
            candidate = candidates[0]
            candidate = candidate.model_copy(
                update={
                    "table_no": len(extracted),
                    "title": self._clean_cell(caption.text),
                }
            )
            if not self._is_duplicate_table(candidate, extracted):
                extracted.append(candidate)

        extracted.sort(key=lambda table: (table.bbox[1], table.bbox[0]))
        return [table.model_copy(update={"table_no": i}) for i, table in enumerate(extracted)]


    def _tighten_caption_block(
        self,
        page: pymupdf.Page,
        caption: TextBlock,
    ) -> TextBlock:
        """Reduce a multi-line PDF text block to the actual table-caption line bbox."""
        first_line = caption.text.splitlines()[0].strip()
        if not first_line:
            return caption
        try:
            matches = page.search_for(first_line)
        except Exception:
            matches = []
        if not matches:
            return caption.model_copy(update={"text": first_line})

        original_y = caption.bbox[1]
        best = min(matches, key=lambda rect: abs(rect.y0 - original_y))
        bbox = tuple(round(float(v), 2) for v in best)
        return caption.model_copy(update={"text": first_line, "bbox": bbox})

    def _table_to_block(
        self,
        table: object,
        page_number: int,
        table_no: int,
        text_blocks: list[TextBlock],
    ) -> TableBlock | None:
        try:
            bbox = tuple(round(float(v), 2) for v in table.bbox)  # type: ignore[attr-defined]
            raw_rows = table.extract()[:]  # type: ignore[attr-defined]
            header = table.header  # type: ignore[attr-defined]
            header_names = list(getattr(header, "names", []) or [])
            header_external = bool(getattr(header, "external", False))
        except Exception:
            return None

        rows = [
            [self._clean_cell(cell) for cell in row]
            for row in raw_rows
            if row is not None
        ]
        rows = [row for row in rows if any(cell for cell in row)]
        if len(rows) < 2:
            return None

        col_count = max((len(row) for row in rows), default=0)
        if col_count < 2:
            return None

        rows = [self._normalize_row(row, col_count) for row in rows]
        headers = self._normalize_row(
            [self._clean_cell(value) for value in header_names],
            col_count,
        )

        if not any(headers):
            headers = rows[0]
            data_rows = rows[1:]
        elif not header_external and rows and self._rows_equal(rows[0], headers):
            data_rows = rows[1:]
        else:
            data_rows = rows

        if not data_rows:
            return None

        non_empty_cells = sum(bool(cell) for row in data_rows for cell in row)
        total_cells = max(len(data_rows) * col_count, 1)
        if non_empty_cells < 4 or non_empty_cells / total_cells < 0.35:
            return None

        title = self._find_table_title(text_blocks, bbox)
        markdown = self._table_to_markdown(headers, data_rows)
        search_text = self._table_to_search_text(title, headers, data_rows)

        return TableBlock(
            page=page_number,
            table_no=table_no,
            bbox=bbox,  # type: ignore[arg-type]
            title=title,
            headers=headers,
            rows=data_rows,
            markdown=markdown,
            search_text=search_text,
        )

    def _table_clip_below_caption(
        self,
        page: pymupdf.Page,
        caption: TextBlock,
        blocks: list[TextBlock],
    ) -> pymupdf.Rect:
        start_y = min(page.rect.height, caption.bbox[3] + 1.0)
        bottom_y = min(page.rect.height * 0.94, start_y + page.rect.height * 0.48)

        for block in sorted(blocks, key=lambda item: item.bbox[1]):
            if block.bbox[1] <= start_y + 10:
                continue
            text = block.text.strip()
            is_boundary = (
                text.startswith(("注:", "注：", "图"))
                or self._TABLE_CAPTION_RE.match(text) is not None
                or self._SECTION_RE.match(text) is not None
                or text.startswith("要点")
            )
            if is_boundary:
                bottom_y = min(bottom_y, max(start_y + 20, block.bbox[1] - 2))
                break

        return pymupdf.Rect(0, start_y, page.rect.width, bottom_y)

    @staticmethod
    def _clean_cell(value: object) -> str:
        if value is None:
            return ""
        text = str(value).replace("\r", "\n")
        text = re.sub(r"[ \t\u3000]+", " ", text)
        text = re.sub(r"\s*\n\s*", " ", text)
        return text.strip()

    @staticmethod
    def _normalize_row(row: list[str], col_count: int) -> list[str]:
        if len(row) < col_count:
            return row + [""] * (col_count - len(row))
        return row[:col_count]

    @staticmethod
    def _rows_equal(left: list[str], right: list[str]) -> bool:
        normalize = lambda row: [re.sub(r"\s+", "", cell) for cell in row]
        return normalize(left) == normalize(right)

    def _find_table_title(
        self,
        blocks: list[TextBlock],
        table_bbox: tuple[float, float, float, float],
    ) -> str | None:
        candidates: list[tuple[float, TextBlock]] = []
        table_y0 = table_bbox[1]
        for block in blocks:
            text = block.text.strip()
            if not self._TABLE_CAPTION_RE.match(text):
                continue
            gap = table_y0 - block.bbox[3]
            if -3 <= gap <= 90:
                candidates.append((abs(gap), block))

        if not candidates:
            return None
        _, best = min(candidates, key=lambda item: item[0])
        return self._clean_cell(best.text.splitlines()[0])

    @staticmethod
    def _table_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
        def esc(value: str) -> str:
            return value.replace("|", "\\|").replace("\n", "<br>")

        width = max(len(headers), max((len(row) for row in rows), default=0))
        if width == 0:
            return ""
        effective_headers = headers if any(headers) else [f"列{i + 1}" for i in range(width)]
        effective_headers = effective_headers[:width] + [""] * max(0, width - len(effective_headers))

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
    def _caption_already_has_table(caption: TextBlock, tables: list[TableBlock]) -> bool:
        for table in tables:
            vertical_gap = table.bbox[1] - caption.bbox[3]
            if -5 <= vertical_gap <= 120:
                return True
        return False

    @staticmethod
    def _is_duplicate_table(candidate: TableBlock, existing: list[TableBlock]) -> bool:
        return any(PdfParser._rect_iou(candidate.bbox, table.bbox) >= 0.65 for table in existing)

    @staticmethod
    def _rect_iou(
        left: tuple[float, float, float, float],
        right: tuple[float, float, float, float],
    ) -> float:
        x0 = max(left[0], right[0])
        y0 = max(left[1], right[1])
        x1 = min(left[2], right[2])
        y1 = min(left[3], right[3])
        intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
        if intersection <= 0:
            return 0.0
        left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
        right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
        union = left_area + right_area - intersection
        return intersection / union if union > 0 else 0.0

    def _remove_table_body_blocks(
        self,
        blocks: list[TextBlock],
        tables: list[TableBlock],
    ) -> list[TextBlock]:
        if not tables:
            return blocks
        return [
            block
            for block in blocks
            if not any(self._block_mostly_inside_table(block, table) for table in tables)
        ]

    @staticmethod
    def _block_mostly_inside_table(block: TextBlock, table: TableBlock) -> bool:
        bx0, by0, bx1, by1 = block.bbox
        tx0, ty0, tx1, ty1 = table.bbox
        ix0, iy0 = max(bx0, tx0), max(by0, ty0)
        ix1, iy1 = min(bx1, tx1), min(by1, ty1)
        intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
        block_area = max(1.0, (bx1 - bx0) * (by1 - by0))
        return intersection / block_area >= 0.55

    def _merge_same_line_fragments(
        self, blocks: list[TextBlock], page_width: float
    ) -> list[TextBlock]:
        """Merge font/subset fragments that visually form one printed line."""
        if not blocks:
            return []

        def side(block: TextBlock) -> str:
            width = block.bbox[2] - block.bbox[0]
            if width >= page_width * 0.58:
                return "wide"
            center = (block.bbox[0] + block.bbox[2]) / 2
            return "left" if center < page_width * 0.5 else "right"

        clusters: list[dict[str, object]] = []
        for block in sorted(blocks, key=lambda b: ((b.bbox[1] + b.bbox[3]) / 2, b.bbox[0])):
            block_side = side(block)
            if block_side == "wide":
                clusters.append({"side": "wide", "blocks": [block]})
                continue

            matched = None
            for cluster in reversed(clusters[-12:]):
                if cluster["side"] != block_side:
                    continue
                items = cluster["blocks"]
                assert isinstance(items, list)
                ref = items[0]
                assert isinstance(ref, TextBlock)
                overlap = max(
                    0.0,
                    min(ref.bbox[3], block.bbox[3]) - max(ref.bbox[1], block.bbox[1]),
                )
                min_height = max(
                    1.0,
                    min(
                        ref.bbox[3] - ref.bbox[1],
                        block.bbox[3] - block.bbox[1],
                    ),
                )
                center_delta = abs(
                    (ref.bbox[1] + ref.bbox[3]) / 2
                    - (block.bbox[1] + block.bbox[3]) / 2
                )
                if overlap / min_height >= 0.5 or center_delta <= 3.0:
                    matched = cluster
                    break

            if matched is None:
                clusters.append({"side": block_side, "blocks": [block]})
            else:
                items = matched["blocks"]
                assert isinstance(items, list)
                items.append(block)

        merged: list[TextBlock] = []
        for cluster in clusters:
            items = cluster["blocks"]
            assert isinstance(items, list)
            line_blocks = sorted(items, key=lambda b: b.bbox[0])
            current = line_blocks[0]
            for block in line_blocks[1:]:
                x_gap = block.bbox[0] - current.bbox[2]
                if -2.0 <= x_gap <= 10.0:
                    separator = self._inline_separator(current.text, block.text)
                    font_sizes = [
                        value
                        for value in (current.font_size, block.font_size)
                        if value is not None
                    ]
                    current = current.model_copy(
                        update={
                            "text": current.text.rstrip() + separator + block.text.lstrip(),
                            "bbox": (
                                min(current.bbox[0], block.bbox[0]),
                                min(current.bbox[1], block.bbox[1]),
                                max(current.bbox[2], block.bbox[2]),
                                max(current.bbox[3], block.bbox[3]),
                            ),
                            "font_size": max(font_sizes) if font_sizes else None,
                            "is_bold": current.is_bold or block.is_bold,
                        }
                    )
                else:
                    merged.append(current)
                    current = block
            merged.append(current)
        return merged

    @staticmethod
    def _inline_separator(left: str, right: str) -> str:
        if not left or not right:
            return ""
        lch, rch = left[-1], right[0]
        if lch == "-" and rch.isascii() and rch.isalpha():
            return ""
        if lch.isascii() and rch.isascii() and lch.isalnum() and rch.isalnum():
            return " "
        return ""

    def _text_layer_is_usable(self, blocks: list[TextBlock], raw_char_count: int) -> bool:
        if raw_char_count < self.min_page_chars:
            return False
        text = "".join(block.text for block in blocks)
        if not text:
            return False
        replacement_count = sum(text.count(ch) for ch in ("�", "\ufffe", "\uffff"))
        return replacement_count / max(len(text), 1) <= self.max_replacement_ratio

    def _order_blocks(
        self,
        blocks: list[TextBlock],
        page_width: float,
        page_height: float,
    ) -> list[TextBlock]:
        """Approximate human reading order for one/two-column academic PDFs."""
        if len(blocks) <= 2:
            return self._assign_order(sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0])))

        narrow = [b for b in blocks if (b.bbox[2] - b.bbox[0]) < page_width * 0.58]
        left = [b for b in narrow if (b.bbox[0] + b.bbox[2]) / 2 < page_width * 0.5]
        right = [b for b in narrow if (b.bbox[0] + b.bbox[2]) / 2 >= page_width * 0.5]

        if len(left) < 2 or len(right) < 2:
            return self._assign_order(sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0])))

        wide = sorted(
            [b for b in blocks if b not in narrow],
            key=lambda b: (b.bbox[1], b.bbox[0]),
        )
        ordered: list[TextBlock] = []
        remaining = set(range(len(blocks)))
        index_by_id = {id(block): idx for idx, block in enumerate(blocks)}
        top = -1.0

        for separator in wide:
            sep_center = (separator.bbox[1] + separator.bbox[3]) / 2
            segment = [
                block
                for block in narrow
                if index_by_id[id(block)] in remaining
                and top < (block.bbox[1] + block.bbox[3]) / 2 < sep_center
            ]
            ordered.extend(self._sort_two_columns(segment, page_width))
            for block in segment:
                remaining.discard(index_by_id[id(block)])
            if index_by_id[id(separator)] in remaining:
                ordered.append(separator)
                remaining.discard(index_by_id[id(separator)])
            top = sep_center

        tail = [blocks[idx] for idx in remaining]
        ordered.extend(self._sort_two_columns(tail, page_width))
        return self._assign_order(ordered)

    @staticmethod
    def _sort_two_columns(blocks: list[TextBlock], page_width: float) -> list[TextBlock]:
        left = [b for b in blocks if (b.bbox[0] + b.bbox[2]) / 2 < page_width * 0.5]
        right = [b for b in blocks if b not in left]
        return sorted(left, key=lambda b: (b.bbox[1], b.bbox[0])) + sorted(
            right, key=lambda b: (b.bbox[1], b.bbox[0])
        )

    @staticmethod
    def _assign_order(blocks: list[TextBlock]) -> list[TextBlock]:
        for order, block in enumerate(blocks):
            block.reading_order = order
        return blocks
