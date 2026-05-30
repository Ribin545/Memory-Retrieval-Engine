"""Feature cache provenance contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ParserVersion:
    parser_name: str
    parser_version: str
    source_path: str
    source_hash: str | None = None


@dataclass(frozen=True)
class FeatureCacheIdentity:
    cache_type: str
    cache_path: str | None
    cache_hash: str | None
    cache_version: str


@dataclass(frozen=True)
class FeatureCacheRegistryEntry:
    cache_type: str
    cache_path: str | None
    cache_hash: str | None
    cache_version: str
    builder_script: str | None
    builder_version: str | None
    parser_name: str | None
    parser_version: str | None
    dataset_path: str
    dataset_hash: str | None
    benchmark_name: str
    schema: str
    turns_mode: str
    compatible_retrieval_modes: tuple[str, ...]
    memory_unit_count: int | None = None
    cache_item_count: int | None = None
    created_at: str | None = None
    source_artifacts: tuple[str, ...] = ()
    validation_status: str = "unknown"
    exists: bool = False
    file_size_bytes: int | None = None
    warnings: tuple[str, ...] = ()

    @property
    def identity(self) -> FeatureCacheIdentity:
        return FeatureCacheIdentity(
            cache_type=self.cache_type,
            cache_path=self.cache_path,
            cache_hash=self.cache_hash,
            cache_version=self.cache_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GrammarCacheProvenance(FeatureCacheRegistryEntry):
    pass


@dataclass(frozen=True)
class TemporalCacheProvenance(FeatureCacheRegistryEntry):
    pass


@dataclass(frozen=True)
class TemporalGraphProvenance(FeatureCacheRegistryEntry):
    pass


@dataclass(frozen=True)
class PointerManifestProvenance(FeatureCacheRegistryEntry):
    cleaned_pointer_compatible: bool = False


@dataclass(frozen=True)
class CacheCompatibilityResult:
    compatible: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeatureCacheManifest:
    registry_version: str
    benchmark_name: str
    dataset_path: str
    dataset_hash: str | None
    schema: str
    turns_mode: str
    retrieval_mode: str
    parser_version: str | None
    entries: tuple[FeatureCacheRegistryEntry, ...]
    compatibility: CacheCompatibilityResult
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
