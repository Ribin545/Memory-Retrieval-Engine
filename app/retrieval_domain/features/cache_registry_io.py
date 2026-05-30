"""Feature cache registry JSON IO."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cache_models import FeatureCacheManifest


FEATURE_REGISTRY_PATH = Path("outputs") / "benchmarks" / "registry" / "feature_cache_registry.json"


def write_feature_cache_registry(
    manifest: FeatureCacheManifest,
    output_path: str | Path | None = None,
) -> Path:
    path = Path(output_path) if output_path else FEATURE_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_feature_cache_registry(path: str | Path = FEATURE_REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
