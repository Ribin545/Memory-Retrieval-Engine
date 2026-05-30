"""Thin CLI wrapper for the external benchmark application service."""

from __future__ import annotations

import os
import sys
from typing import Any


os.environ["HF_HUB_OFFLINE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Preserve historical eager model loading behavior used by the benchmark path.
import app.memory_retriever  # noqa: F401

from app.retrieval_domain.applications.build_benchmark_index import (
    DEFAULT_BENCHMARK_CHROMA_DIR,
    BuildBenchmarkIndex,
)
from app.retrieval_domain.applications.external_benchmark_runner import main as _service_main
from app.retrieval_domain.applications.retrieval_dispatcher import (
    reconstruct_vector_candidates as _reconstruct_vector_candidates,
)
from app.retrieval_domain.applications.retrieval_dispatcher import run_retrieval


_INDEX_BUILDER = BuildBenchmarkIndex()
BENCHMARK_INDEXES_DIR = _INDEX_BUILDER.indexes_dir


def setup_isolated_env(benchmark_name: str, persist_dir: str):
    """Compatibility wrapper for benchmark-only Chroma setup."""

    return _INDEX_BUILDER.setup_isolated_env(benchmark_name, persist_dir)


def recreate_collection(client: Any, collection_name: str):
    """Compatibility wrapper for creating a fresh benchmark collection."""

    return _INDEX_BUILDER.recreate_collection(client, collection_name)


def _stable_collection_name(benchmark_name: str, schema: str, turns_mode: str, mode: str) -> str:
    return _INDEX_BUILDER.stable_collection_name(benchmark_name, schema, turns_mode, mode)


def ingest_full_dataset(
    collection: Any,
    temp_mem_path: str,
    examples: list[Any],
    mode: str,
    turns_mode: str,
    batch_size: int = 50,
    validate_batch_count: bool = True,
) -> int:
    """Compatibility wrapper for full benchmark collection ingestion."""

    return _INDEX_BUILDER.ingest_full_dataset(
        collection,
        temp_mem_path,
        examples,
        mode,
        turns_mode,
        batch_size=batch_size,
        validate_batch_count=validate_batch_count,
    )


def _validate_benchmark_persist_dir(benchmark_name: str, persist_dir: str) -> str:
    return _INDEX_BUILDER.validate_benchmark_persist_dir(benchmark_name, persist_dir)


def main() -> int:
    return _service_main()


if __name__ == "__main__":
    raise SystemExit(main())
