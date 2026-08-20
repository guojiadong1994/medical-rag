from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from statistics import mean

from medical_rag.chunking import StructureAwareChunker
from medical_rag.parsing.models import CleanedDocument


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_preview(chunks: list[object]) -> str:
    sections: list[str] = []
    for chunk in chunks:
        section = chunk.section or "（未识别章节）"
        page_label = (
            f"PAGE {chunk.page_start}"
            if chunk.page_start == chunk.page_end
            else f"PAGES {chunk.page_start}-{chunk.page_end}"
        )
        title = (
            f"TABLE · {chunk.table_title or chunk.chunk_id}"
            if chunk.content_type == "table"
            else f"NARRATIVE · {section}"
        )
        sections.append(
            "\n".join(
                [
                    f"## {title}",
                    "",
                    f"- chunk_id: `{chunk.chunk_id}`",
                    f"- {page_label}",
                    f"- chars: {chunk.char_count}",
                    f"- section_path: {' > '.join(chunk.section_path) or '—'}",
                    "",
                    chunk.text,
                ]
            )
        )
    return "\n\n---\n\n".join(sections)


def _suspicious_section_reason(section: str) -> list[str]:
    reasons: list[str] = []
    text = section.strip()
    if len(text) > 70:
        reasons.append("too_long")
    if re.search(r"[<>≥≤=%/]", text):
        reasons.append("numeric_threshold_symbol")
    if re.search(r"\bP\s*\d|\d\s*[~～-]\s*\d|\d+\s*mmHg", text, re.IGNORECASE):
        reasons.append("numeric_range_or_measurement")
    if re.search(r"[。！？!?；;]", text):
        reasons.append("sentence_punctuation")
    if text.count(",") + text.count("，") >= 2:
        reasons.append("body_like_commas")
    match = re.match(r"^(\d+)\s+", text)
    if match and int(match.group(1)) > 30:
        reasons.append("plain_integer_gt_30")
    return reasons


def _length_stats(chunks: list[object]) -> dict[str, float | int]:
    lengths = [chunk.char_count for chunk in chunks]
    return {
        "count": len(chunks),
        "min": min(lengths) if lengths else 0,
        "avg": round(mean(lengths), 2) if lengths else 0,
        "max": max(lengths) if lengths else 0,
    }


def run(
    input_json: Path,
    output_dir: Path,
    *,
    target_chars: int,
    max_chars: int,
    min_chars: int,
    overlap_chars: int,
) -> None:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    document = CleanedDocument.model_validate(payload)

    chunker = StructureAwareChunker(
        target_chars=target_chars,
        max_chars=max_chars,
        min_chars=min_chars,
        overlap_chars=overlap_chars,
    )
    chunked = chunker.chunk(document)

    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_path = output_dir / "chunks.json"
    preview_path = output_dir / "chunks_preview.md"
    report_path = output_dir / "chunk_report.json"
    section_audit_path = output_dir / "section_audit.json"

    _write_json(chunks_path, [chunk.model_dump(mode="json") for chunk in chunked.chunks])
    preview_path.write_text(_render_preview(chunked.chunks), encoding="utf-8")

    narrative = [chunk for chunk in chunked.chunks if chunk.content_type == "narrative"]
    tables = [chunk for chunk in chunked.chunks if chunk.content_type == "table"]
    lengths = [chunk.char_count for chunk in chunked.chunks]
    sections = sorted({chunk.section for chunk in chunked.chunks if chunk.section})
    sectioned_narrative = [chunk for chunk in narrative if chunk.section]

    section_audit = []
    for section in sections:
        reasons = _suspicious_section_reason(section)
        section_audit.append(
            {
                "section": section,
                "suspicious": bool(reasons),
                "reasons": reasons,
                "chunk_count": sum(chunk.section == section for chunk in chunked.chunks),
            }
        )
    _write_json(section_audit_path, section_audit)

    suspicious_sections = [item for item in section_audit if item["suspicious"]]
    report = {
        "document_id": chunked.document_id,
        "source_file": chunked.source_file,
        "chunk_count": len(chunked.chunks),
        "narrative_chunk_count": len(narrative),
        "table_chunk_count": len(tables),
        "section_count": len(sections),
        "suspicious_section_count": len(suspicious_sections),
        "sectioned_narrative_count": len(sectioned_narrative),
        "unsectioned_narrative_count": len(narrative) - len(sectioned_narrative),
        "sectioned_narrative_ratio": (
            round(len(sectioned_narrative) / len(narrative), 4) if narrative else 0.0
        ),
        "min_chunk_chars": min(lengths) if lengths else 0,
        "avg_chunk_chars": round(mean(lengths), 2) if lengths else 0,
        "max_chunk_chars": max(lengths) if lengths else 0,
        "short_chunk_count": sum(1 for length in lengths if length < min_chars),
        "over_target_chunk_count": sum(1 for length in lengths if length > target_chars),
        "over_max_chunk_count": sum(1 for length in lengths if length > max_chars),
        "narrative_length_stats": _length_stats(narrative),
        "table_length_stats": _length_stats(tables),
        "short_narrative_chunk_count": sum(
            chunk.char_count < min_chars for chunk in narrative
        ),
        "short_table_chunk_count": sum(chunk.char_count < min_chars for chunk in tables),
        "narrative_over_max_chunk_count": sum(
            chunk.char_count > max_chars for chunk in narrative
        ),
        "table_over_max_chunk_count": sum(chunk.char_count > max_chars for chunk in tables),
        "table_over_max_is_expected": True,
        "table_raw_fallback_chunk_count": sum(
            chunk.metadata.get("table_raw_fallback_used") == "true" for chunk in tables
        ),
        "table_structured_only_chunk_count": sum(
            chunk.metadata.get("table_retrieval_strategy") == "structured_only" for chunk in tables
        ),
        "table_numeric_mismatch_chunk_count": sum(
            bool(chunk.metadata.get("table_missing_numeric_tokens")) for chunk in tables
        ),
        "cross_page_chunk_count": sum(
            1 for chunk in narrative if chunk.page_start != chunk.page_end
        ),
        "config": {
            "strategy_version": "stable_v1_table_retrieval_v1_2",
            "strategy_note": "V1.1 retrieval granularity + V1.2 strict section safety; no aggressive short-chunk merge",
            "target_chars": target_chars,
            "max_chars": max_chars,
            "min_chars": min_chars,
            "overlap_chars": overlap_chars,
            "max_chars_scope": "narrative only; tables are intentionally kept intact in V1",
            "short_chunk_policy": "preserve meaningful short chunks; drop only obvious layout noise",
        },
    }
    _write_json(report_path, report)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print("- chunks.json")
    print("- chunks_preview.md")
    print("- chunk_report.json")
    print("- section_audit.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Structure-aware chunking for a cleaned document")
    parser.add_argument(
        "cleaned_document",
        type=Path,
        help="Path to cleaned_document.json generated by scripts/parse_pdf.py",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory; defaults to the cleaned document's directory",
    )
    parser.add_argument("--target-chars", type=int, default=800)
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--min-chars", type=int, default=180)
    parser.add_argument("--overlap-chars", type=int, default=120)
    args = parser.parse_args()

    output_dir = args.output_dir or args.cleaned_document.parent
    run(
        args.cleaned_document,
        output_dir,
        target_chars=args.target_chars,
        max_chars=args.max_chars,
        min_chars=args.min_chars,
        overlap_chars=args.overlap_chars,
    )


if __name__ == "__main__":
    main()
