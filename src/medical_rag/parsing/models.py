from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class TextBlock(BaseModel):
    page: int
    block_no: int
    reading_order: int = 0
    bbox: tuple[float, float, float, float]
    text: str
    font_size: float | None = None
    font_name: str | None = None
    is_bold: bool = False
    source: Literal["text_layer", "ocr"] = "text_layer"


class TableBlock(BaseModel):
    page: int
    table_no: int
    bbox: tuple[float, float, float, float]
    title: str | None = None
    # ``caption_bbox`` is the layout anchor used by the chunker.  A borderless table
    # detector can produce a bbox that is wider / higher than the actual table when a
    # two-column PDF contains narrative text at the same vertical position.  The
    # caption position is much more stable for deciding *where* the table belongs in
    # reading order and therefore which section metadata it should inherit.
    caption_bbox: tuple[float, float, float, float] | None = None
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    markdown: str = ""
    # ``raw_text`` is a layout-aware fallback representation reconstructed directly
    # from the PDF text layer inside the table region.  It is intentionally preserved
    # in addition to structured rows because borderless tables may split a numeric
    # value across virtual cells even though the original text layer is correct.
    raw_text: str = ""
    search_text: str = ""
    extraction_strategy: Literal["lines_strict", "caption_text"] = "lines_strict"
    quality_flags: list[str] = Field(default_factory=list)
    source: Literal["text_layer", "ocr"] = "text_layer"


class ParsedPage(BaseModel):
    page: int
    width: float
    height: float
    blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    raw_block_count: int = 0
    table_text_block_count: int = 0
    raw_char_count: int = 0
    text_layer_ok: bool = True


class ParsedDocument(BaseModel):
    source_path: str
    file_name: str
    page_count: int
    metadata: dict[str, str] = Field(default_factory=dict)
    pages: list[ParsedPage] = Field(default_factory=list)
    ocr_recommended_pages: list[int] = Field(default_factory=list)

    @classmethod
    def from_path(cls, path: Path, **kwargs: object) -> "ParsedDocument":
        return cls(source_path=str(path), file_name=path.name, **kwargs)


class CleanedPage(BaseModel):
    page: int
    width: float
    height: float
    blocks: list[TextBlock] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    text: str = ""


class CleanedDocument(BaseModel):
    source_path: str
    file_name: str
    page_count: int
    metadata: dict[str, str] = Field(default_factory=dict)
    pages: list[CleanedPage] = Field(default_factory=list)
    repeated_noise_patterns: list[str] = Field(default_factory=list)
