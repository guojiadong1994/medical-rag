from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from medical_rag.chunking.models import DocumentChunk
from medical_rag.evaluation import RetrievalEvalSuite, matching_rule_ids
from medical_rag.retrieval.models import DenseSearchHit


def _load_chunks(path: Path) -> list[DocumentChunk]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else payload.get("chunks", [])
    return [DocumentChunk.model_validate(item) for item in items]


def _load_suite(path: Path) -> RetrievalEvalSuite:
    return RetrievalEvalSuite.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _as_hit(chunk: DocumentChunk) -> DenseSearchHit:
    return DenseSearchHit(
        rank=1,
        score=0.0,
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        source_file=chunk.source_file,
        content_type=chunk.content_type,
        section=chunk.section,
        section_path=list(chunk.section_path),
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        text=chunk.text,
        table_title=chunk.table_title,
        table_no=chunk.table_no,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Evaluation V2 evidence labels against the current chunk corpus"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--eval-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--examples-per-rule", type=int, default=3)
    args = parser.parse_args()

    chunks = _load_chunks(args.chunks_json)
    suite = _load_suite(args.eval_file)
    output_dir = args.output_dir or args.chunks_json.parent / "evaluation"

    cases_payload: list[dict[str, object]] = []
    total_zero_match = 0

    for case in suite.cases:
        matched_chunks: list[tuple[DocumentChunk, list[str]]] = []
        counts: Counter[str] = Counter()
        examples: dict[str, list[dict[str, object]]] = {}

        for chunk in chunks:
            rule_ids = matching_rule_ids(_as_hit(chunk), case.evidence_rules)
            if not rule_ids:
                continue
            matched_chunks.append((chunk, rule_ids))
            for rule_id in rule_ids:
                counts[rule_id] += 1
                bucket = examples.setdefault(rule_id, [])
                if len(bucket) < args.examples_per_rule:
                    bucket.append(
                        {
                            "chunk_id": chunk.chunk_id,
                            "page_start": chunk.page_start,
                            "page_end": chunk.page_end,
                            "section": chunk.section,
                            "content_type": chunk.content_type,
                            "table_title": chunk.table_title,
                            "text_preview": chunk.text[:280].replace("\n", " "),
                        }
                    )

        if not matched_chunks:
            total_zero_match += 1

        cases_payload.append(
            {
                "id": case.id,
                "query": case.query,
                "expected_facts": case.expected_facts,
                "evidence_chunk_count": len(matched_chunks),
                "matched_rule_counts": dict(counts),
                "examples_by_rule": examples,
            }
        )

    payload = {
        "suite_name": suite.name,
        "suite_version": suite.version,
        "query_count": len(suite.cases),
        "chunk_count": len(chunks),
        "zero_match_case_count": total_zero_match,
        "cases": cases_payload,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"eval_label_audit_{suite.version}.json"
    md_path = output_dir / f"eval_label_audit_{suite.version}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Evaluation Label Audit · {suite.name}",
        "",
        f"- suite_version: {suite.version}",
        f"- query_count: {len(suite.cases)}",
        f"- chunk_count: {len(chunks)}",
        f"- zero_match_case_count: {total_zero_match}",
        "",
        "| ID | Evidence chunks | Matched rules |",
        "|---|---:|---|",
    ]
    for item in cases_payload:
        counts = item["matched_rule_counts"]
        rule_text = ", ".join(f"{key}={value}" for key, value in counts.items()) or "—"
        lines.append(f"| {item['id']} | {item['evidence_chunk_count']} | {rule_text} |")

    lines.extend([
        "",
        "## Notes",
        "",
        "`zero_match_case_count` 必须为 0。某个规则匹配很多 Chunk 不一定是错误，但需要人工检查是否过宽；",
        "V2 的目标不是让数字变好看，而是让所有能够独立支持答案的证据都获得合理的 positive 标签。",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "suite_name": suite.name,
        "suite_version": suite.version,
        "query_count": len(suite.cases),
        "chunk_count": len(chunks),
        "zero_match_case_count": total_zero_match,
        "evidence_chunk_counts": {
            item["id"]: item["evidence_chunk_count"] for item in cases_payload
        },
    }, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {md_path.name}")


if __name__ == "__main__":
    main()
