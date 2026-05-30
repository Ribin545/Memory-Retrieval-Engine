"""Application service for building isolated benchmark indexes."""

from __future__ import annotations

import json
import os
import platform
import sys
from importlib import metadata as importlib_metadata
from typing import Any, Iterable

import app.vector_store
from app.retrieval_domain.indexing import (
    BenchmarkIndexRegistryEntry,
    ChromaEnvironment,
    CollectionNamePolicy,
    FeatureCacheRegistryEntry,
    MetadataContract,
)
from app.retrieval_domain.indexing.registry_io import sha256_path
from app.retrieval_domain.infrastructure import ChromaAddDiagnostics, ChromaIndexRepository
from app.retrieval_domain.infrastructure import path_config


DEFAULT_BENCHMARK_CHROMA_DIR = os.path.join(
    path_config.DATA_DIR,
    "external",
    "indexes",
    "chroma_cleaned_500_py311_chroma063",
)
BENCHMARK_INDEXES_DIR = os.path.join(path_config.DATA_DIR, "external", "indexes")
COLLECTION_NAME_POLICY = CollectionNamePolicy()
METADATA_CONTRACT = MetadataContract()
PRIMITIVE_METADATA_FIELDS = METADATA_CONTRACT.allowed_keys


class BuildBenchmarkIndex:
    """Build benchmark-only Chroma collections without ranking decisions."""

    def __init__(self, indexes_dir: str = BENCHMARK_INDEXES_DIR) -> None:
        self.indexes_dir = os.path.abspath(indexes_dir)
        self.repository = ChromaIndexRepository(
            indexes_dir=self.indexes_dir,
            metadata_contract=METADATA_CONTRACT,
        )
        self.collection_name_policy = COLLECTION_NAME_POLICY
        self.last_index_entries: dict[str, dict[str, Any]] = {}

    def validate_benchmark_persist_dir(self, benchmark_name: str, persist_dir: str) -> str:
        return self.repository.validate_benchmark_persist_dir(benchmark_name, persist_dir)

    def setup_isolated_env(self, benchmark_name: str, persist_dir: str):
        """Set up the benchmark-only persistent Chroma instance."""

        os.makedirs(self.indexes_dir, exist_ok=True)
        isolated_db_path = self.validate_benchmark_persist_dir(benchmark_name, persist_dir)
        temp_mem_path = os.path.join(self.indexes_dir, f"{benchmark_name}_temp_memories.json")

        os.makedirs(isolated_db_path, exist_ok=True)
        app.vector_store.CHROMA_DIR = isolated_db_path
        path_config.LEGACY_MEMORIES_PATH = temp_mem_path

        client = self.repository.create_client(benchmark_name, isolated_db_path)
        return client, temp_mem_path

    @staticmethod
    def recreate_collection(client: Any, collection_name: str):
        """Create a fresh benchmark collection without suppressing Chroma failures."""

        repository = ChromaIndexRepository(
            indexes_dir=BENCHMARK_INDEXES_DIR,
            metadata_contract=METADATA_CONTRACT,
        )
        collection, _ = repository.get_or_recreate_collection(client, collection_name)
        return collection

    @staticmethod
    def stable_collection_name(benchmark_name: str, schema: str, turns_mode: str, mode: str) -> str:
        return COLLECTION_NAME_POLICY.stable_name(benchmark_name, schema, turns_mode, mode)

    @staticmethod
    def _processed_units(examples: Iterable[Any]) -> list[dict[str, Any]]:
        all_processed_units: list[dict[str, Any]] = []
        for ex in examples:
            for unit_idx, mu in enumerate(ex.memory_units):
                unit = dict(mu)
                original_mem_id = unit.get("original_memory_id") or unit.get("memory_id", "")
                mem_id = f"stable_{ex.example_id}_{unit_idx}_{original_mem_id}"
                unit["memory_id"] = mem_id
                unit["example_id"] = ex.example_id
                all_processed_units.append(unit)
        return all_processed_units

    @staticmethod
    def _metadata_for_unit(unit: dict[str, Any], turns_mode: str) -> dict[str, Any]:
        mem_id = unit["memory_id"]
        session_id = unit.get("session_id") or unit.get("source_session_id") or ""
        metadata = {
            "example_id": unit.get("example_id", ""),
            "memory_id": mem_id,
            "original_memory_id": unit.get("original_memory_id") or mem_id,
            "session_id": session_id,
            "source_session_id": session_id,
            "pointer_id": unit.get("pointer_id", ""),
            "timestamp": unit.get("timestamp", ""),
            "memory_unit_type": unit.get("memory_unit_type", "session"),
            "turns_mode": turns_mode,
        }
        return METADATA_CONTRACT.project(metadata)

    def ingest_full_dataset(
        self,
        collection: Any,
        temp_mem_path: str,
        examples: list[Any],
        mode: str,
        turns_mode: str,
        batch_size: int = 50,
        validate_batch_count: bool = True,
    ) -> int:
        """Ingest all memory units into a fresh benchmark collection."""

        from app.memory_retriever import embed_query

        if batch_size != 50:
            print(f"[WARN] Canonical benchmark batch size is 50; received {batch_size}.")

        all_processed_units = self._processed_units(examples)
        ids: list[str] = []
        embeddings: list[Any] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for unit in all_processed_units:
            text = unit.get("source_text", "")
            ids.append(unit["memory_id"])
            embeddings.append(embed_query(text))
            documents.append(text)
            metadatas.append(self._metadata_for_unit(unit, turns_mode))

        diagnostics = self.repository.add_documents(
            collection,
            ids,
            embeddings,
            documents,
            metadatas,
            batch_size=batch_size,
            validate_batch_count=validate_batch_count,
            desc=f"Chroma add ({mode})",
        )
        if diagnostics.write_error or diagnostics.count_error or diagnostics.query_error:
            raise RuntimeError(f"Chroma ingestion failed: {diagnostics}")

        with open(temp_mem_path, "w", encoding="utf-8") as f:
            json.dump(all_processed_units, f, indent=2)

        actual_count = diagnostics.indexed_document_count
        print(f"[INFO] Successfully indexed {actual_count} memory units into stable collection.")
        return actual_count

    def build_collections(
        self,
        client: Any,
        temp_mem_path: str,
        examples: list[Any],
        modes: list[str],
        benchmark_name: str,
        schema: str,
        turns_mode: str,
        batch_size: int = 50,
        validate_batch_count: bool = True,
        use_existing_index: bool = False,
    ) -> dict[str, Any]:
        """Create fresh collections and ingest the full benchmark dataset per mode."""

        mode_collections: dict[str, Any] = {}
        self.last_index_entries = {}
        for mode in modes:
            collection_name = self.stable_collection_name(benchmark_name, schema, turns_mode, mode)
            collection, reused = self.repository.get_or_recreate_collection(
                client,
                collection_name,
                use_existing_index=use_existing_index,
            )
            mode_collections[mode] = collection
            expected_document_count = len(self._processed_units(examples))

            if reused:
                indexed_document_count = collection.count()
                expected_for_registry = indexed_document_count
            else:
                print(
                    f"[INFO] Ingesting full dataset for mode '{mode}' "
                    f"into collection '{collection_name}'..."
                )
                indexed_document_count = self.ingest_full_dataset(
                    collection,
                    temp_mem_path,
                    examples,
                    mode,
                    turns_mode,
                    batch_size=batch_size,
                    validate_batch_count=validate_batch_count,
                )
                expected_for_registry = expected_document_count

            self.last_index_entries[mode] = {
                "benchmark_name": benchmark_name,
                "schema": schema,
                "turns_mode": turns_mode,
                "retrieval_mode": mode,
                "collection_name": collection_name,
                "collection_alias": self.collection_name_policy.alias_for_mode(mode),
                "batch_size": batch_size,
                "indexed_document_count": indexed_document_count,
                "expected_document_count": expected_for_registry,
                "run_expected_document_count": expected_document_count,
                "metadata_keys": tuple(PRIMITIVE_METADATA_FIELDS),
                "reused_existing_collection": reused,
            }

        return mode_collections

    @staticmethod
    def chroma_environment() -> ChromaEnvironment:
        try:
            chromadb_version = importlib_metadata.version("chromadb")
        except importlib_metadata.PackageNotFoundError:
            chromadb_version = "unknown"
        try:
            posthog_version = importlib_metadata.version("posthog")
        except importlib_metadata.PackageNotFoundError:
            posthog_version = None
        return ChromaEnvironment(
            python_version=platform.python_version() or sys.version.split()[0],
            chromadb_version=chromadb_version,
            posthog_version=posthog_version,
        )

    @staticmethod
    def _feature_cache_entry(cache_type: str, path: str | None, version: str | None = None) -> FeatureCacheRegistryEntry:
        exists = bool(path and os.path.exists(path))
        return FeatureCacheRegistryEntry(
            cache_type=cache_type,
            path=path,
            version=version,
            exists=exists,
            sha256=sha256_path(path) if exists else None,
        )

    def registry_entries(
        self,
        *,
        dataset_path: str,
        persist_path: str,
        grammar_cache_path: str | None,
        temporal_cache_path: str | None,
        temporal_graph_cache_path: str | None,
        pointer_manifest_path: str | None,
        run_artifact_paths: list[str],
        feature_registry_path: str | None = None,
        feature_cache_identities: dict[str, dict[str, Any]] | None = None,
        parser_version: str | None = None,
        cache_compatibility_status: str | None = None,
    ) -> list[BenchmarkIndexRegistryEntry]:
        env = self.chroma_environment()
        feature_cache_identities = feature_cache_identities or {}
        entries: list[BenchmarkIndexRegistryEntry] = []
        for mode, record in self.last_index_entries.items():
            feature_caches = (
                self._feature_cache_entry("grammar", grammar_cache_path, "v2"),
                self._feature_cache_entry("temporal", temporal_cache_path, "v1"),
                self._feature_cache_entry("temporal_event_graph", temporal_graph_cache_path, "v1"),
            )
            entries.append(
                BenchmarkIndexRegistryEntry(
                    benchmark_name=record["benchmark_name"],
                    dataset_path=dataset_path,
                    dataset_sha256=sha256_path(dataset_path),
                    schema=record["schema"],
                    turns_mode=record["turns_mode"],
                    retrieval_mode=mode,
                    persist_path=persist_path,
                    collection_name=record["collection_name"],
                    collection_alias=record["collection_alias"],
                    python_version=env.python_version,
                    chromadb_version=env.chromadb_version,
                    posthog_version=env.posthog_version,
                    posthog_constraint=env.posthog_constraint,
                    batch_size=record["batch_size"],
                    indexed_document_count=record["indexed_document_count"],
                    expected_document_count=record["expected_document_count"],
                    metadata_keys=record["metadata_keys"],
                    feature_caches=feature_caches,
                    feature_registry_path=feature_registry_path,
                    grammar_cache_identity=feature_cache_identities.get("grammar"),
                    temporal_cache_identity=feature_cache_identities.get("temporal"),
                    temporal_graph_identity=feature_cache_identities.get("temporal_graph"),
                    pointer_manifest_identity=feature_cache_identities.get("pointer_manifest"),
                    parser_version=parser_version,
                    cache_compatibility_status=cache_compatibility_status,
                    pointer_manifest_path=pointer_manifest_path,
                    pointer_manifest_exists=bool(pointer_manifest_path and os.path.exists(pointer_manifest_path)),
                    run_artifact_paths=tuple(run_artifact_paths),
                    validation_status="passed",
                    smoke_test_status="not_run",
                    reused_existing_collection=record["reused_existing_collection"],
                )
            )
        return entries
