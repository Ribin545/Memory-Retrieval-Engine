"""Metric aggregation for ranked retrieval candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .hit_policies import HitPolicy


@dataclass(frozen=True)
class PerExampleMetrics:
    """Per-example Recall@K/MRR results."""

    hit_at_1: bool
    hit_at_5: bool
    hit_at_10: bool
    mrr: float


class MetricAggregator:
    """Computes existing benchmark metrics without changing definitions."""

    def evaluate_ranked_candidates(
        self,
        candidates: list[Any],
        expected_session_ids: Iterable[str],
        hit_policy: HitPolicy,
    ) -> PerExampleMetrics:
        hit_at_1 = False
        hit_at_5 = False
        hit_at_10 = False
        mrr = 0.0

        for rank, candidate in enumerate(candidates):
            if hit_policy.is_hit(candidate, expected_session_ids):
                if mrr == 0.0:
                    mrr = 1.0 / (rank + 1)
                if rank == 0:
                    hit_at_1 = True
                if rank < 5:
                    hit_at_5 = True
                if rank < 10:
                    hit_at_10 = True

        return PerExampleMetrics(
            hit_at_1=hit_at_1,
            hit_at_5=hit_at_5,
            hit_at_10=hit_at_10,
            mrr=mrr,
        )
