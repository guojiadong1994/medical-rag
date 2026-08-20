from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.retrieval import (
    DEFAULT_MILVUS_COLLECTION,
    DEFAULT_MILVUS_URI,
    MilvusDenseIndex,
    build_milvus_filter,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_preview(response: object, filter_expr: str | None) -> str:
    lines = [
        "# Milvus Dense Retrieval Preview",
        "",
        f"Query: {response.query}",
        "",
        f"Model: `{response.model_name}`",
        "",
        f"Filter: `{filter_expr or '—'}`",
        "",
    ]
    for hit in response.hits:
        page_label = (
            f"PAGE {hit.page_start}"
            if hit.page_start == hit.page_end
            else f"PAGES {hit.page_start}-{hit.page_end}"
        )
        lines.extend(
            [
                f"## #{hit.rank} · cosine={hit.score:.6f}",
                "",
                f"- chunk_id: `{hit.chunk_id}`",
                f"- type: `{hit.content_type}`",
                f"- section: {hit.section or '—'}",
                f"- {page_label}",
                "",
                hit.text,
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Dense search against Milvus/Milvus Lite")
    parser.add_argument("chunks_json", type=Path, help="Used to locate embedding_manifest.json")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
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
    manifest = load_manifest(args.manifest or parent / "embedding_manifest.json")
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
    index = MilvusDenseIndex(
        uri=args.uri,
        token=args.token,
        collection_name=args.collection,
        manifest=manifest,
    )
    response = index.search(
        args.query,
        embedder=embedder,
        top_k=args.top_k,
        filter_expr=filter_expr,
    )

    output_dir = args.output_dir or parent
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = response.model_dump(mode="json")
    payload["backend"] = "milvus"
    payload["uri"] = args.uri
    payload["collection_name"] = args.collection
    payload["filter"] = filter_expr
    json_path = output_dir / "milvus_dense_search_results.json"
    preview_path = output_dir / "milvus_dense_search_preview.md"
    _write_json(json_path, payload)
    preview_path.write_text(_render_preview(response, filter_expr), encoding="utf-8")

    print(f"\nQuery: {response.query}")
    print(f"Milvus: {args.uri} / {args.collection}")
    print(f"Filter: {filter_expr or '—'}")
    for hit in response.hits:
        page_label = (
            str(hit.page_start)
            if hit.page_start == hit.page_end
            else f"{hit.page_start}-{hit.page_end}"
        )
        text = " ".join(hit.text.split())
        if len(text) > 180:
            text = text[:180] + "…"
        print(
            f"\n#{hit.rank} cosine={hit.score:.6f} page={page_label} "
            f"type={hit.content_type}"
        )
        print(f"section={hit.section or '—'}")
        print(text)

    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {preview_path.name}")


if __name__ == "__main__":
    main()
