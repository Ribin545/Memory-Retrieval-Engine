#!/usr/bin/env python3
"""Validate feature cache registry compatibility before retrieval."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.retrieval_domain.infrastructure import path_config
from app.retrieval_domain.features import FEATURE_REGISTRY_PATH, load_feature_cache_registry
from app.retrieval_domain.features.cache_registry import validate_manifest_entries
from app.retrieval_domain.features.cache_models import FeatureCacheRegistryEntry


def _entry_from_dict(data: dict) -> FeatureCacheRegistryEntry:
    return FeatureCacheRegistryEntry(
        cache_type=data["cache_type"],
        cache_path=data.get("cache_path"),
        cache_hash=data.get("cache_hash"),
        cache_version=data.get("cache_version"),
        builder_script=data.get("builder_script"),
        builder_version=data.get("builder_version"),
        parser_name=data.get("parser_name"),
        parser_version=data.get("parser_version"),
        dataset_path=data.get("dataset_path", ""),
        dataset_hash=data.get("dataset_hash"),
        benchmark_name=data.get("benchmark_name", ""),
        schema=data.get("schema", ""),
        turns_mode=data.get("turns_mode", ""),
        compatible_retrieval_modes=tuple(data.get("compatible_retrieval_modes") or ()),
        memory_unit_count=data.get("memory_unit_count"),
        cache_item_count=data.get("cache_item_count"),
        created_at=data.get("created_at"),
        source_artifacts=tuple(data.get("source_artifacts") or ()),
        validation_status=data.get("validation_status", "unknown"),
        exists=bool(data.get("exists")),
        file_size_bytes=data.get("file_size_bytes"),
        warnings=tuple(data.get("warnings") or ()),
    )


def main() -> int:
    path = FEATURE_REGISTRY_PATH
    if not path.exists():
        print(f"FAIL: feature cache registry does not exist: {path}", file=sys.stderr)
        return 1
    data = load_feature_cache_registry(path)
    entries = tuple(_entry_from_dict(entry) for entry in data.get("entries", []))
    retrieval_mode = data.get("retrieval_mode", "")
    parser_version = data.get("parser_version")

    failures: list[str] = []
    warnings: list[str] = []
    indexes_dir = (Path(path_config.DATA_DIR) / "external" / "indexes").resolve()
    production_dir = Path(path_config.PROTECTED_LEGACY_CHROMA_DIR).resolve()

    for entry in entries:
        cache_path = entry.cache_path
        if cache_path:
            resolved = Path(cache_path).resolve()
            if resolved == production_dir:
                failures.append(f"cache points at production DB: {cache_path}")
            if "protected_legacy_chroma_db" in str(resolved):
                failures.append(f"cache path references production DB text: {cache_path}")
            if entry.cache_type in {"grammar", "temporal", "temporal_graph", "pointer_manifest"}:
                try:
                    resolved.relative_to(indexes_dir)
                except ValueError:
                    warnings.append(f"cache path is outside benchmark indexes: {cache_path}")
            if entry.exists and not resolved.exists():
                failures.append(f"cache marked exists but path missing: {cache_path}")
        warnings.extend(entry.warnings)

    compatibility = validate_manifest_entries(entries, retrieval_mode, parser_version)
    failures.extend(compatibility.errors)
    warnings.extend(compatibility.warnings)

    if retrieval_mode == "clean_hybrid_temporal_multihop_v2":
        if parser_version != "temporal_parser_v2_relcl_acl":
            failures.append("temporal_multihop_v2 must use temporal_parser_v2_relcl_acl")
        graph = next((entry for entry in entries if entry.cache_type == "temporal_graph"), None)
        if not graph or not graph.exists:
            failures.append("temporal_multihop_v2 requires temporal graph provenance")

    print("Feature cache registry validation")
    print(f"- Registry: {path}")
    print(f"- Retrieval mode: {retrieval_mode}")
    print(f"- Entries: {len(entries)}")
    for warning in sorted(set(warnings)):
        print(f"WARN: {warning}")

    if failures:
        print("\nFAIL: feature cache registry validation errors:\n")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: feature cache registry is compatible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
