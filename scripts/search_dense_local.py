from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.retrieval import LocalDenseIndex


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_preview(response: object) -> str:
    lines = [
        "# Dense Retrieval Preview",
        "",
        f"Query: {response.query}",
        "",
        f"Model: `{response.model_name}`",
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
                f"## #{hit.rank} · score={hit.score:.6f}",
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


def run(
    chunks_path: Path,
    embeddings_path: Path,
    manifest_path: Path,
    output_dir: Path,
    *,
    query: str,
    top_k: int,
    device: str | None,
    batch_size: int,
    max_seq_length: int | None,
) -> None:
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
    response = index.search(query, embedder=embedder, top_k=top_k)

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dense_search_results.json"
    preview_path = output_dir / "dense_search_preview.md"
    _write_json(json_path, response.model_dump(mode="json"))
    preview_path.write_text(_render_preview(response), encoding="utf-8")

    print(f"\nQuery: {response.query}")
    print(f"Model: {response.model_name}")
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
            f"\n#{hit.rank}  score={hit.score:.6f}  "
            f"page={page_label}  type={hit.content_type}"
        )
        print(f"section={hit.section or '—'}")
        print(text)

    print(f"\nArtifacts written to: {output_dir.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local cosine/dot-product retrieval used to validate embeddings before Milvus"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    args = parser.parse_args()

    parent = args.chunks_json.parent
    run(
        args.chunks_json,
        args.embeddings or parent / "embeddings.npy",
        args.manifest or parent / "embedding_manifest.json",
        args.output_dir or parent,
        query=args.query,
        top_k=args.top_k,
        device=None if args.device.lower() == "auto" else args.device,
        batch_size=args.batch_size,
        max_seq_length=args.max_seq_length,
    )


if __name__ == "__main__":
    main()
