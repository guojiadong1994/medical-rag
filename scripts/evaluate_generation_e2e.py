from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.evaluation import (
    EvidenceGroundingJudge,
    GenerationEvalCaseResult,
    RetrievalEvalSuite,
    build_generation_eval_report,
    case_overall_passed,
    generation_report_markdown,
)
from medical_rag.generation import GroundedAnswerGenerator, OpenAICompatibleChatClient, OpenAICompatibleConfig
from medical_rag.rag import ContextBuilderConfig, RAGContextBuilder
from medical_rag.reranking import HFSequenceClassificationReranker, HybridRerankerIndex
from medical_rag.retrieval import LocalBM25Index, LocalDenseIndex, ReciprocalRankFusionIndex


def _resolve(cli_value: str | None, *env_names: str) -> str | None:
    if cli_value and cli_value.strip():
        return cli_value.strip()
    for name in env_names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _write_checkpoint(path: Path, results: list[GenerationEvalCaseResult]) -> None:
    path.write_text(
        json.dumps([item.model_dump(mode="json") for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run 14-case end-to-end RAG generation + claim-evidence grounding evaluation"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument("--eval-file", type=Path, default=Path("doc/evaluation/hypertension_2024_retrieval_eval_v2.json"))
    parser.add_argument("--case-id", action="append", default=[], help="Optional case id; may be repeated")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fail-fast", action="store_true")

    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-api-key-env", default="MEDICAL_RAG_LLM_API_KEY")
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--llm-timeout", type=float, default=90.0)

    parser.add_argument("--judge-base-url", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--judge-api-key-env", default="MEDICAL_RAG_JUDGE_API_KEY")
    parser.add_argument("--judge-max-output-tokens", type=int, default=2048)
    parser.add_argument("--judge-timeout", type=float, default=120.0)

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

    llm_base_url = _resolve(args.llm_base_url, "MEDICAL_RAG_LLM_BASE_URL")
    llm_model = _resolve(args.llm_model, "MEDICAL_RAG_LLM_MODEL")
    llm_key = _resolve(None, args.llm_api_key_env)
    if not llm_base_url or not llm_model:
        raise SystemExit("Missing generation LLM base URL/model")

    judge_base_url = _resolve(args.judge_base_url, "MEDICAL_RAG_JUDGE_BASE_URL") or llm_base_url
    judge_model = _resolve(args.judge_model, "MEDICAL_RAG_JUDGE_MODEL") or llm_model
    judge_key = _resolve(None, args.judge_api_key_env, args.llm_api_key_env)

    suite = RetrievalEvalSuite.model_validate_json(args.eval_file.read_text(encoding="utf-8"))
    cases = suite.cases
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if case.id in wanted]
        missing = wanted - {case.id for case in cases}
        if missing:
            raise SystemExit(f"Unknown case ids: {sorted(missing)}")
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be positive")
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No evaluation cases selected")

    parent = args.chunks_json.parent
    output_dir = args.output_dir or parent / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "generation_e2e_checkpoint_v1.json"

    manifest_path = args.manifest or parent / "embedding_manifest.json"
    embeddings_path = args.embeddings or parent / "embeddings.npy"
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
    reranked_index = HybridRerankerIndex(
        hybrid_index=hybrid,
        reranker=reranker,
        rerank_k=args.rerank_k,
    )
    context_builder = RAGContextBuilder(
        ContextBuilderConfig(top_k=args.context_top_k, max_context_chars=args.max_context_chars)
    )

    generation_client = OpenAICompatibleChatClient(
        OpenAICompatibleConfig(
            base_url=llm_base_url,
            model=llm_model,
            api_key=llm_key,
            temperature=0.0,
            max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.llm_timeout,
        )
    )
    judge_client = OpenAICompatibleChatClient(
        OpenAICompatibleConfig(
            base_url=judge_base_url,
            model=judge_model,
            api_key=judge_key,
            temperature=0.0,
            max_output_tokens=args.judge_max_output_tokens,
            timeout_seconds=args.judge_timeout,
        )
    )
    answer_generator = GroundedAnswerGenerator(generation_client)
    judge = EvidenceGroundingJudge(judge_client)

    results: list[GenerationEvalCaseResult] = []
    total_cases = len(cases)
    for index, case in enumerate(cases, start=1):
        print(f"\n[{index}/{total_cases}] {case.id}: {case.query}")
        started = time.perf_counter()
        try:
            reranked = reranked_index.search(case.query, top_k=args.context_top_k)
            context = context_builder.build(reranked)
            generation = answer_generator.generate(context)
            semantic = judge.judge(generation, case.expected_facts)
            elapsed = round(time.perf_counter() - started, 3)
            item = GenerationEvalCaseResult(
                id=case.id,
                query=case.query,
                expected_facts=case.expected_facts,
                generation=generation,
                semantic_grounding=semantic,
                structural_citation_passed=bool(
                    generation.grounding_check.passed and generation.citation_validation.valid
                ),
                overall_passed=case_overall_passed(generation, semantic),
                elapsed_seconds=elapsed,
            )
            print(json.dumps({
                "answer_verdict": semantic.judgment.answer_verdict,
                "faithfulness_score": semantic.metrics.faithfulness_score,
                "expected_fact_coverage": semantic.metrics.expected_fact_coverage,
                "fully_grounded": semantic.metrics.fully_grounded,
                "structural_citation_passed": item.structural_citation_passed,
                "overall_passed": item.overall_passed,
                "generation_tokens": generation.usage.total_tokens,
                "elapsed_seconds": elapsed,
            }, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001 - batch evaluation must persist per-case failures
            elapsed = round(time.perf_counter() - started, 3)
            item = GenerationEvalCaseResult(
                id=case.id,
                query=case.query,
                expected_facts=case.expected_facts,
                elapsed_seconds=elapsed,
                error=f"{type(exc).__name__}: {exc}",
            )
            print(f"ERROR: {item.error}")
            if args.fail_fast:
                results.append(item)
                _write_checkpoint(checkpoint_path, results)
                raise
        results.append(item)
        _write_checkpoint(checkpoint_path, results)

    report = build_generation_eval_report(
        suite_name=suite.name,
        suite_version=suite.version,
        expected_query_count=len(cases),
        generation_model=llm_model,
        judge_model=judge_model,
        context_top_k=args.context_top_k,
        max_context_chars=args.max_context_chars,
        candidate_k=args.candidate_k,
        rerank_k=args.rerank_k,
        rrf_k=args.rrf_k,
        results=results,
    )

    json_path = output_dir / "generation_e2e_eval_v1.json"
    md_path = output_dir / "generation_e2e_eval_v1.md"
    json_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(generation_report_markdown(report), encoding="utf-8")

    summary = {
        "suite_name": report.suite_name,
        "query_count": report.query_count,
        "completed_count": report.completed_count,
        "error_count": report.error_count,
        "generation_model": report.generation_model,
        "judge_model": report.judge_model,
        "structural_citation_pass_rate": report.structural_citation_pass_rate,
        "answer_correct_rate": report.answer_correct_rate,
        "answer_at_least_partial_rate": report.answer_at_least_partial_rate,
        "fully_grounded_rate": report.fully_grounded_rate,
        "overall_pass_rate": report.overall_pass_rate,
        "mean_faithfulness_score": report.mean_faithfulness_score,
        "mean_expected_fact_coverage": report.mean_expected_fact_coverage,
        "total_generation_tokens": report.total_generation_tokens,
        "avg_generation_tokens_per_completed_case": report.avg_generation_tokens_per_completed_case,
    }
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print("- generation_e2e_checkpoint_v1.json")
    print("- generation_e2e_eval_v1.json")
    print("- generation_e2e_eval_v1.md")


if __name__ == "__main__":
    main()
