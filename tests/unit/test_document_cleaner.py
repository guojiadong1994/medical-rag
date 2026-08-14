from medical_rag.cleaning import DocumentCleaner
from medical_rag.parsing.models import ParsedDocument, ParsedPage, TextBlock


def _block(page: int, no: int, y0: float, y1: float, text: str) -> TextBlock:
    return TextBlock(
        page=page,
        block_no=no,
        reading_order=no,
        bbox=(10.0, y0, 580.0, y1),
        text=text,
    )


def test_cleaner_removes_repeated_header_footer_but_keeps_body() -> None:
    pages = []
    for page_no in range(1, 6):
        pages.append(
            ParsedPage(
                page=page_no,
                width=595,
                height=842,
                raw_char_count=100,
                blocks=[
                    _block(page_no, 0, 10, 30, f"中华高血压杂志 2024年第32卷 第{page_no}页"),
                    _block(page_no, 1, 100, 180, f"第{page_no}页的医学正文内容。"),
                    _block(page_no, 2, 815, 830, f"·{600 + page_no}·"),
                ],
            )
        )

    doc = ParsedDocument(
        source_path="guide.pdf",
        file_name="guide.pdf",
        page_count=5,
        pages=pages,
    )
    cleaned = DocumentCleaner(min_repeat_pages=3).clean(doc)

    assert all(len(page.blocks) == 1 for page in cleaned.pages)
    assert "医学正文内容" in cleaned.pages[0].text


def test_clean_block_text_repairs_wrapped_text_and_noise_chars() -> None:
    cleaner = DocumentCleaner()
    text = "高血\ufffe压患者应\n进行治疗性生活方式干预。\nACEI should be\nused carefully."
    cleaned = cleaner.clean_block_text(text)
    assert "高血压患者应进行治疗性生活方式干预" in cleaned
    assert "ACEI should be used carefully" in cleaned


def test_cleaner_keeps_standalone_numbers_inside_body() -> None:
    page = ParsedPage(
        page=1,
        width=595,
        height=842,
        raw_char_count=30,
        blocks=[
            _block(1, 0, 300, 320, "收缩压每降低"),
            _block(1, 1, 320, 340, "5"),
            _block(1, 2, 340, 360, "mmHg,主要心血管事件风险下降。"),
        ],
    )
    doc = ParsedDocument(
        source_path="guide.pdf",
        file_name="guide.pdf",
        page_count=1,
        pages=[page],
    )
    cleaned = DocumentCleaner().clean(doc)
    assert any(block.text == "5" for block in cleaned.pages[0].blocks)
