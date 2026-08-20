from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def main() -> None:
    parser = argparse.ArgumentParser(description="Dense + BM25 retrieval fused by RRF")
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=30)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--dense-weight", type=float, default=1.0)
    parser.add_argument("--bm25-weight", type=float, default=1.0)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    args = parser.parse_args()

    parent = args.chunks_json.parent
    embeddings_path = args.embeddings or parent / "embeddings.npy"
    manifest_path = args.manifest or parent / "embedding_manifest.json"
    manifest = load_manifest(manifest_path)
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
    response = hybrid.search(args.query, top_k=args.top_k)

    print(f"Query: {response.query}")
    print(f"Method: RRF  candidate_k={response.candidate_k}  rrf_k={response.rrf_k}\n")
    for hit in response.hits:
        section = hit.section or "—"
        preview = hit.text[:320].replace("\n", " ")
        print(
            f"#{hit.rank} fused={hit.score:.8f} "
            f"dense_rank={hit.dense_rank or '-'} bm25_rank={hit.bm25_rank or '-'} "
            f"page={hit.page_start}-{hit.page_end} type={hit.content_type}"
        )
        print(f"section={section}")
        print(preview)
        print()

    output = parent / "hybrid_search_results.json"
    output.write_text(
        json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Artifact written to: {output.resolve()}")


if __name__ == "__main__":
    main()
