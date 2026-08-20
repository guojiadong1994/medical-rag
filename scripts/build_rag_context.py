from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.rag import ContextBuilderConfig, GroundedPromptBuilder, RAGContextBuilder
from medical_rag.reranking import HFSequenceClassificationReranker, HybridRerankerIndex
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build citation-ready RAG context from the stable Hybrid + Reranker pipeline"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--context-top-k", type=int, default=5)
    parser.add_argument("--max-context-chars", type=int, default=6000)
    parser.add_argument("--candidate-k", type=int, default=50)
    parser.add_argument("--rerank-k", type=int, default=20)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--reranker-model", default="BAAI/bge-reranker-base")
    parser.add_argument("--reranker-device", default="auto")
    parser.add_argument("--reranker-batch-size", type=int, default=4)
    parser.add_argument("--reranker-max-length", type=int, default=512)
    parser.add_argument("--embeddings", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    parent = args.chunks_json.parent
    output_dir = args.output_dir or parent / "rag"
    output_dir.mkdir(parents=True, exist_ok=True)
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
    )
    print(f"Loading reranker model: {args.reranker_model}")
    reranker = HFSequenceClassificationReranker(
        args.reranker_model,
        device=args.reranker_device,
        batch_size=args.reranker_batch_size,
        max_length=args.reranker_max_length,
    )
    print(f"Reranker device: {reranker.device}")
    reranked = HybridRerankerIndex(
        hybrid_index=hybrid,
        reranker=reranker,
        rerank_k=args.rerank_k,
    ).search(args.query, top_k=args.context_top_k)

    context = RAGContextBuilder(
        ContextBuilderConfig(
            top_k=args.context_top_k,
            max_context_chars=args.max_context_chars,
        )
    ).build(reranked)
    prompt = GroundedPromptBuilder().build(context)

    context_json = output_dir / "rag_context_v1.json"
    context_md = output_dir / "rag_context_v1.md"
    prompt_md = output_dir / "rag_prompt_preview_v1.md"

    context_json.write_text(
        json.dumps(context.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_lines = [
        "# RAG Context V1",
        "",
        f"- query: {context.query}",
        f"- selected_source_count: {context.selected_source_count}",
        f"- used_context_chars: {context.used_context_chars}",
        f"- max_context_chars: {context.max_context_chars}",
        f"- exact_duplicate_skipped: {context.exact_duplicate_skipped}",
        f"- budget_skipped: {context.budget_skipped}",
        f"- truncated_source_count: {context.truncated_source_count}",
        "",
        "## Context",
        "",
        context.context_text or "（无可用证据）",
    ]
    context_md.write_text("\n".join(md_lines), encoding="utf-8")

    prompt_md.write_text(
        "# System Prompt\n\n"
        + prompt.system_prompt
        + "\n\n# User Prompt\n\n"
        + prompt.user_prompt,
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "query": context.query,
                "selected_source_count": context.selected_source_count,
                "used_context_chars": context.used_context_chars,
                "max_context_chars": context.max_context_chars,
                "citation_ids": context.citation_ids,
                "exact_duplicate_skipped": context.exact_duplicate_skipped,
                "budget_skipped": context.budget_skipped,
                "truncated_source_count": context.truncated_source_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print("- rag_context_v1.json")
    print("- rag_context_v1.md")
    print("- rag_prompt_preview_v1.md")


if __name__ == "__main__":
    main()
