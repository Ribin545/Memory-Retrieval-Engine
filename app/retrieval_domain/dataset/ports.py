"""Ports for Dataset Context components."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from app.benchmarks.external_benchmark_adapter import BenchmarkExample


class DatasetRepositoryPort(Protocol):
    """Loads raw dataset records without knowing retrieval or evaluation."""

    def load_first_json(self, data_path: str) -> tuple[list[dict[str, Any]], Path]:
        """Load the first JSON dataset file under a directory."""

    def sha256(self, path: str | Path) -> str:
        """Compute a stable hash for provenance."""


class DatasetAdapterPort(Protocol):
    """Maps raw dataset records into benchmark examples."""

    def examples_from_records(
        self,
        records: list[dict[str, Any]],
        *,
        limit: int | None = None,
        resolved_only: bool = False,
        turns_mode: str = "all_turns",
    ) -> list[BenchmarkExample]:
        """Return normalized benchmark examples."""
