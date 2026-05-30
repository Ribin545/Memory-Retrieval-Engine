"""Raw JSON dataset loading for Dataset Context."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class JsonDatasetRepository:
    """Load raw dataset JSON files without retrieval/storage dependencies."""

    def load_first_json(self, data_path: str) -> tuple[list[dict[str, Any]], Path]:
        dataset_dir = Path(data_path)
        if not dataset_dir.is_dir():
            raise FileNotFoundError(
                f"Expected dataset directory at {data_path}; no JSON was loaded."
            )

        json_files = sorted(path for path in dataset_dir.iterdir() if path.suffix == ".json")
        if not json_files:
            raise FileNotFoundError(f"No JSON files found in {data_path}.")

        file_to_load = json_files[0]
        with file_to_load.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            raise ValueError(f"Expected top-level list in {file_to_load}.")
        return data, file_to_load

    def sha256(self, path: str | Path) -> str:
        file_path = Path(path)
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
