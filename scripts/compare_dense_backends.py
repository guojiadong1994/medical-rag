from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.retrieval import (
    DEFAULT_MILVUS_COLLECTION,
    DEFAULT_MILVUS_URI,
    LocalDenseIndex,
    MilvusDenseIndex,
    build_milvus_filter,
    compare_dense_rankings,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_markdown(query: str, comparison: dict, local: object, milvus: object) -> str:
    lines = [
        "# Local Dense vs Milvus Dense",
        "",
        f"Query: {query}",
        "",
        f"- compared_k: {comparison['compared_k']}",
        f"- overlap_ratio: {comparison['overlap_ratio']:.3f}",
        f"- same_rank_ratio: {comparison['same_rank_ratio']:.3f}",
        f"- first_rank_mismatch: {comparison['first_rank_mismatch'] or '—'}",
        "",
        "| Rank | Local | Milvus | Local score | Milvus score |",
        "|---:|---|---|---:|---:|",
    ]
    for index, (left, right) in enumerate(zip(local.hits, milvus.hits), start=1):
        lines.append(
            f"| {index} | `{left.chunk_id}` | `{right.chunk_id}` | "
            f"{left.score:.6f} | {right.score:.6f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare exact local dense ranking with Milvus dense ranking"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--uri", default=DEFAULT_MILVUS_URI)
    parser.add_argument("--token", default=None)
    parser.add_argument("--collection", default=DEFAULT_MILVUS_COLLECTION)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--source-file", default=None)
    parser.add_argument("--content-type", choices=["narrative", "table"], default=None)
    parser.add_argument("--section", default=None)
    parser.add_argument("--page", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    parent = args.chunks_json.parent
    manifest_path = args.manifest or parent / "embedding_manifest.json"
    manifest = load_manifest(manifest_path)
    embedder = SentenceTransformerEmbedder(
        manifest.model_name,
        device=None if args.device.lower() == "auto" else args.device,
        batch_size=args.batch_size,
        normalize_embeddings=True,
        max_seq_length=args.max_seq_length,
        show_progress_bar=False,
    )

    filter_expr = build_milvus_filter(
        document_id=args.document_id,
        source_file=args.source_file,
        content_type=args.content_type,
        section=args.section,
        page=args.page,
    )
    if filter_expr:
        raise ValueError(
            "V1 backend comparison is intentionally unfiltered because LocalDenseIndex has no "
            "metadata-filter path yet. Use search_dense_milvus.py to verify metadata filters."
        )

    local_index = LocalDenseIndex.load(
        chunks_path=args.chunks_json,
        embeddings_path=args.embeddings or parent / "embeddings.npy",
        manifest_path=manifest_path,
    )
    milvus_index = MilvusDenseIndex(
        uri=args.uri,
        token=args.token,
        collection_name=args.collection,
        manifest=manifest,
    )

    # Make Milvus query-ready before LocalDenseIndex performs the first MPS forward pass.
    milvus_index.ensure_loaded()

    local_response = local_index.search(args.query, embedder=embedder, top_k=args.top_k)
    milvus_response = milvus_index.search(args.query, embedder=embedder, top_k=args.top_k)
    comparison = compare_dense_rankings(local_response, milvus_response)
    payload = {
        "query": args.query,
        "model_name": manifest.model_name,
        "top_k": args.top_k,
        "uri": args.uri,
        "collection_name": args.collection,
        "comparison": comparison,
        "local": local_response.model_dump(mode="json"),
        "milvus": milvus_response.model_dump(mode="json"),
    }

    output_dir = args.output_dir or parent / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dense_backend_comparison_milvus_v1.json"
    md_path = output_dir / "dense_backend_comparison_milvus_v1.md"
    _write_json(json_path, payload)
    md_path.write_text(
        _render_markdown(args.query, comparison, local_response, milvus_response),
        encoding="utf-8",
    )

    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {md_path.name}")


if __name__ == "__main__":
    main()
