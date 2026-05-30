"""Build feature cache registry manifests for benchmark runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.retrieval_domain.features.cache_models import (
    CacheCompatibilityResult,
    FeatureCacheManifest,
    FeatureCacheRegistryEntry,
)
from app.retrieval_domain.features.temporal_versions import (
    GRAMMAR_CACHE_V1,
    PARSER_BY_MODE,
    POINTER_MANIFEST_V1_LEGACY,
    REQUIRED_CACHE_TYPES_BY_MODE,
    TEMPORAL_CACHE_V1,
    TEMPORAL_EVENT_GRAPH_V1,
    TEMPORAL_MULTIHOP_SCORER_V2,
)
from app.retrieval_domain.indexing.registry_io import sha256_path


COMPATIBLE_MODES = {
    "grammar": (
        "clean_hybrid",
        "clean_hybrid_grammar",
        "clean_hybrid_temporal",
        "clean_hybrid_temporal_multihop",
        "clean_hybrid_temporal_multihop_v2",
    ),
    "temporal": (
        "clean_hybrid_temporal",
        "clean_hybrid_temporal_multihop",
        "clean_hybrid_temporal_multihop_v2",
    ),
    "temporal_graph": (
        "clean_hybrid_temporal_multihop",
        "clean_hybrid_temporal_multihop_v2",
    ),
    "pointer_manifest": (
        "vector_only",
        "clean_hybrid",
        "clean_hybrid_temporal",
        "clean_hybrid_temporal_multihop_v2",
    ),
}


def _count_cache_items(path: str | None, cache_type: str) -> int | None:
    if not path or not Path(path).exists():
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict):
        if cache_type == "temporal_graph":
            return len(data.get("event_cards") or data.get("events") or data)
        return len(data)
    if isinstance(data, list):
        return len(data)
    return None


def _file_size(path: str | None) -> int | None:
    if not path or not Path(path).exists():
        return None
    return Path(path).stat().st_size


def _entry(
    *,
    cache_type: str,
    path: str | None,
    version: str,
    builder_script: str | None,
    builder_version: str | None,
    parser_name: str | None,
    parser_version: str | None,
    dataset_path: str,
    dataset_hash: str | None,
    benchmark_name: str,
    schema: str,
    turns_mode: str,
    memory_unit_count: int | None,
    source_artifacts: tuple[str, ...],
) -> FeatureCacheRegistryEntry:
    exists = bool(path and Path(path).exists())
    warnings: list[str] = []
    if not exists:
        warnings.append("cache file is missing")
    warnings.append("dataset/schema/turns provenance is inferred from current run")
    return FeatureCacheRegistryEntry(
        cache_type=cache_type,
        cache_path=path,
        cache_hash=sha256_path(path) if exists else None,
        cache_version=version,
        builder_script=builder_script,
        builder_version=builder_version,
        parser_name=parser_name,
        parser_version=parser_version,
        dataset_path=dataset_path,
        dataset_hash=dataset_hash,
        benchmark_name=benchmark_name,
        schema=schema,
        turns_mode=turns_mode,
        compatible_retrieval_modes=COMPATIBLE_MODES[cache_type],
        memory_unit_count=memory_unit_count,
        cache_item_count=_count_cache_items(path, cache_type),
        created_at=datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc).isoformat()
        if exists
        else None,
        source_artifacts=source_artifacts,
        validation_status="present" if exists else "missing_optional",
        exists=exists,
        file_size_bytes=_file_size(path),
        warnings=tuple(warnings),
    )


def build_feature_cache_manifest(
    *,
    benchmark_name: str,
    dataset_path: str,
    schema: str,
    turns_mode: str,
    retrieval_mode: str,
    grammar_cache_path: str | None,
    temporal_cache_path: str | None,
    temporal_graph_cache_path: str | None,
    pointer_manifest_path: str | None,
    memory_unit_count: int | None,
) -> FeatureCacheManifest:
    dataset_hash = sha256_path(dataset_path)
    parser_version = PARSER_BY_MODE.get(retrieval_mode)
    entries = (
        _entry(
            cache_type="grammar",
            path=grammar_cache_path,
            version=GRAMMAR_CACHE_V1,
            builder_script="app/benchmarks/build_grammar_cache.py",
            builder_version=GRAMMAR_CACHE_V1,
            parser_name=None,
            parser_version=None,
            dataset_path=dataset_path,
            dataset_hash=dataset_hash,
            benchmark_name=benchmark_name,
            schema=schema,
            turns_mode=turns_mode,
            memory_unit_count=memory_unit_count,
            source_artifacts=("app/benchmarks/build_grammar_cache.py",),
        ),
        _entry(
            cache_type="temporal",
            path=temporal_cache_path,
            version=TEMPORAL_CACHE_V1,
            builder_script="app/benchmarks/build_temporal_cache.py",
            builder_version=TEMPORAL_CACHE_V1,
            parser_name="temporal_query_parser.py",
            parser_version="temporal_parser_v1",
            dataset_path=dataset_path,
            dataset_hash=dataset_hash,
            benchmark_name=benchmark_name,
            schema=schema,
            turns_mode=turns_mode,
            memory_unit_count=memory_unit_count,
            source_artifacts=(
                "app/benchmarks/build_temporal_cache.py",
                "app/benchmarks/temporal_query_parser.py",
            ),
        ),
        _entry(
            cache_type="temporal_graph",
            path=temporal_graph_cache_path,
            version=TEMPORAL_EVENT_GRAPH_V1,
            builder_script="app/benchmarks/build_temporal_event_graph.py",
            builder_version=TEMPORAL_EVENT_GRAPH_V1,
            parser_name="temporal_query_parser_v2.py",
            parser_version=parser_version,
            dataset_path=dataset_path,
            dataset_hash=dataset_hash,
            benchmark_name=benchmark_name,
            schema=schema,
            turns_mode=turns_mode,
            memory_unit_count=memory_unit_count,
            source_artifacts=(
                "app/benchmarks/build_temporal_event_graph.py",
                "app/benchmarks/temporal_query_parser_v2.py",
                "app/benchmarks/temporal_multihop_scorer.py",
                TEMPORAL_MULTIHOP_SCORER_V2,
            ),
        ),
        _entry(
            cache_type="pointer_manifest",
            path=pointer_manifest_path,
            version=POINTER_MANIFEST_V1_LEGACY,
            builder_script="app/benchmarks/pointer_manifest.py",
            builder_version=POINTER_MANIFEST_V1_LEGACY,
            parser_name=None,
            parser_version=None,
            dataset_path=dataset_path,
            dataset_hash=dataset_hash,
            benchmark_name=benchmark_name,
            schema=schema,
            turns_mode=turns_mode,
            memory_unit_count=memory_unit_count,
            source_artifacts=("app/benchmarks/pointer_manifest.py",),
        ),
    )
    compatibility = validate_manifest_entries(entries, retrieval_mode, parser_version)
    return FeatureCacheManifest(
        registry_version="1",
        benchmark_name=benchmark_name,
        dataset_path=dataset_path,
        dataset_hash=dataset_hash,
        schema=schema,
        turns_mode=turns_mode,
        retrieval_mode=retrieval_mode,
        parser_version=parser_version,
        entries=entries,
        compatibility=compatibility,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )


def validate_manifest_entries(
    entries: tuple[FeatureCacheRegistryEntry, ...],
    retrieval_mode: str,
    parser_version: str | None,
) -> CacheCompatibilityResult:
    by_type = {entry.cache_type: entry for entry in entries}
    errors: list[str] = []
    warnings: list[str] = []
    required = REQUIRED_CACHE_TYPES_BY_MODE.get(retrieval_mode, ())
    for cache_type in required:
        entry = by_type.get(cache_type)
        if not entry or not entry.exists:
            errors.append(f"required cache missing for {retrieval_mode}: {cache_type}")
        elif retrieval_mode not in entry.compatible_retrieval_modes:
            errors.append(f"cache {cache_type} is not compatible with {retrieval_mode}")
    if retrieval_mode == "clean_hybrid_temporal_multihop_v2":
        temporal_graph = by_type.get("temporal_graph")
        if parser_version != "temporal_parser_v2_relcl_acl":
            errors.append("temporal_multihop_v2 requires temporal_parser_v2_relcl_acl")
        if not temporal_graph or not temporal_graph.exists:
            errors.append("temporal_multihop_v2 requires temporal event graph provenance")
    pointer = by_type.get("pointer_manifest")
    if pointer and not pointer.exists:
        warnings.append("pointer manifest is optional and missing")
    for entry in entries:
        warnings.extend(entry.warnings)
    return CacheCompatibilityResult(
        compatible=not errors,
        errors=tuple(errors),
        warnings=tuple(sorted(set(warnings))),
    )
