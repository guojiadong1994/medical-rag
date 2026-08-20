from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.evaluation import (
    BM25RetrievalEvaluator,
    DenseRetrievalEvaluator,
    HybridRetrievalEvaluator,
    RetrievalEvalReport,
    RetrievalEvalSuite,
)
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def _load_suite(path: Path) -> RetrievalEvalSuite:
    return RetrievalEvalSuite.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _report_row(report: RetrievalEvalReport) -> dict[str, object]:
    return {
        "method": report.retriever_name,
        "model": report.model_name,
        "recall_at_1": report.recall_at_1,
        "recall_at_3": report.recall_at_3,
        "recall_at_5": report.recall_at_5,
        "mrr": report.mrr,
        "no_relevant_in_top_k": report.no_relevant_in_top_k,
    }


def _render_markdown(reports: list[RetrievalEvalReport], suite: RetrievalEvalSuite) -> str:
    lines = [
        f"# Retrieval Method Comparison · {suite.name}",
        "",
        "同一份 Chunk、同一套 14 道标注问题、同一评价规则下比较 Dense、BM25 与 Hybrid RRF。",
        "",
        "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | Top-k MISS |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for report in reports:
        lines.append(
            f"| {report.retriever_name} | {report.recall_at_1:.3f} | "
            f"{report.recall_at_3:.3f} | {report.recall_at_5:.3f} | "
            f"{report.mrr:.3f} | {report.no_relevant_in_top_k} |"
        )

    lines.extend(["", "## Per-query first relevant rank", ""])
    query_ids = [case.id for case in suite.cases]
    report_by_method = {r.retriever_name: r for r in reports}
    methods = [r.retriever_name for r in reports]
    lines.append("| ID | Query | " + " | ".join(methods) + " |")
    lines.append("|---|---|" + "|".join(["---:"] * len(methods)) + "|")
    for case_id in query_ids:
        case = next(item for item in suite.cases if item.id == case_id)
        ranks = []
        for method in methods:
            result = next(x for x in report_by_method[method].results if x.id == case_id)
            ranks.append(str(result.first_relevant_rank or "MISS"))
        query = case.query.replace("|", "\\|")
        lines.append(f"| {case_id} | {query} | " + " | ".join(ranks) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Dense, BM25 and Dense+BM25 RRF on the same retrieval suite"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--eval-file", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=30)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--dense-weight", type=float, default=1.0)
    parser.add_argument("--bm25-weight", type=float, default=1.0)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--tag", default="stable_hybrid_v1", help="Experiment tag used in output filenames")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    args = parser.parse_args()

    parent = args.chunks_json.parent
    output_dir = args.output_dir or parent / "evaluation"
    suite = _load_suite(args.eval_file)
    embeddings_path = args.embeddings or parent / "embeddings.npy"
    manifest_path = args.manifest or parent / "embedding_manifest.json"
    manifest = load_manifest(manifest_path)

    dense_index = LocalDenseIndex.load(
        chunks_path=args.chunks_json,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
    )
    bm25_index = LocalBM25Index.load(args.chunks_json)
    embedder = SentenceTransformerEmbedder(
        manifest.model_name,
        device=None if args.device.lower() == "auto" else args.device,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        max_seq_length=args.max_seq_length,
        show_progress_bar=False,
    )
    hybrid_index = ReciprocalRankFusionIndex(
        dense_index=dense_index,
        bm25_index=bm25_index,
        embedder=embedder,
        candidate_k=args.candidate_k,
        rrf_k=args.rrf_k,
        dense_weight=args.dense_weight,
        bm25_weight=args.bm25_weight,
    )

    reports = [
        DenseRetrievalEvaluator(index=dense_index, embedder=embedder).evaluate(
            suite, top_k=args.top_k
        ),
        BM25RetrievalEvaluator(index=bm25_index).evaluate(suite, top_k=args.top_k),
        HybridRetrievalEvaluator(index=hybrid_index).evaluate(suite, top_k=args.top_k),
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "suite_name": suite.name,
        "query_count": len(suite.cases),
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "rrf_k": args.rrf_k,
        "dense_weight": args.dense_weight,
        "bm25_weight": args.bm25_weight,
        "methods": [_report_row(report) for report in reports],
        "reports": [report.model_dump(mode="json") for report in reports],
    }
    safe_tag = re.sub(r"[^0-9A-Za-z._-]+", "_", args.tag).strip("_")
    suffix = f"_{safe_tag}" if safe_tag else ""
    json_path = output_dir / f"retrieval_methods_comparison{suffix}.json"
    md_path = output_dir / f"retrieval_methods_comparison{suffix}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(reports, suite), encoding="utf-8")

    print(json.dumps({
        "suite_name": suite.name,
        "query_count": len(suite.cases),
        "methods": [_report_row(report) for report in reports],
    }, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {md_path.name}")


if __name__ == "__main__":
    main()
