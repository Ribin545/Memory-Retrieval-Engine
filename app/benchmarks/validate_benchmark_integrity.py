#!/usr/bin/env python3
"""
Validate that benchmark retrieval does not receive evaluation ground truth.

Dataset adapters may load ground truth, and evaluators may consume it after
retrieval returns candidates. Retrieval request construction, clean-hybrid
scoring, metadata scoring, and temporal reranking must not receive it.
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]

FILES_TO_CHECK = [
    ROOT / "app" / "benchmarks" / "run_external_benchmark.py",
    ROOT / "app" / "benchmarks" / "clean_hybrid_retriever.py",
    ROOT / "app" / "retrieval_domain" / "retrieval_models.py",
    ROOT / "app" / "retrieval_domain" / "applications" / "run_benchmark_suite.py",
    ROOT / "app" / "retrieval_domain" / "applications" / "build_benchmark_index.py",
    ROOT / "app" / "retrieval_domain" / "applications" / "evaluate_retrieval_run.py",
    ROOT / "app" / "retrieval_domain" / "applications" / "external_benchmark_runner.py",
    ROOT / "app" / "retrieval_domain" / "applications" / "generate_benchmark_report.py",
    ROOT / "app" / "retrieval_domain" / "applications" / "retrieval_dispatcher.py",
    ROOT / "app" / "retrieval_domain" / "retrieval" / "candidate_mapper.py",
    ROOT / "app" / "benchmarks" / "validate_candidate_schema.py",
    ROOT / "app" / "benchmarks" / "validate_index_registry.py",
    ROOT / "app" / "benchmarks" / "validate_feature_cache_registry.py",
    ROOT / "app" / "benchmarks" / "validate_adapter_evaluation_boundary.py",
]

FORBIDDEN_RETRIEVAL_NAMES = {
    "answer",
    "answer_text",
    "expected_session_ids",
    "answer_session_ids",
    "correct_session_id",
    "correct_session_ids",
    "expected_evidence",
    "expected_evidence_texts",
    "ground_truth",
    "query_session_id",
    "query_evidence_ids",
    "_query_evidence_ids",
}

FORBIDDEN_CALL_KEYWORDS = {
    "answer",
    "answer_text",
    "expected_session_ids",
    "answer_session_ids",
    "correct_session_id",
    "correct_session_ids",
    "expected_evidence",
    "expected_evidence_texts",
    "ground_truth",
    "query_session_id",
    "query_evidence_ids",
    "_query_evidence_ids",
}


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str

    def format(self) -> str:
        rel = self.path.relative_to(ROOT)
        return f"{rel}:{self.line}: {self.message}"


def _names_in(node: ast.AST) -> Iterable[tuple[str, int]]:
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            yield child.id, child.lineno
        elif isinstance(child, ast.Attribute):
            yield child.attr, child.lineno
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            yield child.value, child.lineno


def _function_args(function: ast.FunctionDef) -> set[str]:
    args = (
        list(function.args.posonlyargs)
        + list(function.args.args)
        + list(function.args.kwonlyargs)
    )
    return {arg.arg for arg in args}


def _called_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _class_field_names(class_def: ast.ClassDef) -> set[tuple[str, int]]:
    fields: set[tuple[str, int]] = set()
    for stmt in class_def.body:
        target: ast.expr | None = None
        if isinstance(stmt, ast.AnnAssign):
            target = stmt.target
        elif isinstance(stmt, ast.Assign) and stmt.targets:
            target = stmt.targets[0]
        if isinstance(target, ast.Name):
            fields.add((target.id, stmt.lineno))
    return fields


def check_file(path: Path) -> list[Violation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called_name(node) == "RetrievalRequest":
            for keyword in node.keywords:
                if keyword.arg in FORBIDDEN_CALL_KEYWORDS:
                    violations.append(
                        Violation(
                            path,
                            keyword.value.lineno,
                            "RetrievalRequest receives forbidden "
                            f"ground-truth keyword '{keyword.arg}'",
                        )
                    )

        if isinstance(node, ast.Call) and _called_name(node) == "clean_hybrid_retrieve":
            for keyword in node.keywords:
                if keyword.arg in FORBIDDEN_CALL_KEYWORDS:
                    violations.append(
                        Violation(
                            path,
                            keyword.value.lineno,
                            "clean_hybrid_retrieve receives forbidden "
                            f"ground-truth keyword '{keyword.arg}'",
                        )
                    )

        if isinstance(node, ast.ClassDef) and node.name == "RetrievalRequest":
            for field_name, line in sorted(_class_field_names(node)):
                if field_name in FORBIDDEN_RETRIEVAL_NAMES:
                    violations.append(
                        Violation(
                            path,
                            line,
                            "RetrievalRequest exposes forbidden "
                            f"ground-truth field '{field_name}'",
                        )
                    )

        if not isinstance(node, ast.FunctionDef):
            continue

        if node.name == "clean_hybrid_retrieve":
            for arg in sorted(_function_args(node) & FORBIDDEN_RETRIEVAL_NAMES):
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        f"clean_hybrid_retrieve exposes forbidden argument '{arg}'",
                    )
                )

        if node.name == "_compute_metadata_score":
            for arg in sorted(_function_args(node) & FORBIDDEN_RETRIEVAL_NAMES):
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        f"metadata scoring exposes forbidden argument '{arg}'",
                    )
                )
            for name, line in _names_in(node):
                if name in FORBIDDEN_RETRIEVAL_NAMES:
                    violations.append(
                        Violation(
                            path,
                            line,
                            "metadata scoring consumes forbidden "
                            f"ground-truth field '{name}'",
                        )
                    )

        if path.name in {"run_external_benchmark.py", "retrieval_dispatcher.py"} and node.name == "run_retrieval":
            if "example" in _function_args(node):
                violations.append(
                    Violation(
                        path,
                        node.lineno,
                        "run_retrieval accepts BenchmarkExample; retrieval "
                        "requests must not receive ground-truth containers",
                    )
                )
            for name, line in _names_in(node):
                if name in FORBIDDEN_RETRIEVAL_NAMES:
                    violations.append(
                        Violation(
                            path,
                            line,
                            "run_retrieval references forbidden "
                            f"ground-truth field '{name}'",
                        )
                    )

        if node.name in {"clean_hybrid_retrieve", "score_temporal_multihop"}:
            for name, line in _names_in(node):
                if name in FORBIDDEN_RETRIEVAL_NAMES:
                    violations.append(
                        Violation(
                            path,
                            line,
                            f"{node.name} references forbidden ground-truth "
                            f"field '{name}'",
                        )
                    )

    return violations


def main() -> int:
    missing = [path for path in FILES_TO_CHECK if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing file: {path}", file=sys.stderr)
        return 2

    print("Benchmark integrity validation")
    print("- Ground truth is allowed in Dataset and Evaluation contexts only.")
    print("- example_id filtering is allowed for benchmark haystack isolation, not ranking correctness.")

    violations: list[Violation] = []
    for path in FILES_TO_CHECK:
        violations.extend(check_file(path))

    if violations:
        print("\nFAIL: ground-truth leakage risk found:\n")
        for violation in violations:
            print(f"- {violation.format()}")
        return 1

    print("\nPASS: retrieval request construction and clean-hybrid scoring do not consume ground truth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
