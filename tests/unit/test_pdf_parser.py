from pathlib import Path

import fitz
import pytest

from medical_rag.parsing import PdfParser


@pytest.mark.asyncio
async def test_pdf_parser_preserves_page_and_block_geometry(tmp_path: Path) -> None:
    path = tmp_path / "two_columns.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 100), "Left column first block")
    page.insert_text((60, 150), "Left column second block")
    page.insert_text((330, 100), "Right column first block")
    page.insert_text((330, 150), "Right column second block")
    doc.save(path)
    doc.close()

    result = await PdfParser(min_page_chars=10).parse(path)

    assert result.page_count == 1
    assert result.pages[0].text_layer_ok is True
    texts = [block.text for block in result.pages[0].blocks]
    assert texts.index("Left column first block") < texts.index("Right column first block")
    assert all(len(block.bbox) == 4 for block in result.pages[0].blocks)
