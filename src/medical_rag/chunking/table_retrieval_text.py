from __future__ import annotations

import re
from dataclasses import dataclass, field

from medical_rag.parsing.models import TableBlock


# Numeric facts are unusually important in medical guideline tables.  We therefore
# compare the structured representation with the raw layout text and recover any
# numeric ranges / thresholds that disappeared during virtual-cell reconstruction.
_NUMERIC_TOKEN_RE = re.compile(
    r"[<>≤≥]?\s*\d+(?:\.\d+)?(?:\s*[~～\-–—/]\s*[<>≤≥]?\s*\d+(?:\.\d+)?)?"
)


def _normalize_numeric_token(value: str) -> str:
    value = re.sub(r"\s+", "", value)
    value = value.replace("～", "~").replace("–", "-").replace("—", "-")
    return value


def _numeric_tokens(text: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for match in _NUMERIC_TOKEN_RE.finditer(text or ""):
        token = _normalize_numeric_token(match.group(0))
        # Ignore bare one-digit tokens.  They are usually grade/list markers and are
        # too ambiguous to be useful for deciding whether a medical numeric fact was
        # lost.  Inequality-prefixed single digits are retained.
        if token.isdigit() and len(token) == 1:
            continue
        if token and token not in seen:
            result.append(token)
            seen.add(token)
    return result


@dataclass(slots=True)
class TableRetrievalText:
    text: str
    strategy: str
    used_raw_fallback: bool = False
    missing_numeric_tokens: list[str] = field(default_factory=list)
    fallback_lines: list[str] = field(default_factory=list)


class TableRetrievalTextBuilder:
    """Build retrieval-safe text from both structured and raw table representations.

    Structured rows preserve semantic relationships, but borderless PDF table
    detection can split exact values across virtual cells (for example ``100~109`` ->
    ``1`` + ``00~10``).  Raw layout text is less structured but often preserves those
    exact values.  Instead of blindly duplicating the whole raw table, this builder
    performs a quality-aware numeric comparison and appends only raw lines needed to
    recover facts missing from the structured representation.
    """

    def build(self, table: TableBlock) -> TableRetrievalText:
        structured = (table.search_text or table.markdown or "").strip()
        raw = (table.raw_text or "").strip()

        if not structured and not raw:
            fallback = (table.title or f"表格 {table.table_no + 1}").strip()
            return TableRetrievalText(text=fallback, strategy="title_only")
        if not structured:
            text = self._with_title_if_needed(table.title, raw)
            return TableRetrievalText(
                text=text,
                strategy="raw_only",
                used_raw_fallback=True,
                fallback_lines=[line.strip() for line in raw.splitlines() if line.strip()],
            )
        if not raw:
            return TableRetrievalText(text=structured, strategy="structured_only")

        structured_tokens = set(_numeric_tokens(structured))
        raw_tokens = _numeric_tokens(raw)
        missing = [token for token in raw_tokens if token not in structured_tokens]

        # Only append the raw rows that actually contain a lost numeric fact.  This
        # avoids doubling a whole table and therefore reduces semantic dilution in the
        # embedding while still recovering exact medical thresholds.
        fallback_lines: list[str] = []
        for line in raw.splitlines():
            clean = line.strip()
            if not clean:
                continue
            line_tokens = set(_numeric_tokens(clean))
            if any(token in line_tokens for token in missing):
                fallback_lines.append(clean)

        if missing and fallback_lines:
            recovered = "\n".join(fallback_lines)
            text = structured.rstrip() + "\n\n数值保真补充：\n" + recovered
            return TableRetrievalText(
                text=text,
                strategy="structured_plus_numeric_raw_fallback",
                used_raw_fallback=True,
                missing_numeric_tokens=missing,
                fallback_lines=fallback_lines,
            )

        return TableRetrievalText(text=structured, strategy="structured_only")

    @staticmethod
    def _with_title_if_needed(title: str | None, text: str) -> str:
        if not title:
            return text
        compact_title = re.sub(r"\s+", "", title)
        compact_text = re.sub(r"\s+", "", text)
        if compact_title and compact_title in compact_text:
            return text
        return title.strip() + "\n" + text


__all__ = ["TableRetrievalText", "TableRetrievalTextBuilder"]
