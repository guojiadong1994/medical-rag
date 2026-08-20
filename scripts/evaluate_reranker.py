from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.evaluation import (
    HybridRetrievalEvaluator,
    RerankedHybridRetrievalEvaluator,
    RetrievalEvalReport,
    RetrievalEvalSuite,
)
from medical_rag.reranking import HFSequenceClassificationReranker, HybridRerankerIndex
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def _load_suite(path: Path) -> RetrievalEvalSuite:
    return RetrievalEvalSuite.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _summary(report: RetrievalEvalReport) -> dict[str, object]:
    return {
        "method": report.retriever_name,
        "model": report.model_name,
        "recall_at_1": report.recall_at_1,
        "recall_at_3": report.recall_at_3,
        "recall_at_5": report.recall_at_5,
        "mrr": report.mrr,
        "no_relevant_in_top_k": report.no_relevant_in_top_k,
    }


def _rank_map(report: RetrievalEvalReport) -> dict[str, int | None]:
    return {result.id: result.first_relevant_rank for result in report.results}


def _render_markdown(
    *,
    suite: RetrievalEvalSuite,
    hybrid: RetrievalEvalReport,
    reranked: RetrievalEvalReport,
    config: dict[str, object],
) -> str:
    before = _rank_map(hybrid)
    after = _rank_map(reranked)
    lines = [
        f"# Reranker V1 Evaluation · {suite.name}",
        "",
        "固定 Chunk、Embedding、BM25、RRF 配置，仅增加 Cross-Encoder Reranker，观察排序质量是否提升。",
        "",
        "## Configuration",
        "",
        f"- candidate_k: {config['candidate_k']}",
        f"- rerank_k: {config['rerank_k']}",
        f"- top_k: {config['top_k']}",
        f"- reranker_model: {config['reranker_model']}",
        f"- reranker_device: {config['reranker_device']}",
        "",
        "## Summary",
        "",
        "| Method | Recall@1 | Recall@3 | Recall@5 | MRR | Top-k MISS |",
        "|---|---:|---:|---:|---:|---:|",
        (
            f"| Hybrid RRF | {hybrid.recall_at_1:.3f} | {hybrid.recall_at_3:.3f} | "
            f"{hybrid.recall_at_5:.3f} | {hybrid.mrr:.3f} | {hybrid.no_relevant_in_top_k} |"
        ),
        (
            f"| Hybrid + Reranker | {reranked.recall_at_1:.3f} | "
            f"{reranked.recall_at_3:.3f} | {reranked.recall_at_5:.3f} | "
            f"{reranked.mrr:.3f} | {reranked.no_relevant_in_top_k} |"
        ),
        "",
        "## Per-query rank movement",
        "",
        "| ID | Query | Before | After | Δ |",
        "|---|---|---:|---:|---:|",
    ]
    for case in suite.cases:
        b = before[case.id]
        a = after[case.id]
        if b is None and a is None:
            delta = "—"
        elif b is None:
            delta = "rescued"
        elif a is None:
            delta = "lost"
        else:
            # Positive means moved toward rank 1.
            delta = f"{b - a:+d}"
        lines.append(
            f"| {case.id} | {case.query.replace('|', '\\|')} | "
            f"{b or 'MISS'} | {a or 'MISS'} | {delta} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Hybrid RRF before/after reranking")
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--eval-file", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--rerank-k", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--dense-weight", type=float, default=1.0)
    parser.add_argument("--bm25-weight", type=float, default=1.0)
    parser.add_argument("--reranker-model", default="BAAI/bge-reranker-base")
    parser.add_argument("--reranker-device", default="auto")
    parser.add_argument("--reranker-batch-size", type=int, default=4)
    parser.add_argument("--reranker-max-length", type=int, default=512)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--tag", default="reranker_v1")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    args = parser.parse_args()

    if args.rerank_k < args.top_k:
        raise ValueError("rerank_k must be >= top_k")

    parent = args.chunks_json.parent
    output_dir = args.output_dir or parent / "evaluation"
    embeddings_path = args.embeddings or parent / "embeddings.npy"
    manifest_path = args.manifest or parent / "embedding_manifest.json"
    manifest = load_manifest(manifest_path)
    suite = _load_suite(args.eval_file)

    dense = LocalDenseIndex.load(
        chunks_path=args.chunks_json,
        embeddings_path=embeddings_path,
        manifest_path=manifest_path,
    )
    bm25 = LocalBM25Index.load(args.chunks_json)
    embedder = SentenceTransformerEmbedder(
        manifest.model_name,
        device=None if args.device.lower() == "auto" else args.device,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        max_seq_length=args.max_seq_length,
        show_progress_bar=False,
    )
    hybrid = ReciprocalRankFusionIndex(
        dense_index=dense,
        bm25_index=bm25,
        embedder=embedder,
        candidate_k=args.candidate_k,
        rrf_k=args.rrf_k,
        dense_weight=args.dense_weight,
        bm25_weight=args.bm25_weight,
    )

    hybrid_report = HybridRetrievalEvaluator(index=hybrid).evaluate(suite, top_k=args.top_k)

    print(f"Loading reranker model: {args.reranker_model}")
    reranker = HFSequenceClassificationReranker(
        args.reranker_model,
        device=args.reranker_device,
        batch_size=args.reranker_batch_size,
        max_length=args.reranker_max_length,
    )
    print(f"Reranker device: {reranker.device}")
    reranked_index = HybridRerankerIndex(
        hybrid_index=hybrid,
        reranker=reranker,
        rerank_k=args.rerank_k,
    )
    started = time.perf_counter()
    reranked_report = RerankedHybridRetrievalEvaluator(index=reranked_index).evaluate(
        suite, top_k=args.top_k
    )
    elapsed = time.perf_counter() - started

    config = {
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "rerank_k": args.rerank_k,
        "rrf_k": args.rrf_k,
        "dense_weight": args.dense_weight,
        "bm25_weight": args.bm25_weight,
        "reranker_model": reranker.model_name,
        "reranker_device": reranker.device,
        "reranker_batch_size": args.reranker_batch_size,
        "reranker_max_length": args.reranker_max_length,
        "elapsed_seconds": round(elapsed, 3),
    }
    payload = {
        "suite_name": suite.name,
        "query_count": len(suite.cases),
        "config": config,
        "before": _summary(hybrid_report),
        "after": _summary(reranked_report),
        "delta": {
            "recall_at_1": round(reranked_report.recall_at_1 - hybrid_report.recall_at_1, 6),
            "recall_at_3": round(reranked_report.recall_at_3 - hybrid_report.recall_at_3, 6),
            "recall_at_5": round(reranked_report.recall_at_5 - hybrid_report.recall_at_5, 6),
            "mrr": round(reranked_report.mrr - hybrid_report.mrr, 6),
            "top_k_miss": (
                reranked_report.no_relevant_in_top_k - hybrid_report.no_relevant_in_top_k
            ),
        },
        "reports": {
            "hybrid_rrf": hybrid_report.model_dump(mode="json"),
            "hybrid_rerank": reranked_report.model_dump(mode="json"),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_tag = re.sub(r"[^0-9A-Za-z._-]+", "_", args.tag).strip("_")
    suffix = f"_{safe_tag}" if safe_tag else ""
    json_path = output_dir / f"reranker_comparison{suffix}.json"
    md_path = output_dir / f"reranker_comparison{suffix}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(
        _render_markdown(
            suite=suite,
            hybrid=hybrid_report,
            reranked=reranked_report,
            config=config,
        ),
        encoding="utf-8",
    )

    print(json.dumps({
        "suite_name": suite.name,
        "query_count": len(suite.cases),
        "before": _summary(hybrid_report),
        "after": _summary(reranked_report),
        "delta": payload["delta"],
        "elapsed_seconds": config["elapsed_seconds"],
    }, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {md_path.name}")


if __name__ == "__main__":
    main()
