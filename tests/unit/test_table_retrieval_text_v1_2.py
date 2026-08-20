from __future__ import annotations

from medical_rag.chunking.chunker import StructureAwareChunker
from medical_rag.chunking.table_retrieval_text import TableRetrievalTextBuilder
from medical_rag.parsing.models import CleanedDocument, CleanedPage, TableBlock


def _broken_table6() -> TableBlock:
    return TableBlock(
        page=10,
        table_no=0,
        bbox=(240.79, 525.1, 495.89, 629.61),
        caption_bbox=(280.77, 482.24, 508.9, 505.07),
        title="表6 基于诊室血压的血压分类和高血压分级 (mmHg)",
        headers=["", "正常血压", "<120", "和", "<80"],
        rows=[
            ["", "1级高血压(轻度)", "140~159", "和/或", "90~99"],
            ["", "2级高血压(中度)", "160~179", "和/或 1", "00~10"],
            ["a", "3级高血压(重度)", "≥180", "和/或", "≥11"],
        ],
        search_text=(
            "表6 基于诊室血压的血压分类和高血压分级 (mmHg)\n"
            "正常血压: 1级高血压(轻度)；<120: 140~159；和: 和/或；<80: 90~99\n"
            "正常血压: 2级高血压(中度)；<120: 160~179；和: 和/或 1；<80: 00~10\n"
            "a；正常血压: 3级高血压(重度)；<120: ≥180；和: 和/或；<80: ≥11"
        ),
        raw_text=(
            "1级高血压(轻度) 140~159 和/或 90~99\n"
            "2级血压(中度) 160~179 和/或 100~109\n"
            "a 3级高血压(重度) ≥180 和/或 ≥110"
        ),
        extraction_strategy="caption_text",
        quality_flags=["raw_text_fallback"],
    )


def test_quality_aware_fallback_recovers_missing_medical_ranges() -> None:
    result = TableRetrievalTextBuilder().build(_broken_table6())
    assert result.used_raw_fallback is True
    assert result.strategy == "structured_plus_numeric_raw_fallback"
    assert "100~109" in result.text
    assert "≥110" in result.text
    assert "100~109" in result.missing_numeric_tokens
    assert "≥110" in result.missing_numeric_tokens
    # Already-correct facts should not trigger duplicated fallback rows.
    assert result.text.count("140~159") == 1


def test_raw_fallback_is_not_duplicated_when_structured_numeric_facts_are_complete() -> None:
    table = TableBlock(
        page=1,
        table_no=0,
        bbox=(0, 0, 100, 100),
        title="表1",
        headers=["分类", "范围"],
        rows=[["2级高血压", "160~179 / 100~109"]],
        search_text="表1\n分类: 2级高血压；范围: 160~179 / 100~109",
        raw_text="2级高血压 160~179 100~109",
    )
    result = TableRetrievalTextBuilder().build(table)
    assert result.strategy == "structured_only"
    assert result.used_raw_fallback is False
    assert "数值保真补充" not in result.text


def test_table_chunk_contains_recovered_numeric_evidence_and_diagnostics() -> None:
    document = CleanedDocument(
        source_path="guide.pdf",
        file_name="guide.pdf",
        page_count=1,
        pages=[
            CleanedPage(
                page=10,
                width=600,
                height=800,
                blocks=[],
                tables=[_broken_table6()],
                text="",
            )
        ],
    )
    chunked = StructureAwareChunker().chunk(document)
    table_chunks = [chunk for chunk in chunked.chunks if chunk.content_type == "table"]
    assert len(table_chunks) == 1
    chunk = table_chunks[0]
    assert "2级高血压(中度)" in chunk.text
    assert "100~109" in chunk.text
    assert "3级高血压(重度)" in chunk.text
    assert "≥110" in chunk.text
    assert chunk.metadata["table_raw_fallback_used"] == "true"
    assert "100~109" in chunk.metadata["table_missing_numeric_tokens"]
    assert "≥110" in chunk.metadata["table_missing_numeric_tokens"]
