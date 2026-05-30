"""Metadata contract for benchmark Chroma records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.retrieval_domain.retrieval_models import FORBIDDEN_RETRIEVAL_HINT_KEYS


ALLOWED_BENCHMARK_METADATA_KEYS = (
    "example_id",
    "memory_id",
    "original_memory_id",
    "session_id",
    "source_session_id",
    "pointer_id",
    "timestamp",
    "memory_unit_type",
    "turns_mode",
)


@dataclass(frozen=True)
class MetadataContract:
    """Allowed primitive metadata keys for benchmark Chroma collections."""

    allowed_keys: tuple[str, ...] = ALLOWED_BENCHMARK_METADATA_KEYS
    forbidden_keys: frozenset[str] = field(
        default_factory=lambda: frozenset(FORBIDDEN_RETRIEVAL_HINT_KEYS)
    )

    def validate(self, metadata: Mapping[str, Any]) -> None:
        keys = set(metadata)
        forbidden = sorted(keys & self.forbidden_keys)
        if forbidden:
            raise ValueError(f"Forbidden ground-truth metadata fields: {forbidden}")

        unexpected = sorted(keys - set(self.allowed_keys))
        if unexpected:
            raise ValueError(f"Unexpected benchmark metadata fields: {unexpected}")

        non_primitive = {
            key: type(value).__name__
            for key, value in metadata.items()
            if value is not None and not isinstance(value, (str, int, float, bool))
        }
        if non_primitive:
            raise ValueError(f"Benchmark metadata values must be primitive: {non_primitive}")

    def project(self, metadata: Mapping[str, Any]) -> dict[str, Any]:
        projected = {key: metadata.get(key, "") for key in self.allowed_keys}
        self.validate(projected)
        return projected
