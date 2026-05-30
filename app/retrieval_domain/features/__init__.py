"""Feature-cache provenance contracts and validation."""

from .cache_models import (
    CacheCompatibilityResult,
    FeatureCacheIdentity,
    FeatureCacheManifest,
    FeatureCacheRegistryEntry,
    GrammarCacheProvenance,
    ParserVersion,
    PointerManifestProvenance,
    TemporalCacheProvenance,
    TemporalGraphProvenance,
)
from .cache_registry import build_feature_cache_manifest
from .cache_registry_io import (
    FEATURE_REGISTRY_PATH,
    load_feature_cache_registry,
    write_feature_cache_registry,
)
from .cache_validation import run_feature_cache_preflight

__all__ = [
    "CacheCompatibilityResult",
    "FEATURE_REGISTRY_PATH",
    "FeatureCacheIdentity",
    "FeatureCacheManifest",
    "FeatureCacheRegistryEntry",
    "GrammarCacheProvenance",
    "ParserVersion",
    "PointerManifestProvenance",
    "TemporalCacheProvenance",
    "TemporalGraphProvenance",
    "build_feature_cache_manifest",
    "load_feature_cache_registry",
    "run_feature_cache_preflight",
    "write_feature_cache_registry",
]
