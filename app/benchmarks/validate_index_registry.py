#!/usr/bin/env python3
"""Validate benchmark index registry artifacts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.retrieval_domain.infrastructure import path_config
from app.retrieval_domain.indexing import CollectionNamePolicy, MetadataContract, load_registry
from app.retrieval_domain.indexing.registry_io import REGISTRY_DIR


CANONICAL_CHROMA_VERSION = "0.6.3"


def _failures_for_registry(path: Path) -> list[str]:
    failures: list[str] = []
    data = load_registry(path)
    entries = data.get("entries") or []
    if not entries:
        return [f"{path}: registry has no entries"]

    indexes_dir = (ROOT / "data" / "external" / "indexes").resolve()
    production_dir = Path(path_config.PROTECTED_LEGACY_CHROMA_DIR).resolve()
    metadata_contract = MetadataContract()
    collection_policy = CollectionNamePolicy()

    for idx, entry in enumerate(entries):
        prefix = f"{path}:entry[{idx}]"
        persist_path = (ROOT / entry.get("persist_path", "")).resolve()
        try:
            persist_path.relative_to(indexes_dir)
        except ValueError:
            failures.append(f"{prefix}: persist path is not benchmark-only: {persist_path}")
        if persist_path == production_dir:
            failures.append(f"{prefix}: production Chroma path referenced")

        collection_name = entry.get("collection_name", "")
        try:
            collection_policy.validate(collection_name)
        except ValueError as exc:
            failures.append(f"{prefix}: invalid collection name: {exc}")

        metadata_keys = tuple(entry.get("metadata_keys") or ())
        if metadata_keys != metadata_contract.allowed_keys:
            failures.append(
                f"{prefix}: metadata keys differ from contract: {metadata_keys}"
            )
        for key in metadata_keys:
            if key in metadata_contract.forbidden_keys:
                failures.append(f"{prefix}: forbidden metadata key present: {key}")

        if entry.get("indexed_document_count") != entry.get("expected_document_count"):
            failures.append(
                f"{prefix}: indexed_document_count != expected_document_count "
                f"({entry.get('indexed_document_count')} != {entry.get('expected_document_count')})"
            )
        if entry.get("chromadb_version") != CANONICAL_CHROMA_VERSION:
            failures.append(
                f"{prefix}: chromadb_version is {entry.get('chromadb_version')}, "
                f"expected {CANONICAL_CHROMA_VERSION}"
            )

        for cache in entry.get("feature_caches") or []:
            cache_path = cache.get("path")
            if cache_path and not (ROOT / cache_path).exists():
                failures.append(f"{prefix}: cache path does not exist: {cache_path}")

        pointer_manifest = entry.get("pointer_manifest_path")
        if pointer_manifest and not (ROOT / pointer_manifest).exists():
            failures.append(f"{prefix}: pointer manifest path does not exist: {pointer_manifest}")

        for artifact_path in entry.get("run_artifact_paths") or []:
            if artifact_path and not (ROOT / artifact_path).exists():
                failures.append(f"{prefix}: run artifact path does not exist: {artifact_path}")

        if entry.get("compaction_error"):
            failures.append(f"{prefix}: compaction_error is true")
        for error_key in ("write_error", "count_error", "query_error"):
            if entry.get(error_key):
                failures.append(f"{prefix}: {error_key} recorded: {entry.get(error_key)}")

    return failures


def main() -> int:
    registry_paths = sorted(
        path for path in REGISTRY_DIR.glob("*_registry.json")
        if path.name != "feature_cache_registry.json"
    )
    if not registry_paths:
        print(f"FAIL: no registry JSON files found in {REGISTRY_DIR}", file=sys.stderr)
        return 1

    print("Index registry validation")
    print(f"- Registry directory: {REGISTRY_DIR}")
    print(f"- Files: {len(registry_paths)}")

    failures: list[str] = []
    for path in registry_paths:
        failures.extend(_failures_for_registry(path))

    if failures:
        print("\nFAIL: registry validation errors:\n")
        for failure in failures:
            print(f"- {failure}")
        return 1

    for path in registry_paths:
        print(f"PASS: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
