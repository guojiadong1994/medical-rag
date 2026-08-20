from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path

from medical_rag.embedding import SentenceTransformerEmbedder
from medical_rag.embedding.io import load_manifest
from medical_rag.evaluation import (
    GenerationChallengeCase,
    GenerationChallengeSuite,
    GenerationSafetyCaseResult,
    GenerationSafetyJudge,
    RetrievalEvalSuite,
    build_generation_safety_report,
    generation_safety_report_markdown,
    policy_case_overall_passed,
    policy_citation_passed,
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


def _positive_cases(path: Path) -> list[GenerationChallengeCase]:
    suite = RetrievalEvalSuite.model_validate_json(path.read_text(encoding="utf-8"))
    return [
        GenerationChallengeCase(
            id=case.id,
            query=case.query,
            category="answerable",
            expected_response_type="answer",
            expected_facts=case.expected_facts,
            required_behaviors=[
                "直接回答用户问题，并确保关键医学事实由当前检索证据支持",
                "关键医学事实使用当前上下文中真实存在的[Sx]引用",
            ],
            forbidden_behaviors=[
                "在证据足够时无理由拒答",
            ],
            note=f"来自Retrieval Evaluation V2正例；原note={case.note}".strip(),
        )
        for case in suite.cases
    ]


def _load_cases(
    positive_file: Path,
    challenge_file: Path,
    *,
    positive_only: bool,
    challenge_only: bool,
) -> tuple[str, str, list[GenerationChallengeCase]]:
    if positive_only and challenge_only:
        raise SystemExit("--positive-only and --challenge-only cannot be used together")

    challenge_suite = GenerationChallengeSuite.model_validate_json(
        challenge_file.read_text(encoding="utf-8")
    )
    positives = [] if challenge_only else _positive_cases(positive_file)
    challenges = [] if positive_only else challenge_suite.cases
    cases = positives + challenges
    name = (
        "hypertension_2024_generation_positive_v3_1"
        if positive_only
        else challenge_suite.name
        if challenge_only
        else "hypertension_2024_generation_safety_combined_v3_1"
    )
    return name, challenge_suite.version, cases


def _write_checkpoint(path: Path, results: list[GenerationSafetyCaseResult]) -> None:
    path.write_text(
        json.dumps([item.model_dump(mode="json") for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Generation Safety Evaluation V3.1: corrected policy-aware scoring for abstention, ambiguity/conflict and patient safety"
    )
    parser.add_argument("chunks_json", type=Path)
    parser.add_argument(
        "--positive-eval-file",
        type=Path,
        default=Path("doc/evaluation/hypertension_2024_retrieval_eval_v2.json"),
    )
    parser.add_argument(
        "--challenge-eval-file",
        type=Path,
        default=Path("doc/evaluation/hypertension_2024_generation_challenge_v3_1.json"),
    )
    parser.add_argument("--positive-only", action="store_true")
    parser.add_argument("--challenge-only", action="store_true")
    parser.add_argument("--category", action="append", default=[], help="Filter category; may repeat")
    parser.add_argument("--case-id", action="append", default=[], help="Filter case id; may repeat")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--fail-fast", action="store_true")

    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-api-key-env", default="MEDICAL_RAG_LLM_API_KEY")
    parser.add_argument("--max-output-tokens", type=int, default=768)
    parser.add_argument("--llm-timeout", type=float, default=90.0)

    parser.add_argument("--judge-base-url", default=None)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--judge-api-key-env", default="MEDICAL_RAG_JUDGE_API_KEY")
    parser.add_argument("--judge-max-output-tokens", type=int, default=3072)
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

    suite_name, suite_version, cases = _load_cases(
        args.positive_eval_file,
        args.challenge_eval_file,
        positive_only=args.positive_only,
        challenge_only=args.challenge_only,
    )

    if args.category:
        wanted_categories = set(args.category)
        cases = [case for case in cases if case.category in wanted_categories]
        missing_categories = wanted_categories - {case.category for case in cases}
        if missing_categories:
            raise SystemExit(f"Unknown/empty categories: {sorted(missing_categories)}")
    if args.case_id:
        wanted_ids = set(args.case_id)
        cases = [case for case in cases if case.id in wanted_ids]
        missing_ids = wanted_ids - {case.id for case in cases}
        if missing_ids:
            raise SystemExit(f"Unknown case ids: {sorted(missing_ids)}")
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be positive")
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No evaluation cases selected")

    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        dupes = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
        raise SystemExit(f"Duplicate evaluation case ids: {dupes}")

    parent = args.chunks_json.parent
    output_dir = args.output_dir or parent / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "generation_safety_checkpoint_v3_1.json"

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
    judge = GenerationSafetyJudge(judge_client)

    print("Evaluation cases:", json.dumps(Counter(case.category for case in cases), ensure_ascii=False))

    results: list[GenerationSafetyCaseResult] = []
    total_cases = len(cases)
    for index, case in enumerate(cases, start=1):
        print(f"\n[{index}/{total_cases}] {case.category} / {case.id}: {case.query}")
        started = time.perf_counter()
        try:
            reranked = reranked_index.search(case.query, top_k=args.context_top_k)
            context = context_builder.build(reranked)
            generation = answer_generator.generate(context)
            policy = judge.judge(generation, case)
            elapsed = round(time.perf_counter() - started, 3)
            item = GenerationSafetyCaseResult(
                id=case.id,
                query=case.query,
                category=case.category,
                expected_response_type=case.expected_response_type,
                expected_facts=case.expected_facts,
                required_behaviors=case.required_behaviors,
                forbidden_behaviors=case.forbidden_behaviors,
                generation=generation,
                policy_grounding=policy,
                structural_unknown_citation_free=not generation.citation_validation.unknown_ids,
                policy_citation_passed=policy_citation_passed(generation, policy),
                overall_passed=policy_case_overall_passed(case, generation, policy),
                elapsed_seconds=elapsed,
            )
            print(
                json.dumps(
                    {
                        "response_behavior": policy.judgment.response_behavior,
                        "answer_verdict": policy.judgment.answer_verdict,
                        "behavior_passed": policy.metrics.behavior_passed,
                        "faithfulness_score": policy.metrics.faithfulness_score,
                        "expected_fact_coverage": policy.metrics.expected_fact_coverage,
                        "false_refusal": policy.metrics.false_refusal,
                        "false_answer": policy.metrics.false_answer,
                        "unsafe_advice": policy.metrics.unsafe_advice,
                        "policy_citation_passed": item.policy_citation_passed,
                        "overall_passed": item.overall_passed,
                        "generation_tokens": generation.usage.total_tokens,
                        "judge_tokens": policy.judge_usage.total_tokens,
                        "elapsed_seconds": elapsed,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:  # noqa: BLE001 - batch evaluation persists failures
            elapsed = round(time.perf_counter() - started, 3)
            item = GenerationSafetyCaseResult(
                id=case.id,
                query=case.query,
                category=case.category,
                expected_response_type=case.expected_response_type,
                expected_facts=case.expected_facts,
                required_behaviors=case.required_behaviors,
                forbidden_behaviors=case.forbidden_behaviors,
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

    report = build_generation_safety_report(
        suite_name=suite_name,
        suite_version=suite_version,
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

    json_path = output_dir / "generation_safety_eval_v3_1.json"
    md_path = output_dir / "generation_safety_eval_v3_1.md"
    json_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(generation_safety_report_markdown(report), encoding="utf-8")

    summary = {
        "suite_name": report.suite_name,
        "query_count": report.query_count,
        "completed_count": report.completed_count,
        "error_count": report.error_count,
        "generation_model": report.generation_model,
        "judge_model": report.judge_model,
        "overall_pass_rate": report.overall_pass_rate,
        "policy_citation_pass_rate": report.policy_citation_pass_rate,
        "answerable_answer_accuracy": report.answerable_answer_accuracy,
        "answerable_false_refusal_rate": report.answerable_false_refusal_rate,
        "unanswerable_abstention_accuracy": report.unanswerable_abstention_accuracy,
        "unanswerable_false_answer_rate": report.unanswerable_false_answer_rate,
        "ambiguous_handling_rate": report.ambiguous_handling_rate,
        "apparent_conflict_resolution_rate": report.apparent_conflict_resolution_rate,
        "patient_specific_safety_rate": report.patient_specific_safety_rate,
        "unsafe_advice_rate": report.unsafe_advice_rate,
        "category_pass_rates": report.category_pass_rates,
        "mean_faithfulness_score": report.mean_faithfulness_score,
        "mean_expected_fact_coverage": report.mean_expected_fact_coverage,
        "total_generation_tokens": report.total_generation_tokens,
        "total_judge_tokens": report.total_judge_tokens,
        "total_tokens": report.total_tokens,
    }
    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print("- generation_safety_checkpoint_v3_1.json")
    print("- generation_safety_eval_v3_1.json")
    print("- generation_safety_eval_v3_1.md")


if __name__ == "__main__":
    main()
