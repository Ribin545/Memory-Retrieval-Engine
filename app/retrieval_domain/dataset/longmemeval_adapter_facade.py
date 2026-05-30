"""Backward-compatible LongMemEval facade over Dataset Context adapters."""

from __future__ import annotations

import sys
from typing import Any

from app.benchmarks.external_benchmark_adapter import (
    BaseBenchmarkAdapter,
    BenchmarkExample,
    BenchmarkResult,
)
from app.retrieval_domain.evaluation import EvaluationService, StrictSessionIdHitPolicy

from .json_dataset_repository import JsonDatasetRepository
from .longmemeval_cleaned_adapter import LongMemEvalCleanedAdapter
from .longmemeval_legacy_adapter import LongMemEvalLegacyAdapter


class LongMemEvalAdapterFacade(BaseBenchmarkAdapter):
    """Compatibility facade preserving the historical LongMemEvalAdapter API."""

    def __init__(
        self,
        repository: JsonDatasetRepository | None = None,
        cleaned_adapter: LongMemEvalCleanedAdapter | None = None,
        legacy_adapter: LongMemEvalLegacyAdapter | None = None,
        evaluation_service: EvaluationService | None = None,
    ) -> None:
        self.repository = repository or JsonDatasetRepository()
        self.cleaned_adapter = cleaned_adapter or LongMemEvalCleanedAdapter()
        self.legacy_adapter = legacy_adapter or LongMemEvalLegacyAdapter()
        self.cleaned_evaluator = evaluation_service or EvaluationService(
            hit_policy=StrictSessionIdHitPolicy()
        )

    def load_dataset(
        self,
        data_path: str,
        limit: int | None = None,
        resolved_only: bool = False,
        schema: str = "default",
        turns_mode: str = "all_turns",
    ) -> list[BenchmarkExample]:
        try:
            records, file_to_load = self.repository.load_first_json(data_path)
        except Exception as exc:
            print(f"[ERROR] Failed to load LongMemEval dataset: {exc}")
            sys.exit(1)

        print(f"[INFO] Loading LongMemEval dataset from {file_to_load} (schema: {schema})")
        adapter = self.cleaned_adapter if schema == "cleaned" else self.legacy_adapter
        return adapter.examples_from_records(
            records,
            limit=limit,
            resolved_only=resolved_only,
            turns_mode=turns_mode,
        )

    def evaluate_retrieval(
        self,
        example: BenchmarkExample,
        retrieved_candidates: list[dict[str, Any]],
    ) -> BenchmarkResult:
        if example.metadata.get("schema") == "cleaned":
            return self.cleaned_evaluator.evaluate_to_result(
                example_id=example.example_id,
                candidates=retrieved_candidates,
                expected_session_ids=example.expected_session_ids,
                result_factory=BenchmarkResult,
                latency_ms=0.0,
            )
        return super().evaluate_retrieval(example, retrieved_candidates)
