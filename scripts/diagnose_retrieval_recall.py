from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.evaluation import RetrievalEvalSuite, diagnose_recall
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex


def _load_suite(path: Path) -> RetrievalEvalSuite:
    return RetrievalEvalSuite.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _fmt_rank(rank: int | None) -> str:
    return str(rank) if rank is not None else "MISS"


def _render_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    lines = [
        "# Retrieval Recall Deep Diagnosis",
        "",
        "这份报告不是再看一个总 Recall 数字，而是追踪正确证据在检索流水线中的去向：",
        "`Chunk 是否存在 → Dense 排名 → BM25 排名 → candidate_k 截断 → RRF 最终排名`。",
        "",
        f"- suite: `{payload['suite_name']}`",
        f"- top_k: `{payload['top_k']}`",
        f"- candidate_k: `{payload['candidate_k']}`",
        f"- deep_k: `{payload['deep_k']}`",
        f"- cases: **{summary['case_count']}**",
        f"- operational Hybrid Top-K misses: **{summary['hybrid_topk_miss_count']}**",
        "",
        "## Category summary",
        "",
        "| Category | Count |",
        "|---|---:|",
    ]
    for category, count in summary["category_counts"].items():
        lines.append(f"| {category} | {count} |")

    lines.extend([
        "",
        "## Miss / weak cases",
        "",
    ])

    weak = [item for item in payload["cases"] if item["category"] != "HIT"]
    if not weak:
        lines.append("当前所有问题的正确证据均已进入 Hybrid Top-K。")
        return "\n".join(lines)

    for item in weak:
        lines.extend([
            f"### {item['case_id']} · {item['query']}",
            "",
            f"- category: `{item['category']}`",
            f"- evidence chunks in chunks.json: **{item['evidence_chunk_count']}**",
            f"- Dense first relevant rank: **{_fmt_rank(item['dense']['first_relevant_rank'])}**",
            f"- BM25 first relevant rank: **{_fmt_rank(item['bm25']['first_relevant_rank'])}**",
            f"- Hybrid (deep candidate pool) first relevant rank: **{_fmt_rank(item['deep_hybrid']['first_relevant_rank'])}**",
            f"- Hybrid operational Top-K rank: **{_fmt_rank(item['operational_hybrid_rank'])}**",
            f"- diagnosis: {item['explanation']}",
            f"- next action: {item['recommendation']}",
            "",
        ])
        if item["query_bm25_tokens"]:
            lines.append("- Query BM25 tokens: `" + " | ".join(item["query_bm25_tokens"][:30]) + "`")
        if item["evidence_bm25_token_overlap"]:
            lines.append("- Query↔evidence BM25 overlap: `" + " | ".join(item["evidence_bm25_token_overlap"][:30]) + "`")
        if item["evidence_preview"]:
            lines.extend(["", "> Evidence preview: " + item["evidence_preview"][:500]])
        lines.append("")

    lines.extend([
        "## How to read the categories",
        "",
        "- `EVIDENCE_MISSING_FROM_CHUNKS`: 正确证据在 Chunk 层就不存在，先查 Parsing/Chunk/评测标注。",
        "- `FUSION_RANKING_LOSS`: 某一路 Top-K 已命中，但 RRF 融合把它挤掉。",
        "- `FUSION_TOPK_LOSS`: 证据进入 candidate_k 候选池，但没进入最终 Top-K。",
        "- `CANDIDATE_POOL_BOTTLENECK`: candidate_k 太小，扩大候选池即可把证据送进融合。",
        "- `WEAK_RECALL*`: Dense/BM25 原始排名都偏后，需要修 Query/Retriever/Chunk，而不是先上 Reranker。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deep-diagnose why labeled evidence misses Hybrid Top-K"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--eval-file", type=Path, required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--candidate-k", type=int, default=30)
    parser.add_argument(
        "--deep-k",
        type=int,
        default=0,
        help="Deep diagnostic depth; 0 means inspect all chunks",
    )
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--dense-weight", type=float, default=1.0)
    parser.add_argument("--bm25-weight", type=float, default=1.0)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--tag", default="hybrid_v1")
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

    deep_k = None if args.deep_k == 0 else args.deep_k
    diagnoses = diagnose_recall(
        suite,
        dense_index=dense_index,
        bm25_index=bm25_index,
        embedder=embedder,
        top_k=args.top_k,
        candidate_k=args.candidate_k,
        deep_k=deep_k,
        rrf_k=args.rrf_k,
        dense_weight=args.dense_weight,
        bm25_weight=args.bm25_weight,
    )

    rows = [asdict(item) for item in diagnoses]
    category_counts = Counter(item.category for item in diagnoses)
    operational_misses = [item for item in diagnoses if item.operational_hybrid_rank is None]
    actual_deep_k = len(dense_index.chunks) if deep_k is None else min(deep_k, len(dense_index.chunks))
    payload = {
        "suite_name": suite.name,
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "deep_k": actual_deep_k,
        "rrf_k": args.rrf_k,
        "dense_weight": args.dense_weight,
        "bm25_weight": args.bm25_weight,
        "summary": {
            "case_count": len(diagnoses),
            "hybrid_topk_miss_count": len(operational_misses),
            "category_counts": dict(category_counts),
        },
        "cases": rows,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_tag = re.sub(r"[^0-9A-Za-z._-]+", "_", args.tag).strip("_") or "current"
    json_path = output_dir / f"retrieval_recall_diagnosis_{safe_tag}.json"
    md_path = output_dir / f"retrieval_recall_diagnosis_{safe_tag}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print("\nMiss / weak cases:")
    for item in diagnoses:
        if item.category == "HIT":
            continue
        print(
            f"- {item.case_id}: {item.category} | "
            f"dense={_fmt_rank(item.dense.first_relevant_rank)} "
            f"bm25={_fmt_rank(item.bm25.first_relevant_rank)} "
            f"deep_hybrid={_fmt_rank(item.deep_hybrid.first_relevant_rank)} "
            f"operational={_fmt_rank(item.operational_hybrid_rank)}"
        )
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {md_path.name}")


if __name__ == "__main__":
    main()
