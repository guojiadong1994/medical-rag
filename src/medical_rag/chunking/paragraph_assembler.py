from __future__ import annotations

import re

from medical_rag.parsing.models import TextBlock


class ParagraphAssembler:
    """Merge PDF visual-line blocks into paragraph-like semantic blocks.

    PDF extractors often return one visual line (or a few lines) as one ``TextBlock``.
    Chunking those blocks directly creates false paragraph boundaries such as
    ``高血压防治指`` / ``南``. This assembler uses geometry plus conservative textual
    cues to join wrapped continuations while preserving headings, bullets and lists.
    """

    _HEADING_RE = re.compile(r"^\s*\d+(?:\.\d+){0,4}\s+\S+")
    _CHAPTER_RE = re.compile(r"^\s*第[一二三四五六七八九十百0-9]+[章节篇部]")
    _KEYPOINT_RE = re.compile(r"^\s*要点\s*\d+")
    _TABLE_OR_FIGURE_RE = re.compile(r"^\s*(?:表|图|Table|Figure)\s*\d+", re.IGNORECASE)
    _BULLET_RE = re.compile(
        r"^\s*(?:[·•▪◦●○◆◇▶►]|[-–—]\s+|[（(]\d{1,3}[)）]|\d{1,3}[、)])"
    )
    _SENTENCE_END = ("。", "！", "？", "!", "?", "；", ";")

    def assemble(self, blocks: list[TextBlock], page_width: float) -> list[TextBlock]:
        ordered = sorted(blocks, key=lambda block: block.reading_order)
        if not ordered:
            return []

        result: list[TextBlock] = []
        current = self._normalize_block(ordered[0])
        previous_physical = current

        for raw in ordered[1:]:
            block = self._normalize_block(raw)
            if not block.text:
                continue

            if self._should_join(previous_physical, block, page_width):
                current = self._merge_blocks(current, block)
            else:
                if current.text:
                    result.append(current)
                current = block

            previous_physical = block

        if current.text:
            result.append(current)

        for order, block in enumerate(result):
            block.reading_order = order
        return result

    @classmethod
    def _should_join(cls, previous: TextBlock, current: TextBlock, page_width: float) -> bool:
        if not previous.text or not current.text:
            return False
        if not cls._same_column(previous, current, page_width):
            return False
        if cls._is_semantic_start(current):
            return False
        if cls._is_heading_like(previous):
            return False

        # A full sentence/semicolon is a safe semantic boundary. Keeping it as a
        # paragraph boundary is preferable to accidentally merging two paragraphs.
        if previous.text.rstrip().endswith(cls._SENTENCE_END):
            return False

        prev_height = max(1.0, previous.bbox[3] - previous.bbox[1])
        curr_height = max(1.0, current.bbox[3] - current.bbox[1])
        line_height = max(8.0, min(prev_height, curr_height))
        vertical_step = current.bbox[1] - previous.bbox[1]

        # Same-line fragments can have a slightly negative delta; ordinary visual-line
        # wrapping usually advances by roughly one line height.
        if not (-0.45 * line_height <= vertical_step <= 1.8 * line_height):
            return False

        # A visible first-line indent after a complete clause is more likely a new
        # paragraph. We intentionally do not apply this when the previous line is mid-
        # sentence, because Chinese PDF wraps often have small x jitter.
        x_indent = current.bbox[0] - previous.bbox[0]
        if x_indent > 14.0 and previous.text.rstrip().endswith(("，", ",", "：", ":")):
            return False

        return True

    @classmethod
    def _is_semantic_start(cls, block: TextBlock) -> bool:
        text = block.text.strip()
        if not text:
            return False
        if block.is_bold and len(text) <= 80:
            return True
        return bool(
            cls._HEADING_RE.match(text)
            or cls._CHAPTER_RE.match(text)
            or cls._KEYPOINT_RE.match(text)
            or cls._TABLE_OR_FIGURE_RE.match(text)
            or cls._BULLET_RE.match(text)
        )

    @classmethod
    def _is_heading_like(cls, block: TextBlock) -> bool:
        text = block.text.strip()
        if not text:
            return False
        if block.is_bold and len(text) <= 80:
            return True
        return bool(
            cls._HEADING_RE.match(text)
            or cls._CHAPTER_RE.match(text)
            or cls._KEYPOINT_RE.match(text)
        )

    @classmethod
    def _normalize_block(cls, block: TextBlock) -> TextBlock:
        raw = block.text.replace("\r", "\n")
        lines = [re.sub(r"[\t\u3000]+", " ", line).strip() for line in raw.split("\n")]
        lines = [line for line in lines if line]
        if not lines:
            return block.model_copy(update={"text": ""})

        text = lines[0]
        for line in lines[1:]:
            text = cls._join_wrapped_line(text, line)
        text = re.sub(r" {2,}", " ", text).strip()
        return block.model_copy(update={"text": text})

    @staticmethod
    def _same_column(left: TextBlock, right: TextBlock, page_width: float) -> bool:
        def side(block: TextBlock) -> str:
            width = block.bbox[2] - block.bbox[0]
            if width >= page_width * 0.58:
                return "wide"
            center = (block.bbox[0] + block.bbox[2]) / 2
            return "left" if center < page_width * 0.5 else "right"

        return side(left) == side(right)

    @classmethod
    def _merge_blocks(cls, left: TextBlock, right: TextBlock) -> TextBlock:
        text = cls._join_wrapped_line(left.text.rstrip(), right.text.lstrip())
        sizes = [value for value in (left.font_size, right.font_size) if value is not None]
        return left.model_copy(
            update={
                "text": text,
                "bbox": (
                    min(left.bbox[0], right.bbox[0]),
                    min(left.bbox[1], right.bbox[1]),
                    max(left.bbox[2], right.bbox[2]),
                    max(left.bbox[3], right.bbox[3]),
                ),
                "font_size": max(sizes) if sizes else None,
                "is_bold": left.is_bold or right.is_bold,
            }
        )

    @staticmethod
    def _join_wrapped_line(previous: str, current: str) -> str:
        if not previous:
            return current
        if not current:
            return previous
        if previous.endswith("-") and current[:1].isascii() and current[:1].isalpha():
            return previous[:-1] + current

        left = previous[-1]
        right = current[0]
        left_ascii_word = left.isascii() and (left.isalnum() or left in ")]%")
        right_ascii_word = right.isascii() and (right.isalnum() or right in "([")
        separator = " " if left_ascii_word and right_ascii_word else ""
        return previous + separator + current
