"""
Pointer Manifest Validator for External Benchmarks

Validates that every pointer in the manifest resolves correctly:
  - source_hash matches resolved text
  - resolved text matches preview (prefix check)
  - JSON path navigation succeeds
  - No protected legacy DB is touched

Outputs:
  - Console: phase names, counts, tqdm progress bars
  - outputs/benchmarks/pointer_resolver_validation.json
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone
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
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PointerValidator:
    def __init__(self, manifest_path: str):
        self.manifest_path = manifest_path
        self.entries: Dict[str, Dict[str, Any]] = {}
        self.results: List[Dict[str, Any]] = []
        self.stats = {
            "total": 0,
            "resolved": 0,
            "hash_match": 0,
            "hash_mismatch": 0,
            "preview_match": 0,
            "preview_mismatch": 0,
            "json_path_failed": 0,
            "source_file_missing": 0,
            "errors": [],
        }

    def load_manifest(self) -> None:
        print(f"[PHASE] Loading manifest from {self.manifest_path}...")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.entries = manifest.get("entries", {})
        self.stats["total"] = len(self.entries)
        print(f"[INFO] Loaded {self.stats['total']:,} entries.")

    def _resolve_single(self, pointer_id: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve one pointer and return validation result dict."""
        result = {
            "pointer_id": pointer_id,
            "resolved": False,
            "hash_match": False,
            "preview_match": False,
            "error": None,
            "dataset": entry.get("dataset", ""),
            "source_file": entry.get("source_file", ""),
        }

        source_file = entry.get("source_file", "")
        json_path = entry.get("json_path", "")
        expected_hash = entry.get("source_hash", "").replace("sha256:", "")
        preview = entry.get("preview", "")

        if not source_file or not os.path.exists(source_file):
            result["error"] = f"Source file missing: {source_file}"
            self.stats["source_file_missing"] += 1
            return result

        try:
            with open(source_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            result["error"] = f"Failed to parse source JSON: {e}"
            self.stats["errors"].append(f"{pointer_id}: {e}")
            return result

        # Navigate JSON path
        parts = [p for p in json_path.split("/") if p]
        try:
            node = data
            for part in parts:
                if isinstance(node, list):
                    node = node[int(part)]
                elif isinstance(node, dict):
                    node = node[part]
                else:
                    raise ValueError(f"Cannot navigate into {type(node)}")
        except (IndexError, KeyError, ValueError) as e:
            result["error"] = f"JSON path failed at '{json_path}': {e}"
            self.stats["json_path_failed"] += 1
            return result

        source_text = node if isinstance(node, str) else json.dumps(node, ensure_ascii=False)
        result["resolved"] = True
        self.stats["resolved"] += 1

        # Hash check
        actual_hash = _sha256(source_text)
        if expected_hash and actual_hash == expected_hash:
            result["hash_match"] = True
            self.stats["hash_match"] += 1
        elif expected_hash:
            result["hash_match"] = False
            result["error"] = f"Hash mismatch: expected {expected_hash[:16]}... got {actual_hash[:16]}..."
            self.stats["hash_mismatch"] += 1
        else:
            result["hash_match"] = None  # No hash to check

        # Preview check (preview should be prefix of source_text)
        # Preview may end with "..." if truncated
        preview_clean = preview.rstrip(".")
        if preview_clean and source_text.startswith(preview_clean):
            result["preview_match"] = True
            self.stats["preview_match"] += 1
        elif preview_clean:
            result["preview_match"] = False
            result["error"] = result["error"] or "Preview mismatch"
            self.stats["preview_mismatch"] += 1
        else:
            result["preview_match"] = None

        return result

    def validate(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Run validation on all or a subset of manifest entries.

        Args:
            limit: If set, validate only the first N entries.

        Returns:
            Validation report dict.
        """
        self.load_manifest()

        items = list(self.entries.items())
        if limit:
            items = items[:limit]
            print(f"[PHASE] Validating first {limit} entries (limited mode)...")
        else:
            print(f"[PHASE] Validating all {len(items):,} entries...")

        self.results = []
        for pointer_id, entry in tqdm(items, desc="Validating pointers", total=len(items)):
            result = self._resolve_single(pointer_id, entry)
            self.results.append(result)

        # Compute summary
        self.stats["validated_count"] = len(self.results)
        self.stats["success_rate"] = round(self.stats["resolved"] / len(self.results), 4) if self.results else 0.0

        report = {
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "manifest_path": os.path.normpath(self.manifest_path),
            "entries_validated": len(self.results),
            "stats": self.stats,
            "sample_failures": [r for r in self.results if r.get("error")][:10],
            "sample_successes": [r for r in self.results if not r.get("error")][:5],
        }
        return report


def main():
    parser = argparse.ArgumentParser(description="Validate Pointer Manifest")
    parser.add_argument("--manifest-path", type=str, default="data/external/indexes/pointer_manifest.json")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of entries to validate")
    parser.add_argument("--output-path", type=str, default="outputs/benchmarks/pointer_resolver_validation.json")
    args = parser.parse_args()

    validator = PointerValidator(args.manifest_path)
    report = validator.validate(limit=args.limit)

    # Write JSON report
    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    tmp_path = args.output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, args.output_path)

    # Print summary
    print("\n" + "=" * 60)
    print("POINTER VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Entries validated: {report['entries_validated']:,}")
    print(f"Resolved:          {report['stats']['resolved']:,}")
    print(f"Hash matches:      {report['stats']['hash_match']:,}")
    print(f"Hash mismatches:   {report['stats']['hash_mismatch']:,}")
    print(f"Preview matches:   {report['stats']['preview_match']:,}")
    print(f"Preview mismatches:{report['stats']['preview_mismatch']:,}")
    print(f"JSON path failed:  {report['stats']['json_path_failed']:,}")
    print(f"Source missing:    {report['stats']['source_file_missing']:,}")
    print(f"Success rate:      {report['stats']['success_rate'] * 100:.2f}%")
    print("=" * 60)
    print(f"Detailed report:   {args.output_path}")

    # Write markdown report
    md_path = args.output_path.replace(".json", ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Pointer Resolver Validation Report\n\n")
        f.write(f"- **Manifest:** {report['manifest_path']}\n")
        f.write(f"- **Validated:** {report['entries_validated']:,} entries\n")
        f.write(f"- **Resolved:** {report['stats']['resolved']:,}\n")
        f.write(f"- **Hash matches:** {report['stats']['hash_match']:,}\n")
        f.write(f"- **Success rate:** {report['stats']['success_rate'] * 100:.2f}%\n\n")

        failures = report["sample_failures"]
        if failures:
            f.write("## Sample Failures\n\n")
            for r in failures:
                f.write(f"- `{r['pointer_id']}`: {r['error']}\n")
            f.write("\n")

        successes = report["sample_successes"]
        if successes:
            f.write("## Sample Successes\n\n")
            for r in successes[:3]:
                f.write(f"- `{r['pointer_id']}`: OK (dataset={r['dataset']})\n")

    print(f"Markdown report:   {md_path}")

    # Exit non-zero if any hash mismatches or unresolved entries
    if report["stats"]["hash_mismatch"] > 0 or report["stats"]["resolved"] < report["entries_validated"]:
        print("\n[FAIL] Validation found errors.")
        sys.exit(1)
    else:
        print("\n[PASS] All validated pointers resolved and hashes matched.")
        sys.exit(0)


if __name__ == "__main__":
    main()
