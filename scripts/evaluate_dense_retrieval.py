from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.evaluation import DenseRetrievalEvaluator, RetrievalEvalSuite
from medical_rag.retrieval import LocalDenseIndex


def _load_suite(path: Path) -> RetrievalEvalSuite:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RetrievalEvalSuite.model_validate(payload)


def _safe_tag(tag: str | None) -> str:
    if not tag:
        return ""
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", tag).strip("_")
    return f"_{value}" if value else ""


def _render_markdown(report: object) -> str:
    lines = [
        f"# Dense Retrieval Evaluation · {report.suite_name}",
        "",
        f"- model: `{report.model_name}`",
        f"- queries: {report.query_count}",
        f"- top_k: {report.top_k}",
        f"- Recall@1: **{report.recall_at_1:.3f}**",
        f"- Recall@3: **{report.recall_at_3:.3f}**",
        f"- Recall@5: **{report.recall_at_5:.3f}**",
        f"- MRR: **{report.mrr:.3f}**",
        f"- no relevant evidence in Top-{report.top_k}: {report.no_relevant_in_top_k}",
        "",
        "| ID | Query | First relevant rank | RR |",
        "|---|---|---:|---:|",
    ]
    for item in report.results:
        rank = item.first_relevant_rank if item.first_relevant_rank is not None else "MISS"
        query = item.query.replace("|", "\\|")
        lines.append(f"| {item.id} | {query} | {rank} | {item.reciprocal_rank:.3f} |")

    lines.extend(["", "## Misses / weak cases", ""])
    weak = [x for x in report.results if x.first_relevant_rank is None or x.first_relevant_rank > 3]
    if not weak:
        lines.append("Top-3 内全部命中。")
    else:
        for item in weak:
            lines.append(f"### {item.id} · {item.query}")
            lines.append("")
            lines.append(f"First relevant rank: `{item.first_relevant_rank or 'MISS'}`")
            lines.append("")
            for hit in item.hits[:5]:
                flag = "✅" if hit.relevant else "·"
                section = hit.section or "—"
                lines.append(
                    f"- {flag} #{hit.rank} score={hit.score:.6f} "
                    f"page={hit.page_start}-{hit.page_end} type={hit.content_type} section={section}"
                )
                if hit.text_preview:
                    lines.append(f"  - {hit.text_preview[:220]}")
            lines.append("")
    return "\n".join(lines)


def run(
    *,
    chunks_path: Path,
    eval_file: Path,
    embeddings_path: Path,
    manifest_path: Path,
    output_dir: Path,
    top_k: int,
    device: str | None,
    batch_size: int,
    max_seq_length: int | None,
    tag: str | None,
) -> None:
    suite = _load_suite(eval_file)
    manifest = load_manifest(manifest_path)
    index = LocalDenseIndex.load(
        chunks_path=chunks_path,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
    )
    embedder = SentenceTransformerEmbedder(
        manifest.model_name,
        device=device,
        batch_size=batch_size,
        normalize_embeddings=True,
        max_seq_length=max_seq_length,
        show_progress_bar=False,
    )
    evaluator = DenseRetrievalEvaluator(index=index, embedder=embedder)
    report = evaluator.evaluate(suite, top_k=top_k)

    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = _safe_tag(tag)
    json_path = output_dir / f"dense_retrieval_eval_report{suffix}.json"
    md_path = output_dir / f"dense_retrieval_eval_report{suffix}.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    print(json.dumps({
        "suite_name": report.suite_name,
        "model_name": report.model_name,
        "query_count": report.query_count,
        "top_k": report.top_k,
        "recall_at_1": report.recall_at_1,
        "recall_at_3": report.recall_at_3,
        "recall_at_5": report.recall_at_5,
        "mrr": report.mrr,
        "no_relevant_in_top_k": report.no_relevant_in_top_k,
        "tag": tag or "",
    }, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {md_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local dense retrieval with a labeled query suite")
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--eval-file", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--tag", default=None, help="Optional experiment tag; prevents report overwrite")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    args = parser.parse_args()

    parent = args.chunks_json.parent
    run(
        chunks_path=args.chunks_json,
        eval_file=args.eval_file,
        embeddings_path=args.embeddings or parent / "embeddings.npy",
        manifest_path=args.manifest or parent / "embedding_manifest.json",
        output_dir=args.output_dir or parent / "evaluation",
        top_k=args.top_k,
        device=None if args.device.lower() == "auto" else args.device,
        batch_size=args.batch_size,
        max_seq_length=args.max_seq_length,
        tag=args.tag,
    )


if __name__ == "__main__":
    main()
