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


class ParsedPage(BaseModel):
    page: int
    width: float
    height: float
    blocks: list[TextBlock] = Field(default_factory=list)
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
    text: str = ""


class CleanedDocument(BaseModel):
    source_path: str
    file_name: str
    page_count: int
    metadata: dict[str, str] = Field(default_factory=dict)
    pages: list[CleanedPage] = Field(default_factory=list)
    repeated_noise_patterns: list[str] = Field(default_factory=list)
