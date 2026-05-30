"""Retrieval-context contracts and integrity checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from .dataset_models import MemoryUnit


RetrievalMode = Literal[
    "vector_only",
    "clean_hybrid",
    "clean_hybrid_temporal",
    "clean_hybrid_temporal_multihop_v2",
]


FORBIDDEN_RETRIEVAL_HINT_KEYS = frozenset(
    {
        "answer",
        "answer_text",
        "answer_session_ids",
        "correct_session_id",
        "correct_session_ids",
        "expected_evidence",
        "expected_evidence_texts",
        "expected_session_ids",
        "ground_truth",
        "query_evidence_ids",
        "_query_evidence_ids",
        "query_session_id",
    }
)


def _find_forbidden_keys(value: Any, path: str = "") -> list[str]:
    if not isinstance(value, Mapping):
        return []

    violations: list[str] = []
    for key, nested in value.items():
        key_text = str(key)
        current_path = f"{path}.{key_text}" if path else key_text
        if key_text in FORBIDDEN_RETRIEVAL_HINT_KEYS:
            violations.append(current_path)
        violations.extend(_find_forbidden_keys(nested, current_path))
    return violations


@dataclass(frozen=True)
class ScoreBreakdown:
    """Per-signal score components for a retrieved candidate."""

    dense: float | None = None
    sparse: float | None = None
    grammar: float | None = None
    emotion: float | None = None
    metadata: float | None = None
    temporal: float | None = None
    temporal_event: float | None = None
    temporal_pair: float | None = None
    final: float | None = None
    components: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        violations = _find_forbidden_keys(self.components, "score_breakdown.components")
        if violations:
            joined = ", ".join(sorted(violations))
            raise ValueError(f"ScoreBreakdown cannot carry ground-truth hints: {joined}")

    def to_dict(self) -> dict[str, Any]:
        data = {
            "dense": self.dense,
            "sparse": self.sparse,
            "grammar": self.grammar,
            "emotion": self.emotion,
            "metadata": self.metadata,
            "temporal": self.temporal,
            "temporal_event": self.temporal_event,
            "temporal_pair": self.temporal_pair,
            "final": self.final,
            "components": dict(self.components),
        }
        return data


@dataclass(frozen=True)
class RetrievalRequest:
    """Query and ranking configuration.

    This contract deliberately excludes ground truth fields. `example_id` is
    allowed only to isolate a benchmark haystack, not to rank correctness.
    """

    query: str
    mode: RetrievalMode
    top_k: int = 10
    memory_units: tuple[MemoryUnit, ...] = ()
    example_id: str | None = None
    query_timestamp: str | None = None
    feature_cache_keys: Mapping[str, Any] = field(default_factory=dict)
    retrieval_config: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        violations = _find_forbidden_keys(self.feature_cache_keys, "feature_cache_keys")
        violations.extend(_find_forbidden_keys(self.retrieval_config, "retrieval_config"))
        if violations:
            joined = ", ".join(sorted(violations))
            raise ValueError(
                "RetrievalRequest cannot carry evaluation ground-truth hints: "
                f"{joined}"
            )


@dataclass(frozen=True)
class RetrievalCandidate:
    """Ranked retrieval result returned before evaluation."""

    memory_id: str
    source_text: str
    original_memory_id: str | None = None
    session_id: str | None = None
    source_session_id: str | None = None
    pointer_id: str | None = None
    summary: str | None = None
    dia_ids: tuple[str, ...] = ()
    score: float | None = None
    final_score: float | None = None
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        violations = _find_forbidden_keys(self.metadata, "metadata")
        if violations:
            joined = ", ".join(sorted(violations))
            raise ValueError(f"RetrievalCandidate cannot carry ground-truth hints: {joined}")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "memory_id": self.memory_id,
            "original_memory_id": self.original_memory_id,
            "session_id": self.session_id,
            "source_session_id": self.source_session_id,
            "pointer_id": self.pointer_id,
            "source_text": self.source_text,
            "summary": self.summary if self.summary is not None else self.source_text,
            "dia_ids": list(self.dia_ids),
            "score": self.score,
            "final_score": self.final_score,
            "score_breakdown": self.score_breakdown.to_dict(),
            "metadata": dict(self.metadata),
        }
        for key, value in self.metadata.items():
            if key not in data and key not in FORBIDDEN_RETRIEVAL_HINT_KEYS:
                data[key] = value
        return data
