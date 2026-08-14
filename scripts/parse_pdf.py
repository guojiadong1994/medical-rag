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


async def run(input_pdf: Path, output_dir: Path) -> None:
    parser = PdfParser()
    cleaner = DocumentCleaner()

    parsed = await parser.parse(input_pdf)
    cleaned = cleaner.clean(parsed)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "parsed_document.json", parsed.model_dump(mode="json"))
    _write_json(output_dir / "cleaned_document.json", cleaned.model_dump(mode="json"))

    raw_blocks = sum(len(page.blocks) for page in parsed.pages)
    cleaned_blocks = sum(len(page.blocks) for page in cleaned.pages)
    report = {
        "file_name": parsed.file_name,
        "page_count": parsed.page_count,
        "raw_blocks": raw_blocks,
        "cleaned_blocks": cleaned_blocks,
        "removed_blocks": raw_blocks - cleaned_blocks,
        "raw_characters": sum(page.raw_char_count for page in parsed.pages),
        "cleaned_characters": sum(len(page.text) for page in cleaned.pages),
        "text_layer_pages": sum(1 for page in parsed.pages if page.text_layer_ok),
        "ocr_recommended_pages": parsed.ocr_recommended_pages,
        "repeated_noise_patterns": cleaned.repeated_noise_patterns,
    }
    _write_json(output_dir / "parse_report.json", report)

    preview = "\n\n".join(
        f"===== PAGE {page.page} =====\n{page.text}" for page in cleaned.pages
    )
    (output_dir / "cleaned_preview.txt").write_text(preview, encoding="utf-8")

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
