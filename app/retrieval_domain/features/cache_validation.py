"""Preflight validation for feature cache compatibility."""

from __future__ import annotations

from pathlib import Path

from app.retrieval_domain.features.cache_registry import build_feature_cache_manifest
from app.retrieval_domain.features.cache_registry_io import write_feature_cache_registry
from app.retrieval_domain.infrastructure import path_config
from app.retrieval_domain.indexing.metadata_contracts import MetadataContract


def run_feature_cache_preflight(
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
    persist_path: str,
) -> tuple[Path, list[str]]:
    indexes_dir = Path(path_config.DATA_DIR) / "external" / "indexes"
    resolved_persist = Path(persist_path).resolve()
    try:
        resolved_persist.relative_to(indexes_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Benchmark persist path is not isolated: {resolved_persist}") from exc
    if resolved_persist == Path(path_config.PROTECTED_LEGACY_CHROMA_DIR).resolve():
        raise RuntimeError("Benchmark preflight refused production Chroma path")

    MetadataContract().validate({key: "" for key in MetadataContract().allowed_keys})
    manifest = build_feature_cache_manifest(
        benchmark_name=benchmark_name,
        dataset_path=dataset_path,
        schema=schema,
        turns_mode=turns_mode,
        retrieval_mode=retrieval_mode,
        grammar_cache_path=grammar_cache_path,
        temporal_cache_path=temporal_cache_path,
        temporal_graph_cache_path=temporal_graph_cache_path,
        pointer_manifest_path=pointer_manifest_path,
        memory_unit_count=memory_unit_count,
    )
    registry_path = write_feature_cache_registry(manifest)
    if not manifest.compatibility.compatible:
        raise RuntimeError(
            "Feature cache compatibility preflight failed: "
            + "; ".join(manifest.compatibility.errors)
        )
    return registry_path, list(manifest.compatibility.warnings)
