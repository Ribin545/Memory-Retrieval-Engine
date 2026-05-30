"""Collection naming policy for benchmark Chroma 0.6.3 stores."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_CHROMA_COLLECTION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]$")


@dataclass(frozen=True)
class CollectionNamePolicy:
    """Generate and validate Chroma collection names."""

    max_length: int = 63
    min_length: int = 3
    mode_aliases: dict[str, str] = field(
        default_factory=lambda: {
            "clean_hybrid_temporal_multihop_v2": "ch_temporal_mh_v2",
        }
    )

    def alias_for_mode(self, mode: str) -> str:
        return self.mode_aliases.get(mode, mode)

    def stable_name(self, benchmark_name: str, schema: str, turns_mode: str, mode: str) -> str:
        collection_name = (
            f"{benchmark_name}_{schema}_{turns_mode}_{self.alias_for_mode(mode)}_stable_v1"
        )
        self.validate(collection_name)
        return collection_name

    def validate(self, collection_name: str) -> None:
        if not self.min_length <= len(collection_name) <= self.max_length:
            raise ValueError(
                "Chroma 0.6.3 collection names must be "
                f"{self.min_length}-{self.max_length} characters: {collection_name}"
            )
        if ".." in collection_name:
            raise ValueError(f"Chroma collection name cannot contain '..': {collection_name}")
        if not _CHROMA_COLLECTION_PATTERN.match(collection_name):
            raise ValueError(
                "Chroma collection names must start/end with alphanumeric "
                "characters and contain only alphanumeric, dot, underscore, or hyphen: "
                f"{collection_name}"
            )
