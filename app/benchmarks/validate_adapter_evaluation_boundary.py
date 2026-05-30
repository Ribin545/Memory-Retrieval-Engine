#!/usr/bin/env python3
"""Validate Dataset/Evaluation boundary rules for benchmark adapters."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

ADAPTER_FILES = [
    ROOT / "app" / "benchmarks" / "longmemeval_s_adapter.py",
    ROOT / "app" / "benchmarks" / "external_benchmark_adapter.py",
]
DATASET_FILES = [
    ROOT / "app" / "retrieval_domain" / "dataset" / "__init__.py",
    ROOT / "app" / "retrieval_domain" / "dataset" / "ports.py",
    ROOT / "app" / "retrieval_domain" / "dataset" / "json_dataset_repository.py",
    ROOT / "app" / "retrieval_domain" / "dataset" / "longmemeval_cleaned_adapter.py",
    ROOT / "app" / "retrieval_domain" / "dataset" / "longmemeval_legacy_adapter.py",
    ROOT / "app" / "retrieval_domain" / "dataset" / "longmemeval_adapter_facade.py",
]
EVALUATION_FILES = [
    ROOT / "app" / "retrieval_domain" / "evaluation" / "__init__.py",
    ROOT / "app" / "retrieval_domain" / "evaluation" / "hit_policies.py",
    ROOT / "app" / "retrieval_domain" / "evaluation" / "metric_aggregation.py",
    ROOT / "app" / "retrieval_domain" / "evaluation" / "evaluation_service.py",
]
RETRIEVAL_FILES = [
    ROOT / "app" / "benchmarks" / "clean_hybrid_retriever.py",
    ROOT / "app" / "retrieval_domain" / "applications" / "retrieval_dispatcher.py",
    ROOT / "app" / "retrieval_domain" / "retrieval_models.py",
    ROOT / "app" / "retrieval_domain" / "retrieval" / "candidate_mapper.py",
]

FORBIDDEN_ADAPTER_IMPORTS = {
    "app.benchmarks.clean_hybrid_retriever",
    "app.retrieval_domain.infrastructure",
    "app.retrieval_domain.infrastructure.chroma_index_repository",
    "chromadb",
}
FORBIDDEN_DATASET_IMPORT_FRAGMENTS = {
    "clean_hybrid_retriever",
    "retrieval_dispatcher",
    "chroma",
    "infrastructure",
    "generate_benchmark_report",
}
FORBIDDEN_EVALUATION_IMPORT_FRAGMENTS = {
    "chroma",
    "clean_hybrid_retriever",
    "retriever",
    "infrastructure",
}
FORBIDDEN_RETRIEVAL_IMPORTS = {
    "app.retrieval_domain.evaluation",
    "app.retrieval_domain.evaluation.hit_policies",
    "app.retrieval_domain.evaluation.evaluation_service",
}
FORBIDDEN_RETRIEVAL_NAMES = {"GroundTruth", "HitPolicy", "StrictSessionIdHitPolicy"}


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path.relative_to(ROOT)}:{self.line}: {self.message}"


def _imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    modules: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            modules.append((module, node.lineno))
            for alias in node.names:
                modules.append((f"{module}.{alias.name}", node.lineno))
    return modules


def _is_schema_cleaned_test(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Constant) and child.value == "cleaned"
        for child in ast.walk(node)
    )


def _calls_function(node: ast.AST, function_name: str) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name) and func.id == function_name:
            return True
        if isinstance(func, ast.Attribute) and func.attr == function_name:
            return True
    return False


def _assigns_candidate_score(node: ast.AST) -> list[int]:
    lines: list[int] = []
    score_fields = {"score", "final_score"}
    for child in ast.walk(node):
        if not isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = []
        if isinstance(child, ast.Assign):
            targets.extend(child.targets)
        else:
            targets.append(child.target)
        for target in targets:
            for nested in ast.walk(target):
                if isinstance(nested, ast.Attribute) and nested.attr in score_fields:
                    lines.append(nested.lineno)
                elif isinstance(nested, ast.Subscript):
                    key = nested.slice
                    if isinstance(key, ast.Constant) and key.value in score_fields:
                        lines.append(nested.lineno)
    return lines


def _check_adapter(path: Path, tree: ast.AST) -> list[Violation]:
    violations: list[Violation] = []
    for module_name, line in _imported_modules(tree):
        if module_name in FORBIDDEN_ADAPTER_IMPORTS:
            violations.append(
                Violation(path, line, f"dataset adapter imports forbidden module {module_name}")
            )

    if path.name == "longmemeval_s_adapter.py":
        source = path.read_text(encoding="utf-8")
        if "Legacy fuzzy evidence setup" not in source:
            violations.append(
                Violation(path, 1, "legacy fuzzy evidence setup is not clearly labeled")
            )
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and _is_schema_cleaned_test(node.test):
                for stmt in node.body:
                    if _calls_function(stmt, "fuzzy_match_evidence"):
                        violations.append(
                            Violation(
                                path,
                                stmt.lineno,
                                "cleaned LongMemEval-S path calls legacy fuzzy evidence matching",
                            )
                        )
    return violations


def _check_dataset_module(path: Path, tree: ast.AST) -> list[Violation]:
    violations: list[Violation] = []
    for module_name, line in _imported_modules(tree):
        lowered = module_name.lower()
        for fragment in FORBIDDEN_DATASET_IMPORT_FRAGMENTS:
            if fragment in lowered:
                violations.append(
                    Violation(
                        path,
                        line,
                        f"dataset module imports forbidden dependency {module_name}",
                    )
                )

    if path.name == "longmemeval_cleaned_adapter.py":
        for node in ast.walk(tree):
            if _calls_function(node, "fuzzy_match_evidence"):
                violations.append(
                    Violation(
                        path,
                        getattr(node, "lineno", 1),
                        "cleaned adapter references legacy fuzzy evidence setup",
                    )
                )
        for module_name, line in _imported_modules(tree):
            if "LegacyFuzzyEvidenceSetupPolicy" in module_name:
                violations.append(
                    Violation(
                        path,
                        line,
                        "cleaned adapter imports legacy fuzzy evidence setup",
                    )
                )

    if path.name != "longmemeval_legacy_adapter.py":
        source = path.read_text(encoding="utf-8")
        if "LegacyFuzzyEvidenceSetupPolicy" in source or "fuzzy_match_evidence(" in source:
            if path.name not in {"__init__.py"}:
                violations.append(
                    Violation(
                        path,
                        1,
                        "legacy fuzzy evidence setup is only allowed in longmemeval_legacy_adapter.py",
                    )
                )

    if path.name == "longmemeval_legacy_adapter.py":
        source = path.read_text(encoding="utf-8")
        if "legacy and non-canonical" not in source.lower():
            violations.append(
                Violation(path, 1, "legacy adapter must label fuzzy setup as non-canonical")
            )

    if path.name == "json_dataset_repository.py":
        for module_name, line in _imported_modules(tree):
            if module_name.startswith("app."):
                violations.append(
                    Violation(
                        path,
                        line,
                        f"dataset repository imports application module {module_name}",
                    )
                )
    return violations


def _check_evaluation(path: Path, tree: ast.AST) -> list[Violation]:
    violations: list[Violation] = []
    for module_name, line in _imported_modules(tree):
        lowered = module_name.lower()
        for fragment in FORBIDDEN_EVALUATION_IMPORT_FRAGMENTS:
            if fragment in lowered:
                violations.append(
                    Violation(
                        path,
                        line,
                        f"evaluation module imports retrieval/storage dependency {module_name}",
                    )
                )
    for line in _assigns_candidate_score(tree):
        violations.append(
            Violation(path, line, "evaluation module mutates candidate score/final_score")
        )
    return violations


def _check_retrieval(path: Path, tree: ast.AST) -> list[Violation]:
    violations: list[Violation] = []
    for module_name, line in _imported_modules(tree):
        if module_name in FORBIDDEN_RETRIEVAL_IMPORTS:
            violations.append(
                Violation(path, line, f"retrieval module imports evaluation context {module_name}")
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_RETRIEVAL_NAMES:
            violations.append(
                Violation(
                    path,
                    node.lineno,
                    f"retrieval module references evaluation-owned symbol {node.id}",
                )
            )
    return violations


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def main() -> int:
    print("Adapter/Evaluation boundary validation")
    print("- Dataset adapters map raw data only.")
    print("- Evaluation owns hit policies and ground-truth comparison.")

    paths = ADAPTER_FILES + DATASET_FILES + EVALUATION_FILES + RETRIEVAL_FILES
    missing = [path for path in paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing file: {path}", file=sys.stderr)
        return 2

    violations: list[Violation] = []
    for path in ADAPTER_FILES:
        violations.extend(_check_adapter(path, _parse(path)))
    for path in DATASET_FILES:
        violations.extend(_check_dataset_module(path, _parse(path)))
    for path in EVALUATION_FILES:
        violations.extend(_check_evaluation(path, _parse(path)))
    for path in RETRIEVAL_FILES:
        violations.extend(_check_retrieval(path, _parse(path)))

    if violations:
        print("\nFAIL: adapter/evaluation boundary violations found:\n")
        for violation in violations:
            print(f"- {violation.format()}")
        return 1

    print("\nPASS: adapter/evaluation boundary rules hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
