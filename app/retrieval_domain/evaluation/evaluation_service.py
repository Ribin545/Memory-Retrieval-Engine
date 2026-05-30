"""Evaluation application-facing service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .hit_policies import HitPolicy, StrictSessionIdHitPolicy
from .metric_aggregation import MetricAggregator, PerExampleMetrics


@dataclass
class EvaluationService:
    """Coordinates hit policy and metric aggregation after retrieval."""

    hit_policy: HitPolicy = field(default_factory=StrictSessionIdHitPolicy)
    metric_aggregator: MetricAggregator = field(default_factory=MetricAggregator)

    def evaluate(
        self,
        candidates: list[Any],
        expected_session_ids: Iterable[str],
    ) -> PerExampleMetrics:
        return self.metric_aggregator.evaluate_ranked_candidates(
            candidates=candidates,
            expected_session_ids=expected_session_ids,
            hit_policy=self.hit_policy,
        )

    def evaluate_to_result(
        self,
        *,
        example_id: str,
        candidates: list[Any],
        expected_session_ids: Iterable[str],
        result_factory: Callable[..., Any],
        latency_ms: float = 0.0,
    ) -> Any:
        metrics = self.evaluate(candidates, expected_session_ids)
        return result_factory(
            example_id=example_id,
            retrieved_top_k=candidates,
            hit_at_1=metrics.hit_at_1,
            hit_at_5=metrics.hit_at_5,
            hit_at_10=metrics.hit_at_10,
            mrr=metrics.mrr,
            latency_ms=latency_ms,
        )
