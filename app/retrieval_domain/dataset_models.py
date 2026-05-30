"""Dataset-context contracts for retrieval benchmark refactors.

These models are intentionally lightweight. They define the target domain
language without forcing existing benchmark runners to migrate in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class MemoryUnit:
    """Normalized memory text plus stable source identity."""

    memory_id: str
    source_text: str
    session_id: str | None = None
    source_session_id: str | None = None
    original_memory_id: str | None = None
    timestamp: str | None = None
    memory_unit_type: str | None = None
    pointer_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GroundTruth:
    """Evaluation-owned answer evidence.

    Retrieval requests must not receive this object or its fields.
    """

    expected_session_ids: tuple[str, ...] = ()
    expected_memory_ids: tuple[str, ...] = ()
    expected_pointer_ids: tuple[str, ...] = ()
    answer: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkExample:
    """Normalized benchmark example produced by a dataset adapter."""

    example_id: str
    query: str
    memory_units: tuple[MemoryUnit, ...]
    ground_truth: GroundTruth
    query_timestamp: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
