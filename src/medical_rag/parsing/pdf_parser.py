from __future__ import annotations

import asyncio
import re
from pathlib import Path
from statistics import median

import fitz

from medical_rag.parsing.models import ParsedDocument, ParsedPage, TextBlock


class PdfParser:
    """Parse born-digital PDFs while preserving page/block geometry.

    OCR is deliberately not performed here. Pages whose text layer looks unusable are
    returned in ``ocr_recommended_pages`` so an OCR fallback can be plugged in later.
    """

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

        with fitz.open(path) as doc:
            pages: list[ParsedPage] = []
            ocr_recommended_pages: list[int] = []

            for page_index, page in enumerate(doc, start=1):
                blocks = self._extract_text_blocks(page, page_index)
                blocks = self._order_blocks(blocks, page.rect.width, page.rect.height)
                raw_char_count = sum(len(block.text) for block in blocks)
                text_layer_ok = self._text_layer_is_usable(blocks, raw_char_count)
                if not text_layer_ok:
                    ocr_recommended_pages.append(page_index)

                pages.append(
                    ParsedPage(
                        page=page_index,
                        width=round(page.rect.width, 2),
                        height=round(page.rect.height, 2),
                        blocks=blocks,
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

    def _extract_text_blocks(self, page: fitz.Page, page_number: int) -> list[TextBlock]:
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

    def _merge_same_line_fragments(
        self, blocks: list[TextBlock], page_width: float
    ) -> list[TextBlock]:
        """Merge font/subset fragments that visually form one printed line.

        We first cluster by column and vertical overlap, then sort each visual line by x.
        This avoids a common PDF extraction bug where an English continuation such as
        ``sin`` is emitted after the rest of the line because its y-coordinate differs by
        one or two points.
        """
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
        """Approximate human reading order for one/two-column academic PDFs.

        Wide blocks are treated as separators (title/table/caption-like regions). Within
        each vertical segment, left-column blocks are read top-to-bottom before right-column
        blocks. If a two-column layout is not detected, ordinary y/x ordering is used.
        """
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
