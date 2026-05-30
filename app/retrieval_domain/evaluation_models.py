"""Evaluation-context contracts for benchmark results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .dataset_models import GroundTruth
from .retrieval_models import RetrievalCandidate, RetrievalMode


@dataclass(frozen=True)
class MetricSet:
    """Aggregated retrieval metrics owned by Evaluation."""

    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    avg_latency_ms: float | None = None
    indexed_document_count: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkRunConfig:
    """Stable application-level benchmark run configuration."""

    benchmark: str
    schema: str
    turns_mode: str
    modes: tuple[RetrievalMode, ...]
    limit: int | None = None
    top_k: int = 10
    batch_size: int = 50
    persist_path: str | None = None
    output_dir: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    """Per-example ranked candidates and evaluation-owned ground truth."""

    example_id: str
    candidates: tuple[RetrievalCandidate, ...]
    ground_truth: GroundTruth
    hit_rank: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
