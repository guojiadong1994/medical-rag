from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.reranking import HFSequenceClassificationReranker, HybridRerankerIndex
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def main() -> None:
    parser = argparse.ArgumentParser(description="Dense + BM25 + RRF + neural reranker")
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
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
    reranker = HFSequenceClassificationReranker(
        args.reranker_model,
        device=args.reranker_device,
        batch_size=args.reranker_batch_size,
        max_length=args.reranker_max_length,
    )
    index = HybridRerankerIndex(
        hybrid_index=hybrid,
        reranker=reranker,
        rerank_k=args.rerank_k,
    )
    response = index.search(args.query, top_k=args.top_k)

    print(f"Query: {response.query}")
    print(
        f"Method: RRF + Reranker  candidate_k={response.candidate_k} "
        f"rerank_k={response.rerank_k} rrf_k={response.rrf_k}"
    )
    print(f"Reranker: {response.reranker_model}  device={response.reranker_device}\n")
    for hit in response.hits:
        preview = hit.text[:320].replace("\n", " ")
        print(
            f"#{hit.rank} rerank={hit.reranker_score:.6f} pre_rank={hit.pre_rerank_rank} "
            f"rrf={hit.rrf_score:.8f} dense_rank={hit.dense_rank or '-'} "
            f"bm25_rank={hit.bm25_rank or '-'} page={hit.page_start}-{hit.page_end}"
        )
        print(f"section={hit.section or '—'}")
        print(preview)
        print()

    output = parent / "hybrid_rerank_search_results.json"
    output.write_text(
        json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Artifact written to: {output.resolve()}")


if __name__ == "__main__":
    main()
