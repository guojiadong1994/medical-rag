from __future__ import annotations

import re
from dataclasses import dataclass

from medical_rag.parsing.models import TextBlock


@dataclass(slots=True)
class HeadingMatch:
    level: int
    title: str
    body: str = ""


@dataclass(slots=True)
class EmbeddedHeadingMatch:
    prefix: str
    heading: HeadingMatch


class SectionDetector:
    """Conservative heading detector for Chinese medical guidelines.

    V1.2 intentionally prefers *missing* a weak heading over inventing a wrong one.
    Wrong headings are especially harmful in RAG because section text is prepended to
    ``embedding_text`` and therefore changes retrieval semantics.

    Main rules:
    - dotted headings (``4.5`` / ``4.5.1``) are strong evidence;
    - plain integer headings (``1 我国人群...``) need bold metadata or a strongly
      title-shaped Chinese phrase;
    - numeric thresholds / percentiles / ratios are rejected as headings;
    - table-like labels such as ``1 推荐类别`` are rejected unless typography is strong;
    - glued trailing headings are recovered only when evidence is strong enough.
    """

    _NUMBERED_RE = re.compile(r"^(?P<number>\d+(?:\.\d+){0,4})\s+(?P<rest>\S.*)$")
    _CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百0-9]+[章节篇部])\s*(.*)$")
    _KEYPOINT_RE = re.compile(r"^(要点\s*\d+)\s*(.*)$")
    _TRAILING_DOTTED_RE = re.compile(
        r"(?P<prefix>.+?)(?<![\d.])"
        r"(?P<number>\d+(?:\.\d+){1,4})\s+"
        r"(?P<title>[\u4e00-\u9fffA-Za-z][^。！？!?；;]{2,50})$"
    )
    _TRAILING_PLAIN_RE = re.compile(
        r"(?P<prefix>.+?[。！？；;])\s*"
        r"(?P<number>\d{1,2})\s+"
        r"(?P<title>[\u4e00-\u9fff][^。！？!?；;,，]{7,35})$"
    )
    _TABLE_LIKE_TITLES = {
        "推荐类别",
        "证据等级",
        "级别定义",
        "推荐类别定义建议使用的表述",
        "分类",
        "测量方式",
    }

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
            if len(text) <= self.max_title_chars * 2 and not self._looks_like_long_body(suffix):
                title, body = self._split_title_and_body(suffix)
                if title:
                    return HeadingMatch(
                        level=2,
                        title=keypoint.group(1) + (f" {title}" if title else ""),
                        body=body,
                    )

        return self._detect_numbered(text, block)

    def detect_trailing_embedded(self, block: TextBlock) -> EmbeddedHeadingMatch | None:
        """Recover a heading accidentally glued to preceding body text.

        V1.2 is deliberately stricter than V1.1. Dotted section numbers are accepted
        because they are strong structural evidence. Plain integers are accepted only
        after a real sentence boundary, which avoids turning numeric body fragments into
        hundreds of fake sections.
        """

        text = self._normalize(block.text)
        if len(text) < 16:
            return None

        match = self._TRAILING_DOTTED_RE.search(text)
        force_plain = False
        if match is None:
            match = self._TRAILING_PLAIN_RE.search(text)
            force_plain = True
        if match is None:
            return None

        prefix = match.group("prefix").strip()
        number = match.group("number")
        title = match.group("title").strip()
        if len(prefix) < 8 or not self._title_shape_ok(title):
            return None

        synthetic = block.model_copy(update={"text": f"{number} {title}"})
        heading = self._detect_numbered(
            f"{number} {title}",
            synthetic,
            force_plain=force_plain,
        )
        if heading is None:
            return None
        return EmbeddedHeadingMatch(prefix=prefix, heading=heading)

    def _detect_numbered(
        self,
        text: str,
        block: TextBlock,
        *,
        force_plain: bool = False,
    ) -> HeadingMatch | None:
        match = self._NUMBERED_RE.match(text)
        if not match:
            return None

        number = match.group("number")
        rest = match.group("rest").strip()
        level = number.count(".") + 1
        dotted = "." in number

        if self._looks_like_numeric_body(rest):
            return None

        # Dotted numbering is strong structural evidence. PDF extraction frequently
        # glues the first body sentence after a short title, e.g.
        # ``4.5.1 按血压水平分类和分级 目前,我国采用正常...``.
        if dotted:
            title, body = self._split_title_and_body(rest)
            if title and self._title_shape_ok(title):
                return HeadingMatch(level=level, title=f"{number} {title}", body=body)
            return None

        if not self._plain_integer_number_ok(number):
            return None

        title, body = self._split_title_and_body(rest)
        if not title or not self._plain_integer_title_ok(title):
            return None

        strong_typography = block.is_bold
        strong_text_shape = (
            len(title) >= 7
            and len(title) <= 32
            and self._mostly_cjk(title, minimum_ratio=0.72)
            and not body
        )
        if not (force_plain or strong_typography or strong_text_shape):
            return None

        # Short table labels are common false positives in medical PDFs.
        if title in self._TABLE_LIKE_TITLES and not strong_typography:
            return None

        # Non-bold plain-integer headings with an attached body are too ambiguous.
        if body and not (strong_typography or force_plain):
            return None

        return HeadingMatch(level=1, title=f"{number} {title}", body=body)

    def _split_title_and_body(self, rest: str) -> tuple[str, str]:
        rest = rest.strip()
        if not rest:
            return "", ""

        # If there is exactly the normal Chinese section-title token followed by body,
        # take the first token as title. This fixes titles such as
        # ``4.5.1 按血压水平分类和分级 目前,我国采用正常...``.
        if " " in rest:
            first, remainder = rest.split(" ", 1)
            first = first.strip()
            remainder = remainder.strip()
            if (
                2 <= len(first) <= 30
                and self._title_shape_ok(first)
                and remainder
                and self._looks_body_like(remainder)
            ):
                return first, remainder

        if len(rest) <= self.max_title_chars and self._title_shape_ok(rest):
            return rest, ""

        # Fall back to a first-token boundary for long extraction artifacts.
        first, sep, remainder = rest.partition(" ")
        if sep and 2 <= len(first) <= 30 and self._title_shape_ok(first):
            return first, remainder.strip()
        return "", ""

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"[ \t\u3000]+", " ", text.replace("\n", " ")).strip()

    @staticmethod
    def _looks_like_sentence(text: str) -> bool:
        if len(text) > 80:
            return True
        return bool(re.search(r"[。！？；;]", text))

    @staticmethod
    def _looks_like_long_body(text: str) -> bool:
        return len(text) > 90 or bool(re.search(r"[。！？；;].{8,}", text))

    @classmethod
    def _looks_body_like(cls, text: str) -> bool:
        if len(text) >= 18:
            return True
        return bool(re.search(r"[,，:：。！？；;()（）\[\]<>≥≤=%/]", text))

    @staticmethod
    def _plain_integer_number_ok(number: str) -> bool:
        try:
            value = int(number)
        except ValueError:
            return False
        return 1 <= value <= 30

    @classmethod
    def _plain_integer_title_ok(cls, text: str) -> bool:
        if not cls._title_shape_ok(text):
            return False
        if cls._looks_like_numeric_body(text):
            return False
        if text.count(",") + text.count("，"):
            return False
        return True

    @staticmethod
    def _looks_like_numeric_body(text: str) -> bool:
        return bool(
            re.search(
                r"[<>≥≤=%/]"
                r"|\bP\s*\d"
                r"|\d\s*[~～-]\s*\d"
                r"|\d+\s*mmHg",
                text,
                re.IGNORECASE,
            )
        )

    @classmethod
    def _title_shape_ok(cls, text: str) -> bool:
        text = text.strip()
        if not (2 <= len(text) <= 60):
            return False
        if re.search(r"[。！？!?；;]", text):
            return False
        if text.count(",") + text.count("，") >= 2:
            return False
        return cls._mostly_cjk_or_medical(text)

    @staticmethod
    def _mostly_cjk(text: str, *, minimum_ratio: float) -> bool:
        if not text:
            return False
        cjk = sum("\u4e00" <= ch <= "\u9fff" for ch in text)
        return cjk / len(text) >= minimum_ratio

    @staticmethod
    def _mostly_cjk_or_medical(text: str) -> bool:
        if not text:
            return False
        allowed = sum(
            1
            for ch in text
            if "\u4e00" <= ch <= "\u9fff"
            or ch.isascii()
            and (ch.isalpha() or ch.isdigit() or ch in "-_/()（）+%")
            or ch in "、·—"
        )
        return allowed / len(text) >= 0.8
