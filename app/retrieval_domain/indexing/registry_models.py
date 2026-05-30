"""Registry models for reproducible benchmark indexes and runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChromaEnvironment:
    python_version: str
    chromadb_version: str
    posthog_version: str | None = None
    posthog_constraint: str = "posthog<3"


@dataclass(frozen=True)
class FeatureCacheRegistryEntry:
    cache_type: str
    path: str | None
    version: str | None = None
    exists: bool = False
    sha256: str | None = None


@dataclass(frozen=True)
class IndexBuildConfig:
    benchmark_name: str
    dataset_path: str
    schema: str
    turns_mode: str
    retrieval_mode: str
    persist_path: str
    collection_name: str
    collection_alias: str
    batch_size: int
    metadata_keys: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkIndexRegistryEntry:
    benchmark_name: str
    dataset_path: str
    dataset_sha256: str | None
    schema: str
    turns_mode: str
    retrieval_mode: str
    persist_path: str
    collection_name: str
    collection_alias: str
    python_version: str
    chromadb_version: str
    posthog_version: str | None
    posthog_constraint: str
    batch_size: int
    indexed_document_count: int
    expected_document_count: int
    metadata_keys: tuple[str, ...]
    feature_caches: tuple[FeatureCacheRegistryEntry, ...] = ()
    feature_registry_path: str | None = None
    grammar_cache_identity: dict[str, Any] | None = None
    temporal_cache_identity: dict[str, Any] | None = None
    temporal_graph_identity: dict[str, Any] | None = None
    pointer_manifest_identity: dict[str, Any] | None = None
    parser_version: str | None = None
    cache_compatibility_status: str | None = None
    pointer_manifest_path: str | None = None
    pointer_manifest_exists: bool = False
    run_artifact_paths: tuple[str, ...] = ()
    validation_status: str = "unknown"
    smoke_test_status: str = "not_run"
    compaction_error: bool = False
    write_error: str | None = None
    count_error: str | None = None
    query_error: str | None = None
    reused_existing_collection: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BenchmarkRunRegistry:
    registry_version: str
    benchmark_name: str
    schema: str
    turns_mode: str
    entries: tuple[BenchmarkIndexRegistryEntry, ...]
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
