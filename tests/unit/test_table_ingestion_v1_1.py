from __future__ import annotations

import pymupdf

from medical_rag.chunking.chunker import StructureAwareChunker
from medical_rag.parsing.models import TableBlock, TextBlock
from medical_rag.parsing.pdf_parser import PdfParser


def _block(
    text: str,
    bbox: tuple[float, float, float, float],
    *,
    order: int,
) -> TextBlock:
    return TextBlock(
        page=10,
        block_no=order,
        reading_order=order,
        bbox=bbox,
        text=text,
    )


def test_caption_guided_clip_stays_in_right_column_when_left_prose_exists() -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    parser = PdfParser()

    caption = _block(
        "表6 基于诊室血压的血压分类和高血压分级",
        (330, 320, 565, 338),
        order=4,
    )
    blocks = [
        _block("4.4.4 眼底", (35, 280, 260, 300), order=0),
        _block("眼底检查可检测高血压导致的视网膜病变。", (35, 330, 270, 355), order=1),
        _block("4.5.1 按血压水平分类和分级", (330, 270, 565, 295), order=2),
        caption,
        _block("分类 收缩压 舒张压", (330, 350, 565, 368), order=5),
    ]

    clip = parser._table_clip_below_caption(page, caption, blocks)
    assert clip.x0 > 250
    assert clip.x1 == 600


def test_raw_table_text_preserves_exact_numeric_range() -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=800)
    page.insert_text((330, 360), "2 grade BP", fontsize=10)
    page.insert_text((430, 360), "160~179", fontsize=10)
    page.insert_text((505, 360), "100~109", fontsize=10)

    parser = PdfParser()
    raw = parser._extract_raw_table_text(page, pymupdf.Rect(300, 330, 590, 390))
    assert "160~179" in raw
    assert "100~109" in raw


def test_search_text_keeps_raw_fallback_when_structured_cells_are_split() -> None:
    search_text = PdfParser._table_to_search_text(
        "表6",
        ["分类", "收缩压", "舒张压"],
        [["2级高血压(中度)", "160~179", "00~10"]],
        "2级高血压(中度) 160~179 和/或 100~109",
    )
    assert "00~10" in search_text
    assert "100~109" in search_text
    assert "原始表格文本" in search_text


def test_table_reading_order_uses_caption_column_not_contaminated_bbox() -> None:
    chunker = StructureAwareChunker()
    blocks = [
        _block("4.4.4 眼底", (30, 100, 270, 120), order=0),
        _block("眼底正文", (30, 140, 270, 180), order=1),
        _block("4.5 血压分类与心血管危险分层", (330, 100, 570, 120), order=2),
        _block("4.5.1 按血压水平分类和分级", (330, 220, 570, 240), order=3),
        _block("表后正文", (330, 500, 570, 540), order=4),
    ]
    table = TableBlock(
        page=10,
        table_no=0,
        # Simulate a bad virtual bbox that spans both columns.
        bbox=(20, 300, 575, 470),
        caption_bbox=(330, 280, 570, 298),
        title="表6 基于诊室血压的血压分类和高血压分级",
        headers=["分类", "收缩压", "舒张压"],
        rows=[["2级高血压", "160~179", "100~109"]],
        search_text="表6\n2级高血压 160~179 100~109",
    )

    elements = chunker._page_elements(blocks, [table], 600)
    labels = [item.text if kind == "text" else item.title for kind, item in elements]

    heading_index = labels.index("4.5.1 按血压水平分类和分级")
    table_index = labels.index("表6 基于诊室血压的血压分类和高血压分级")
    after_index = labels.index("表后正文")
    assert heading_index < table_index < after_index


def test_table_chunk_inherits_nearest_right_column_section() -> None:
    from medical_rag.parsing.models import CleanedDocument, CleanedPage

    blocks = [
        _block("4.4.4 眼底", (30, 100, 270, 120), order=0),
        _block("眼底正文。", (30, 140, 270, 180), order=1),
        _block("4.5 血压分类与心血管危险分层", (330, 100, 570, 120), order=2),
        _block("4.5.1 按血压水平分类和分级", (330, 220, 570, 240), order=3),
        _block("后续正文。", (330, 500, 570, 540), order=4),
    ]
    table = TableBlock(
        page=10,
        table_no=0,
        bbox=(20, 300, 575, 470),
        caption_bbox=(330, 280, 570, 298),
        title="表6 基于诊室血压的血压分类和高血压分级",
        headers=["分类", "收缩压", "舒张压"],
        rows=[["2级高血压", "160~179", "100~109"]],
        search_text="表6\n2级高血压 160~179 100~109",
    )
    document = CleanedDocument(
        source_path="guide.pdf",
        file_name="guide.pdf",
        page_count=1,
        pages=[
            CleanedPage(
                page=10,
                width=600,
                height=800,
                blocks=blocks,
                tables=[table],
                text="",
            )
        ],
    )

    chunked = StructureAwareChunker().chunk(document)
    table_chunks = [chunk for chunk in chunked.chunks if chunk.content_type == "table"]
    assert len(table_chunks) == 1
    assert table_chunks[0].section == "4.5.1 按血压水平分类和分级"
    assert "100~109" in table_chunks[0].text
