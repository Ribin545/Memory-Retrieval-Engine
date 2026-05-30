"""
Pointer Resolver for External Benchmarks

Resolves pointer_ids back to exact source_text from original dataset JSON files.
Provides both single-pointer and batch resolution with hash verification.

Usage:
    from app.benchmarks.pointer_resolver import PointerResolver, resolve_pointer

    resolver = PointerResolver("data/external/indexes/pointer_manifest.json")
    text = resolver.resolve("lme:q123:doc:0")
    texts = resolver.resolve_many(["lme:q123:doc:0", "lme:q123:doc:1"])
"""
import os
import sys
import json
import hashlib
from typing import Dict, Any, List, Optional

try:
    from tqdm import tqdm
except ImportError:
    class tqdm:
        def __init__(self, iterable=None, total=None, desc="", **kwargs):
            self.iterable = iterable
            self.total = total
            self.desc = desc
            self.n = 0
            if desc:
                print(f"[{desc}] Starting...")
        def __iter__(self):
            for item in self.iterable:
                yield item
                self.n += 1
        def update(self, n=1):
            self.n += n
        def close(self):
            if self.desc:
                print(f"[{self.desc}] Done.")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PointerResolver:
    """
    Resolves pointer IDs to source text using the pointer manifest.
    Caches loaded JSON source files to avoid repeated disk reads.
    """

    def __init__(self, manifest_path: str):
        self.manifest_path = manifest_path
        self.entries: Dict[str, Dict[str, Any]] = {}
        self._source_cache: Dict[str, Any] = {}  # path -> parsed JSON
        self._load_manifest()

    def _load_manifest(self) -> None:
        print(f"[INFO] Loading pointer manifest from {self.manifest_path}...")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.entries = manifest.get("entries", {})
        print(f"[INFO] Loaded {len(self.entries)} manifest entries.")

    def _get_source_data(self, source_file: str) -> Any:
        """Load and cache source JSON file."""
        norm_path = os.path.normpath(source_file)
        if norm_path not in self._source_cache:
            with open(norm_path, "r", encoding="utf-8") as f:
                self._source_cache[norm_path] = json.load(f)
        return self._source_cache[norm_path]

    def resolve(self, pointer_id: str, verify_hash: bool = True) -> Optional[str]:
        """
        Resolve a single pointer_id to its source_text.

        Args:
            pointer_id: The pointer ID (e.g., "lme:q123:doc:0")
            verify_hash: If True, verify SHA-256 hash matches manifest

        Returns:
            The source text string, or None if resolution fails.
        """
        entry = self.entries.get(pointer_id)
        if not entry:
            return None

        dataset = entry.get("dataset", "")
        source_file = entry.get("source_file", "")
        json_path = entry.get("json_path", "")
        expected_hash = entry.get("source_hash", "").replace("sha256:", "")

        if not source_file or not json_path:
            return None

        try:
            data = self._get_source_data(source_file)
        except Exception as e:
            print(f"[WARN] Failed to load source file {source_file}: {e}")
            return None

        # Navigate JSON path like "/0/documents/0" or "/2/conversation/session_1/5"
        parts = [p for p in json_path.split("/") if p]
        try:
            node = data
            for part in parts:
                if isinstance(node, list):
                    node = node[int(part)]
                elif isinstance(node, dict):
                    node = node[part]
                else:
                    return None
        except (IndexError, KeyError, ValueError) as e:
            print(f"[WARN] JSON path navigation failed for {pointer_id} at '{json_path}': {e}")
            return None

        source_text = node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)

        if verify_hash and expected_hash:
            actual_hash = _sha256(source_text)
            if actual_hash != expected_hash:
                print(
                    f"[WARN] Hash mismatch for {pointer_id}: expected {expected_hash[:16]}... "
                    f"got {actual_hash[:16]}..."
                )
                # Still return text; caller decides whether to trust it

        return source_text

    def resolve_many(
        self,
        pointer_ids: List[str],
        verify_hash: bool = True,
        show_progress: bool = True,
    ) -> List[Optional[str]]:
        """
        Resolve multiple pointers in batch.

        Args:
            pointer_ids: List of pointer IDs
            verify_hash: If True, verify SHA-256 hashes
            show_progress: If True, show tqdm progress bar

        Returns:
            List of source texts (None for failed resolutions)
        """
        iterable = tqdm(pointer_ids, desc="Resolving pointers", total=len(pointer_ids)) if show_progress else pointer_ids
        results = []
        for pid in iterable:
            results.append(self.resolve(pid, verify_hash=verify_hash))
        return results

    def get_entry(self, pointer_id: str) -> Optional[Dict[str, Any]]:
        """Return the manifest entry for a pointer_id without resolving text."""
        return self.entries.get(pointer_id)

    def resolve_composite(
        self,
        pointer_ids: List[str],
        format_template: str = "{text}",
        join_char: str = "\n",
        verify_hash: bool = True,
    ) -> Optional[str]:
        """
        Resolve multiple base pointers and join them into a composite text.
        Useful for LoCoMo session/window units built from multiple turns.

        Args:
            pointer_ids: Ordered list of base pointer IDs
            format_template: Template for each turn; default is plain text.
                             Use {text}, {speaker}, {dia_id}, {turn_index} placeholders.
            join_char: String to join formatted turns
            verify_hash: If True, verify hashes

        Returns:
            Composite text string, or None if any resolution fails.
        """
        parts = []
        for idx, pid in enumerate(pointer_ids):
            entry = self.get_entry(pid)
            text = self.resolve(pid, verify_hash=verify_hash)
            if text is None:
                return None
            # Extract metadata from entry for templating
            speaker = entry.get("speaker", "") if entry else ""
            dia_id = entry.get("turn_id", "") if entry else ""
            formatted = format_template.format(
                text=text,
                speaker=speaker,
                dia_id=dia_id,
                turn_index=idx,
            )
            parts.append(formatted)
        return join_char.join(parts)


def resolve_pointer(pointer_id: str, manifest_path: str = "data/external/indexes/pointer_manifest.json") -> Optional[str]:
    """Convenience function: resolve a single pointer with default manifest path."""
    resolver = PointerResolver(manifest_path)
    return resolver.resolve(pointer_id)


def resolve_many(
    pointer_ids: List[str],
    manifest_path: str = "data/external/indexes/pointer_manifest.json",
) -> List[Optional[str]]:
    """Convenience function: resolve multiple pointers with default manifest path."""
    resolver = PointerResolver(manifest_path)
    return resolver.resolve_many(pointer_ids)
