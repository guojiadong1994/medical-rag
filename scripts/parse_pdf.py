from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from medical_rag.cleaning import DocumentCleaner
from medical_rag.parsing import PdfParser


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_tables_preview(cleaned: object) -> str:
    sections: list[str] = []
    for page in cleaned.pages:
        for table in page.tables:
            title = table.title or f"Table {table.table_no + 1}"
            sections.append(
                "\n".join(
                    [
                        f"## PAGE {page.page} · {title}",
                        "",
                        f"- strategy: `{table.extraction_strategy}`",
                        f"- quality_flags: `{', '.join(table.quality_flags) or 'none'}`",
                        f"- bbox: `{table.bbox}`",
                        f"- caption_bbox: `{table.caption_bbox}`",
                        "",
                        "### Structured table",
                        "",
                        table.markdown,
                        "",
                        "### Raw text fallback",
                        "",
                        table.raw_text or "(empty)",
                        "",
                        "### Search text",
                        "",
                        table.search_text,
                    ]
                )
            )
    return "\n\n---\n\n".join(sections)


async def run(input_pdf: Path, output_dir: Path) -> None:
    parser = PdfParser()
    cleaner = DocumentCleaner()
    parsed = await parser.parse(input_pdf)
    cleaned = cleaner.clean(parsed)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "parsed_document.json", parsed.model_dump(mode="json"))
    _write_json(output_dir / "cleaned_document.json", cleaned.model_dump(mode="json"))

    raw_blocks = sum(page.raw_block_count for page in parsed.pages)
    parsed_text_blocks = sum(len(page.blocks) for page in parsed.pages)
    table_text_blocks = sum(page.table_text_block_count for page in parsed.pages)
    cleaned_blocks = sum(len(page.blocks) for page in cleaned.pages)
    table_count = sum(len(page.tables) for page in cleaned.pages)
    table_pages = [page.page for page in cleaned.pages if page.tables]
    all_tables = [table for page in cleaned.pages for table in page.tables]
    table_strategy_counts: dict[str, int] = {}
    for table in all_tables:
        table_strategy_counts[table.extraction_strategy] = (
            table_strategy_counts.get(table.extraction_strategy, 0) + 1
        )

    report = {
        "file_name": parsed.file_name,
        "page_count": parsed.page_count,
        "raw_blocks": raw_blocks,
        "parsed_text_blocks": parsed_text_blocks,
        "table_text_blocks_separated": table_text_blocks,
        "cleaned_blocks": cleaned_blocks,
        "removed_noise_blocks": parsed_text_blocks - cleaned_blocks,
        "raw_characters": sum(page.raw_char_count for page in parsed.pages),
        "cleaned_characters": sum(len(page.text) for page in cleaned.pages),
        "text_layer_pages": sum(1 for page in parsed.pages if page.text_layer_ok),
        "ocr_recommended_pages": parsed.ocr_recommended_pages,
        "table_count": table_count,
        "table_pages": table_pages,
        "table_strategy_counts": table_strategy_counts,
        "column_clipped_table_count": sum(
            "column_clipped" in table.quality_flags for table in all_tables
        ),
        "raw_text_fallback_table_count": sum(bool(table.raw_text) for table in all_tables),
        "repeated_noise_patterns": cleaned.repeated_noise_patterns,
    }
    _write_json(output_dir / "parse_report.json", report)

    preview = "\n\n".join(
        f"===== PAGE {page.page} =====\n{page.text}" for page in cleaned.pages
    )
    (output_dir / "cleaned_preview.txt").write_text(preview, encoding="utf-8")

    tables_payload = [
        table.model_dump(mode="json")
        for page in cleaned.pages
        for table in page.tables
    ]
    _write_json(output_dir / "tables.json", tables_payload)
    _write_json(
        output_dir / "table_quality_report.json",
        [
            {
                "page": table.page,
                "table_no": table.table_no,
                "title": table.title,
                "bbox": table.bbox,
                "caption_bbox": table.caption_bbox,
                "extraction_strategy": table.extraction_strategy,
                "quality_flags": table.quality_flags,
                "raw_text_chars": len(table.raw_text),
            }
            for table in all_tables
        ],
    )
    (output_dir / "tables_preview.md").write_text(
        _render_tables_preview(cleaned),
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")


def main() -> None:
    arg_parser = argparse.ArgumentParser(description="Parse and clean a medical PDF")
    arg_parser.add_argument("pdf", type=Path, help="Path to the input PDF")
    arg_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/pdf_parse"),
        help="Directory for parser/cleaner outputs",
    )
    args = arg_parser.parse_args()
    asyncio.run(run(args.pdf, args.output_dir))


if __name__ == "__main__":
    main()
