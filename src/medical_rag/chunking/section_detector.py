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

    V1.1 extends the original detector in two directions:
    - short plain-integer headings (``1 我国人群高血压流行及防控现状``) no longer
      require bold metadata when the text shape itself strongly resembles a title;
    - a trailing heading accidentally glued to preceding PDF text can be recovered,
      e.g. ``……非随机对照研究1 我国人群高血压流行及防控现状``.
    """

    _NUMBERED_RE = re.compile(r"^(?P<number>\d+(?:\.\d+){0,4})\s+(?P<rest>\S.*)$")
    _CHAPTER_RE = re.compile(r"^(第[一二三四五六七八九十百0-9]+[章节篇部])\s*(.*)$")
    _KEYPOINT_RE = re.compile(r"^(要点\s*\d+)\s*(.*)$")
    _TRAILING_NUMBERED_RE = re.compile(
        r"(?P<prefix>.+?)(?<![\d.])"
        r"(?P<number>\d+(?:\.\d+){0,4})\s+"
        r"(?P<title>[\u4e00-\u9fffA-Za-z][^。！？!?；;]{2,60})$"
    )

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
            if len(text) <= self.max_title_chars * 2 and not self._looks_like_long_body(suffix):
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

        return self._detect_numbered(text, block)

    def detect_trailing_embedded(self, block: TextBlock) -> EmbeddedHeadingMatch | None:
        """Recover a heading that was glued to the end of a preceding PDF block.

        The rule is intentionally strict for plain integers: the prefix must be non-trivial
        and the trailing title must be long enough to avoid treating short table labels such
        as ``1 推荐类别`` as document sections.
        """

        text = self._normalize(block.text)
        if len(text) < 16:
            return None

        match = self._TRAILING_NUMBERED_RE.search(text)
        if not match:
            return None

        prefix = match.group("prefix").strip()
        number = match.group("number")
        title = match.group("title").strip()
        if len(prefix) < 10:
            return None

        dotted = "." in number
        if not dotted and len(title) < 6:
            return None
        if not self._title_shape_ok(title):
            return None

        synthetic = block.model_copy(update={"text": f"{number} {title}"})
        heading = self._detect_numbered(f"{number} {title}", synthetic, force_plain=True)
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
        strong_number = "." in number

        plain_title_evidence = (
            force_plain
            or block.is_bold
            or (
                self._plain_integer_number_ok(number)
                and len(rest) <= min(self.max_title_chars, 36)
                and self._plain_integer_title_ok(rest)
                and not self._looks_like_sentence(rest)
            )
        )
        if not strong_number and not plain_title_evidence:
            return None

        if len(rest) <= self.max_title_chars and not self._looks_like_sentence(rest):
            return HeadingMatch(level=level, title=f"{number} {rest}")

        # Common PDF artifact: ``4.2 体格检查 仔细的体格检查有助于……``.
        # Chinese section titles normally have no internal spaces, so the first token
        # is a useful conservative boundary and the remainder is retained as body text.
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
    def _looks_like_long_body(text: str) -> bool:
        return len(text) > 90 or bool(re.search(r"[。！？；;].{8,}", text))

    @staticmethod
    def _plain_integer_number_ok(number: str) -> bool:
        if "." in number:
            return True
        try:
            value = int(number)
        except ValueError:
            return False
        # Medical guideline top-level sections are normally small integers.
        # This rejects percentile/value fragments such as ``95 定义为高血压...``.
        return 1 <= value <= 30

    @classmethod
    def _plain_integer_title_ok(cls, text: str) -> bool:
        if not cls._title_shape_ok(text):
            return False
        # Numeric thresholds / ratios are strong evidence that this is body text,
        # not a plain top-level heading.
        if re.search(r"[<>≥≤=%/]|P\d|\d[~～-]\d", text, re.IGNORECASE):
            return False
        return True

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
