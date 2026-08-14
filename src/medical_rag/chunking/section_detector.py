from __future__ import annotations

import re
from dataclasses import dataclass

from medical_rag.parsing.models import TextBlock


@dataclass(slots=True)
class HeadingMatch:
    level: int
    title: str
    body: str = ""


class SectionDetector:
    """Heuristic heading detector for Chinese medical guidelines.

    The detector intentionally stays conservative. It recognizes numbered headings such
    as ``4.5.1 按血压水平分类和分级`` and can also split a common PDF artifact where a
    heading and the first sentence are merged into the same text block.
    """

    _NUMBERED_RE = re.compile(r"^(?P<number>\d+(?:\.\d+){0,4})\s*(?P<rest>\S.*)$")
    _CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百0-9]+[章节篇部])\s*(.*)$")
    _KEYPOINT_RE = re.compile(r"^(要点\s*\d+)\s*(.*)$")

    def __init__(self, *, max_title_chars: int = 60) -> None:
        self.max_title_chars = max_title_chars

    def detect(self, block: TextBlock) -> HeadingMatch | None:
        text = self._normalize(block.text)
        if not text:
            return None

        chapter = self._CHAPTER_RE.match(text)
        if chapter and len(text) <= self.max_title_chars:
            suffix = chapter.group(2).strip()
            title = chapter.group(1) + (f" {suffix}" if suffix else "")
            return HeadingMatch(level=1, title=title)

        keypoint = self._KEYPOINT_RE.match(text)
        if keypoint:
            suffix = keypoint.group(2).strip()
            if len(text) <= self.max_title_chars * 2:
                title = keypoint.group(1) + (f" {suffix}" if suffix else "")
                return HeadingMatch(level=2, title=title)
            for delimiter in ("·", "•"):
                if delimiter in suffix:
                    title_part, body = suffix.split(delimiter, 1)
                    title_part = title_part.strip()
                    if 2 <= len(title_part) <= self.max_title_chars:
                        return HeadingMatch(
                            level=2,
                            title=f"{keypoint.group(1)} {title_part}",
                            body=(delimiter + body).strip(),
                        )

        match = self._NUMBERED_RE.match(text)
        if not match:
            return None

        number = match.group("number")
        rest = match.group("rest").strip()
        level = number.count(".") + 1

        # Dotted numbering (4.2 / 4.5.1) is strong evidence. Plain integers are only
        # treated as headings when typography also suggests a heading.
        strong_number = "." in number
        if not strong_number and not block.is_bold:
            return None

        # Normal case: the whole block is a short heading.
        if len(rest) <= self.max_title_chars and not self._looks_like_sentence(rest):
            return HeadingMatch(level=level, title=f"{number} {rest}")

        # Common PDF artifact: "4.2 体格检查 仔细的体格检查有助于……". Chinese section
        # titles normally have no internal spaces, so the first token is a useful V1
        # boundary while keeping the body available for chunking.
        first, sep, remainder = rest.partition(" ")
        if (
            sep
            and 2 <= len(first) <= 30
            and self._mostly_cjk_or_medical(first)
            and remainder.strip()
        ):
            return HeadingMatch(
                level=level,
                title=f"{number} {first}",
                body=remainder.strip(),
            )

        return None

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[ \t\u3000]+", " ", text.replace("\n", " ")).strip()

    @staticmethod
    def _looks_like_sentence(text: str) -> bool:
        if len(text) > 80:
            return True
        return bool(re.search(r"[。！？；;]", text))

    @staticmethod
    def _mostly_cjk_or_medical(text: str) -> bool:
        if not text:
            return False
        allowed = sum(
            1
            for ch in text
            if "\u4e00" <= ch <= "\u9fff"
            or ch.isascii()
            and (ch.isalpha() or ch.isdigit() or ch in "-_/()（）")
        )
        return allowed / len(text) >= 0.8
