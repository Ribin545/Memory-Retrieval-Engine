"""Evaluation-context services and hit policies."""

from .evaluation_service import EvaluationService
from .hit_policies import HitPolicy, LegacyFuzzyEvidenceSetupPolicy, StrictSessionIdHitPolicy
from .metric_aggregation import MetricAggregator, PerExampleMetrics

__all__ = [
    "EvaluationService",
    "HitPolicy",
    "LegacyFuzzyEvidenceSetupPolicy",
    "MetricAggregator",
    "PerExampleMetrics",
    "StrictSessionIdHitPolicy",
]
