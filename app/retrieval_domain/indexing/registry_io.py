"""Read/write benchmark index registry JSON artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .registry_models import BenchmarkIndexRegistryEntry, BenchmarkRunRegistry


REGISTRY_DIR = Path("outputs") / "benchmarks" / "registry"


def sha256_path(path: str | Path | None) -> str | None:
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    digest = hashlib.sha256()
    files = [target] if target.is_file() else sorted(p for p in target.rglob("*") if p.is_file())
    for file_path in files:
        digest.update(str(file_path.relative_to(target) if target.is_dir() else file_path.name).encode("utf-8"))
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def registry_path_for(benchmark_name: str, schema: str, turns_mode: str) -> Path:
    return REGISTRY_DIR / f"{benchmark_name}_{schema}_{turns_mode}_registry.json"


def write_registry(
    benchmark_name: str,
    schema: str,
    turns_mode: str,
    entries: list[BenchmarkIndexRegistryEntry],
    output_path: str | Path | None = None,
) -> Path:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    path = Path(output_path) if output_path else registry_path_for(benchmark_name, schema, turns_mode)
    registry = BenchmarkRunRegistry(
        registry_version="1",
        benchmark_name=benchmark_name,
        schema=schema,
        turns_mode=turns_mode,
        entries=tuple(entries),
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    path.write_text(json.dumps(registry.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_registry(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
