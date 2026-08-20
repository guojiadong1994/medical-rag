from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.generation import (
    GroundedAnswerGenerator,
    OpenAICompatibleChatClient,
    OpenAICompatibleConfig,
)
from medical_rag.rag import ContextBuilderConfig, RAGContextBuilder, citation_summary_lines
from medical_rag.reranking import HFSequenceClassificationReranker, HybridRerankerIndex
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def _resolve_setting(cli_value: str | None, env_name: str) -> str | None:
    if cli_value is not None and cli_value.strip():
        return cli_value.strip()
    value = os.getenv(env_name)
    return value.strip() if value and value.strip() else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Retrieval -> RRF -> Reranker -> Context -> LLM -> Citation validation"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--query", required=True)

    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-api-key-env", default="MEDICAL_RAG_LLM_API_KEY")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--llm-timeout", type=float, default=60.0)

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

    base_url = _resolve_setting(args.llm_base_url, "MEDICAL_RAG_LLM_BASE_URL")
    model = _resolve_setting(args.llm_model, "MEDICAL_RAG_LLM_MODEL")
    api_key = os.getenv(args.llm_api_key_env)

    if not base_url:
        raise SystemExit(
            "Missing LLM base URL. Use --llm-base-url or set MEDICAL_RAG_LLM_BASE_URL."
        )
    if not model:
        raise SystemExit(
            "Missing LLM model. Use --llm-model or set MEDICAL_RAG_LLM_MODEL."
        )

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

    client = OpenAICompatibleChatClient(
        OpenAICompatibleConfig(
            base_url=base_url,
            model=model,
            api_key=api_key,
            temperature=args.temperature,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.llm_timeout,
        )
    )
    result = GroundedAnswerGenerator(client).generate(context)

    result_json = output_dir / "rag_generation_v1.json"
    answer_md = output_dir / "rag_answer_v1.md"
    trace_md = output_dir / "rag_generation_trace_v1.md"

    result_json.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    answer_md.write_text(
        "# RAG Answer V1\n\n"
        f"## Question\n\n{result.query}\n\n"
        f"## Answer\n\n{result.answer}\n\n"
        "## Citations\n\n"
        + ("\n".join(f"- {line}" for line in citation_summary_lines(context)) or "- 无")
        + "\n",
        encoding="utf-8",
    )

    trace_lines = [
        "# RAG Generation Trace V1",
        "",
        f"- provider: {result.provider}",
        f"- model: {result.model}",
        f"- llm_called: {result.llm_called}",
        f"- selected_source_count: {context.selected_source_count}",
        f"- used_context_chars: {context.used_context_chars}",
        f"- cited_ids: {result.citation_validation.cited_ids}",
        f"- unknown_ids: {result.citation_validation.unknown_ids}",
        f"- grounding_status: {result.grounding_check.status}",
        f"- grounding_passed: {result.grounding_check.passed}",
        f"- prompt_tokens: {result.usage.prompt_tokens}",
        f"- completion_tokens: {result.usage.completion_tokens}",
        f"- total_tokens: {result.usage.total_tokens}",
        "",
        "## System Prompt",
        "",
        result.prompt.system_prompt,
        "",
        "## User Prompt",
        "",
        result.prompt.user_prompt,
        "",
        "## Answer",
        "",
        result.answer,
    ]
    trace_md.write_text("\n".join(trace_lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "query": result.query,
                "provider": result.provider,
                "model": result.model,
                "llm_called": result.llm_called,
                "answer": result.answer,
                "selected_source_count": context.selected_source_count,
                "citation_ids": context.citation_ids,
                "cited_ids": result.citation_validation.cited_ids,
                "unknown_ids": result.citation_validation.unknown_ids,
                "citation_valid": result.citation_validation.valid,
                "grounding_status": result.grounding_check.status,
                "grounding_passed": result.grounding_check.passed,
                "usage": result.usage.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print("- rag_generation_v1.json")
    print("- rag_answer_v1.md")
    print("- rag_generation_trace_v1.md")


if __name__ == "__main__":
    main()
