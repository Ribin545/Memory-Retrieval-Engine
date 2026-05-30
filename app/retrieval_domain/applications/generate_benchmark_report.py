"""Application service for benchmark report generation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from .evaluate_retrieval_run import EvaluateRetrievalRun


@dataclass(frozen=True)
class BenchmarkReportContext:
    benchmark: str
    output_dir: str
    top_k: int
    mode_arg: str
    examples_tested: int
    unit_type: str | None = None
    resolved_only: bool | None = None
    grammar_cache_path: str | None = None
    temporal_cache_path: str | None = None
    temporal_graph_cache_path: str | None = None


class GenerateBenchmarkReport:
    """Write Markdown and JSON reports from completed results."""

    def __init__(self, evaluator: EvaluateRetrievalRun | None = None) -> None:
        self.evaluator = evaluator or EvaluateRetrievalRun()

    def write(
        self,
        context: BenchmarkReportContext,
        modes: list[str],
        all_results: dict[str, list[Any]],
    ) -> tuple[str, str]:
        md = f"# {context.benchmark.upper()} Retrieval Benchmark Report\n\n"
        md += f"**Examples Tested:** {context.examples_tested}\n"
        md += f"**Top-K Evaluation:** {context.top_k}\n\n"
        if context.benchmark == "locomo":
            md += f"**Unit Type:** {context.unit_type or 'turn'}\n\n"
        if context.benchmark == "longmemeval_s":
            md += f"**Resolved Only:** {'yes' if context.resolved_only else 'no'}\n\n"
        if context.grammar_cache_path:
            md += f"**Grammar Cache:** `{context.grammar_cache_path}`\n\n"
        if context.temporal_cache_path:
            md += f"**Temporal Cache:** `{context.temporal_cache_path}`\n\n"
        if context.temporal_graph_cache_path:
            md += f"**Temporal Event Graph Cache:** `{context.temporal_graph_cache_path}`\n\n"

        md += "| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Avg Latency (ms) |\n"
        md += "|------|----------|----------|-----------|-----|------------------|\n"

        json_report: dict[str, Any] = {
            "benchmark": context.benchmark,
            "examples_tested": context.examples_tested,
            "top_k": context.top_k,
            "unit_type": context.unit_type if context.benchmark == "locomo" else None,
            "resolved_only": (
                context.resolved_only if context.benchmark == "longmemeval_s" else None
            ),
            "grammar_cache_path": context.grammar_cache_path,
            "temporal_cache_path": context.temporal_cache_path,
            "temporal_graph_cache_path": context.temporal_graph_cache_path,
            "modes": {},
        }

        for mode in modes:
            results = all_results[mode]
            if not results:
                continue

            summary = self.evaluator.summarize_results(results)
            md += (
                f"| {mode} | {summary['recall_at_1']:.2%} | "
                f"{summary['recall_at_5']:.2%} | {summary['recall_at_10']:.2%} | "
                f"{summary['mrr']:.4f} | {summary['avg_latency_ms']:.1f} |\n"
            )

            resolved_results = [r for r in results if not r.error]
            unresolved_count = sum(1 for r in resolved_results if not r.hit_at_1)
            failures = [r for r in resolved_results if not r.hit_at_1]
            top_failures = []
            for result in failures[:5]:
                entry = {
                    "example_id": result.example_id,
                    "mrr": result.mrr,
                    "hit_at_1": result.hit_at_1,
                }
                if result.diagnostics:
                    entry["diagnostics"] = result.diagnostics
                top_failures.append(entry)

            sample_breakdowns = []
            for result in resolved_results:
                if result.diagnostics:
                    sample_breakdowns.append(
                        {
                            "example_id": result.example_id,
                            "hit_at_1": result.hit_at_1,
                            "scores": result.diagnostics.get("top_candidate_scores"),
                        }
                    )
                if len(sample_breakdowns) >= 6:
                    break

            json_report["modes"][mode] = {
                "recall_at_1": summary["recall_at_1"],
                "recall_at_5": summary["recall_at_5"],
                "recall_at_10": summary["recall_at_10"],
                "mrr": summary["mrr"],
                "avg_latency_ms": summary["avg_latency_ms"],
                "total_examples": summary["total_examples"],
                "unresolved_count": unresolved_count,
                "top_5_failures": top_failures,
                "sample_score_breakdowns": sample_breakdowns,
            }

        suffix = (
            f"_{context.unit_type}"
            if context.benchmark == "locomo" and context.unit_type
            else ""
        )
        mode_suffix = f"_{context.mode_arg}" if context.mode_arg != "all" else ""
        report_path = os.path.join(
            context.output_dir,
            f"{context.benchmark}{suffix}{mode_suffix}_retrieval_report.md",
        )
        json_report_path = os.path.join(
            context.output_dir,
            f"{context.benchmark}{suffix}{mode_suffix}_retrieval_report.json",
        )

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md)
        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(json_report, f, indent=2, ensure_ascii=False)

        print(f"\n[INFO] Benchmark complete. Report saved to {report_path}")
        print(f"[INFO] JSON report saved to {json_report_path}")
        return report_path, json_report_path
