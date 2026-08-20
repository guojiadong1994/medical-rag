from __future__ import annotations

import argparse
import json
from pathlib import Path

from medical_rag.evaluation.models import RetrievalEvalReport


def _load(path: Path) -> RetrievalEvalReport:
    return RetrievalEvalReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _first_relevant_hit(item):
    for hit in item.hits:
        if hit.relevant:
            return hit
    return None


def _case_diagnosis(item) -> dict[str, object]:
    top1 = item.hits[0] if item.hits else None
    relevant = _first_relevant_hit(item)
    if relevant is None:
        category = "MISS_TOP_K"
        explanation = "Top-K 内没有符合人工证据规则的 Chunk，属于召回失败。"
        score_gap = None
    elif relevant.rank == 1:
        category = "HIT_AT_1"
        explanation = "正确证据已经排在第一名。"
        score_gap = 0.0
    else:
        score_gap = round((top1.score - relevant.score) if top1 else 0.0, 6)
        if score_gap <= 0.03:
            category = "NEAR_TIE_RANKING"
            explanation = "正确证据已召回，但与 Top-1 分数非常接近，主要是排序问题。"
        else:
            category = "RANKING_GAP"
            explanation = "正确证据已召回，但被更高相似度的 Chunk 压在后面。"

        if top1 and relevant and top1.section != relevant.section:
            explanation += " Top-1 与正确证据来自不同章节，存在上下文/人群/章节竞争。"
        if top1 and relevant and top1.content_type != relevant.content_type:
            explanation += " 同时存在正文与表格之间的内容类型竞争。"

    return {
        "id": item.id,
        "query": item.query,
        "first_relevant_rank": item.first_relevant_rank,
        "category": category,
        "explanation": explanation,
        "score_gap_top1_to_relevant": score_gap,
        "top1": None if top1 is None else top1.model_dump(mode="json"),
        "first_relevant_hit": None if relevant is None else relevant.model_dump(mode="json"),
        "top5": [hit.model_dump(mode="json") for hit in item.hits[:5]],
    }


def _compare(current: RetrievalEvalReport, baseline: RetrievalEvalReport) -> dict[str, object]:
    base_by_id = {item.id: item for item in baseline.results}
    rows = []
    improved = regressed = unchanged = 0

    def rank_value(rank: int | None, top_k: int) -> int:
        return rank if rank is not None else top_k + 1

    for item in current.results:
        base = base_by_id.get(item.id)
        if base is None:
            continue
        before = rank_value(base.first_relevant_rank, baseline.top_k)
        after = rank_value(item.first_relevant_rank, current.top_k)
        if after < before:
            status = "improved"
            improved += 1
        elif after > before:
            status = "regressed"
            regressed += 1
        else:
            status = "unchanged"
            unchanged += 1
        rows.append({
            "id": item.id,
            "query": item.query,
            "baseline_rank": base.first_relevant_rank,
            "current_rank": item.first_relevant_rank,
            "status": status,
        })

    return {
        "metric_delta": {
            "recall_at_1": round(current.recall_at_1 - baseline.recall_at_1, 6),
            "recall_at_3": round(current.recall_at_3 - baseline.recall_at_3, 6),
            "recall_at_5": round(current.recall_at_5 - baseline.recall_at_5, 6),
            "mrr": round(current.mrr - baseline.mrr, 6),
            "no_relevant_in_top_k": current.no_relevant_in_top_k - baseline.no_relevant_in_top_k,
        },
        "improved_case_count": improved,
        "regressed_case_count": regressed,
        "unchanged_case_count": unchanged,
        "cases": rows,
    }


def _render_md(current: RetrievalEvalReport, diagnoses: list[dict], comparison: dict | None) -> str:
    lines = [
        "# Dense Retrieval Error Analysis",
        "",
        f"- suite: `{current.suite_name}`",
        f"- Recall@1: **{current.recall_at_1:.3f}**",
        f"- Recall@3: **{current.recall_at_3:.3f}**",
        f"- Recall@5: **{current.recall_at_5:.3f}**",
        f"- MRR: **{current.mrr:.3f}**",
        f"- Top-{current.top_k} misses: **{current.no_relevant_in_top_k}**",
        "",
    ]

    if comparison:
        delta = comparison["metric_delta"]
        lines.extend([
            "## Baseline comparison",
            "",
            f"- ΔRecall@1: **{delta['recall_at_1']:+.3f}**",
            f"- ΔRecall@3: **{delta['recall_at_3']:+.3f}**",
            f"- ΔRecall@5: **{delta['recall_at_5']:+.3f}**",
            f"- ΔMRR: **{delta['mrr']:+.3f}**",
            f"- improved / regressed / unchanged: **{comparison['improved_case_count']} / {comparison['regressed_case_count']} / {comparison['unchanged_case_count']}**",
            "",
            "| ID | Baseline rank | Current rank | Status |",
            "|---|---:|---:|---|",
        ])
        for row in comparison["cases"]:
            before = row["baseline_rank"] if row["baseline_rank"] is not None else "MISS"
            after = row["current_rank"] if row["current_rank"] is not None else "MISS"
            lines.append(f"| {row['id']} | {before} | {after} | {row['status']} |")
        lines.append("")

    weak = [d for d in diagnoses if d["category"] != "HIT_AT_1"]
    lines.extend(["## Weak / failed cases", ""])
    if not weak:
        lines.append("所有测试题的正确证据均排在 Top-1。")
        return "\n".join(lines)

    for item in weak:
        lines.extend([
            f"### {item['id']} · {item['query']}",
            "",
            f"- category: `{item['category']}`",
            f"- first relevant rank: `{item['first_relevant_rank'] if item['first_relevant_rank'] is not None else 'MISS'}`",
            f"- diagnosis: {item['explanation']}",
        ])
        if item["score_gap_top1_to_relevant"] is not None:
            lines.append(f"- score gap (Top1 - first relevant): `{item['score_gap_top1_to_relevant']:.6f}`")
        lines.append("")
        for hit in item["top5"]:
            flag = "✅" if hit["relevant"] else "·"
            section = hit.get("section") or "—"
            lines.append(
                f"- {flag} #{hit['rank']} score={hit['score']:.6f} page={hit['page_start']}-{hit['page_end']} "
                f"type={hit['content_type']} section={section}"
            )
            preview = (hit.get("text_preview") or "").strip()
            if preview:
                lines.append(f"  - {preview[:260]}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze dense-retrieval ranking failures")
    parser.add_argument("report_json", type=Path, help="Current dense retrieval evaluation report")
    parser.add_argument("--baseline", type=Path, default=None, help="Optional baseline report for rank-by-rank comparison")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--tag", default="current")
    args = parser.parse_args()

    current = _load(args.report_json)
    baseline = _load(args.baseline) if args.baseline else None
    diagnoses = [_case_diagnosis(item) for item in current.results]
    comparison = _compare(current, baseline) if baseline else None

    payload = {
        "suite_name": current.suite_name,
        "metrics": {
            "recall_at_1": current.recall_at_1,
            "recall_at_3": current.recall_at_3,
            "recall_at_5": current.recall_at_5,
            "mrr": current.mrr,
            "no_relevant_in_top_k": current.no_relevant_in_top_k,
        },
        "comparison": comparison,
        "cases": diagnoses,
    }

    output_dir = args.output_dir or args.report_json.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_tag = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in args.tag)
    json_path = output_dir / f"retrieval_error_analysis_{safe_tag}.json"
    md_path = output_dir / f"retrieval_error_analysis_{safe_tag}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_md(current, diagnoses, comparison), encoding="utf-8")

    category_counts: dict[str, int] = {}
    for item in diagnoses:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1
    print(json.dumps({
        "recall_at_1": current.recall_at_1,
        "recall_at_3": current.recall_at_3,
        "recall_at_5": current.recall_at_5,
        "mrr": current.mrr,
        "categories": category_counts,
        "comparison": comparison and {
            "metric_delta": comparison["metric_delta"],
            "improved": comparison["improved_case_count"],
            "regressed": comparison["regressed_case_count"],
            "unchanged": comparison["unchanged_case_count"],
        },
    }, ensure_ascii=False, indent=2))
    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print(f"- {json_path.name}")
    print(f"- {md_path.name}")


if __name__ == "__main__":
    main()
