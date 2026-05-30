"""Indexing/storage-context value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_CHROMA_COLLECTION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]$")


@dataclass(frozen=True)
class CollectionName:
    """Validated Chroma collection name."""

    value: str

    def __post_init__(self) -> None:
        if not 3 <= len(self.value) <= 63:
            raise ValueError("Chroma collection names must be 3-63 characters")
        if ".." in self.value:
            raise ValueError("Chroma collection names cannot contain consecutive dots")
        if not _CHROMA_COLLECTION_PATTERN.match(self.value):
            raise ValueError(
                "Chroma collection names must start/end with alphanumeric "
                "characters and contain only alphanumeric, dot, underscore, or hyphen"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PersistPath:
    """Storage path value object for benchmark Chroma isolation."""

    path: Path

    @classmethod
    def from_string(cls, path: str) -> "PersistPath":
        return cls(Path(path))

    def normalized(self) -> Path:
        return self.path.expanduser()

    def is_under(self, root: str | Path) -> bool:
        normalized = self.normalized().resolve()
        root_path = Path(root).expanduser().resolve()
        try:
            normalized.relative_to(root_path)
            return True
        except ValueError:
            return False

    def reject_production_path(self, production_path: str | Path) -> None:
        if self.normalized().resolve() == Path(production_path).expanduser().resolve():
            raise ValueError("Benchmark storage must not use the production Chroma DB")

    def __str__(self) -> str:
        return str(self.path)
