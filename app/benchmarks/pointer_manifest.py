"""
Pointer Manifest Builder for External Benchmarks

Builds a centralized manifest mapping pointer_id -> source location in original
dataset JSON files. Enables pointer-based retrieval: indexes and caches store
lightweight pointer_ids instead of duplicating full conversation text.

Pointer ID formats:
  - longmemeval_s:   lme:{question_id}:doc:{doc_idx}
  - locomo:          locomo:{sample_id}:session:{session_id}:turn:{turn_idx}

Manifest entry schema:
  {
    "dataset": "longmemeval_s",
    "source_file": "data/external/longmemeval/longmemeval_s.json",
    "example_id": "...",
    "doc_id": "doc_0",
    "session_id": "session_1",
    "turn_id": "D1:1",
    "turn_index": 0,
    "char_start": 12345,
    "char_end": 12456,
    "source_hash": "sha256:...",
    "preview": "First 200 chars...",
    "json_path": "/0/documents/0"
  }

Output: data/external/indexes/pointer_manifest.json
"""
import os
import sys
import json
import hashlib
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

try:
    from tqdm import tqdm
except ImportError:
    # Minimal fallback if tqdm is missing
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


def _compute_char_offsets(raw_text: str, target_text: str, start_hint: int = 0) -> Optional[tuple]:
    """
    Find the first occurrence of target_text in raw_text at or after start_hint.
    Returns (char_start, char_end) or None if not found.
    """
    # JSON-escaped versions may exist; try raw text first
    pos = raw_text.find(target_text, start_hint)
    if pos != -1:
        return (pos, pos + len(target_text))
    # Fallback: try with escaped newlines
    escaped = target_text.replace("\n", "\\n").replace("\r", "\\r")
    if escaped != target_text:
        pos = raw_text.find(escaped, start_hint)
        if pos != -1:
            return (pos, pos + len(escaped))
    return None


def _build_longmemeval_manifest(data_path: str, raw_text: str, data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build manifest entries for LongMemEval-S dataset."""
    entries: Dict[str, Dict[str, Any]] = {}
    print(f"[PHASE] Building LongMemEval-S manifest ({len(data)} examples)...")

    for ex_idx, item in enumerate(tqdm(data, desc="LongMemEval-S", total=len(data))):
        question_id = item.get("question_id") or item.get("id") or f"idx_{ex_idx}"
        documents = item.get("documents", [])

        for doc_idx, doc_text in enumerate(documents):
            pointer_id = f"lme:{question_id}:doc:{doc_idx}"
            preview = doc_text[:200] + "..." if len(doc_text) > 200 else doc_text
            source_hash = _sha256(doc_text)

            # Compute char offsets in the raw JSON file
            offsets = _compute_char_offsets(raw_text, doc_text)
            if offsets is None:
                # If exact text not found (possible escaping), record -1
                char_start, char_end = -1, -1
            else:
                char_start, char_end = offsets

            entries[pointer_id] = {
                "dataset": "longmemeval_s",
                "source_file": os.path.normpath(data_path),
                "example_id": str(question_id),
                "doc_id": f"doc_{doc_idx}",
                "session_id": "",
                "turn_id": "",
                "turn_index": -1,
                "char_start": char_start,
                "char_end": char_end,
                "source_hash": f"sha256:{source_hash}",
                "preview": preview,
                "json_path": f"/{ex_idx}/documents/{doc_idx}",
            }

    print(f"[DONE] Built {len(entries)} LongMemEval-S pointer entries.")
    return entries


def _build_locomo_manifest(data_path: str, raw_text: str, data: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Build manifest entries for LoCoMo dataset (per-turn granularity)."""
    entries: Dict[str, Dict[str, Any]] = {}
    total_turns = 0

    print(f"[PHASE] Building LoCoMo manifest ({len(data)} personas)...")

    for persona_idx, persona in enumerate(tqdm(data, desc="LoCoMo personas", total=len(data))):
        sample_id = persona.get("sample_id", f"persona_{persona_idx}")
        conversation = persona.get("conversation", {})

        session_keys = [k for k in conversation.keys() if k.startswith("session_") and not k.endswith("_date_time")]
        for session_key in session_keys:
            turns = conversation.get(session_key, [])
            if not isinstance(turns, list):
                continue
            for turn_idx, turn in enumerate(turns):
                turn_text = turn.get("text", "")
                dia_id = turn.get("dia_id", "")
                speaker = turn.get("speaker", "")

                if not turn_text:
                    continue

                pointer_id = f"locomo:{sample_id}:session:{session_key}:turn:{turn_idx}"
                preview = turn_text[:200] + "..." if len(turn_text) > 200 else turn_text
                source_hash = _sha256(turn_text)

                offsets = _compute_char_offsets(raw_text, turn_text)
                if offsets is None:
                    char_start, char_end = -1, -1
                else:
                    char_start, char_end = offsets

                entries[pointer_id] = {
                    "dataset": "locomo",
                    "source_file": os.path.normpath(data_path),
                    "example_id": str(sample_id),
                    "doc_id": "",
                    "session_id": session_key,
                    "turn_id": str(dia_id),
                    "turn_index": turn_idx,
                    "char_start": char_start,
                    "char_end": char_end,
                    "source_hash": f"sha256:{source_hash}",
                    "preview": preview,
                    "json_path": f"/{persona_idx}/conversation/{session_key}/{turn_idx}",
                }
                total_turns += 1

    print(f"[DONE] Built {len(entries)} LoCoMo pointer entries ({total_turns} total turns).")
    return entries


def build_pointer_manifest(
    dataset: str,
    data_path: str,
    output_path: str,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build the full pointer manifest for a dataset.

    Args:
        dataset: "longmemeval_s" or "locomo"
        data_path: Path to the dataset JSON file or directory
        output_path: Where to write the manifest JSON
        limit: Optional limit on examples/personas to process (for debugging)

    Returns:
        Manifest dict with metadata and entries
    """
    # Resolve data path
    if os.path.isdir(data_path):
        json_files = [f for f in os.listdir(data_path) if f.endswith(".json")]
        if not json_files:
            raise ValueError(f"No JSON files found in directory: {data_path}")
        json_path = os.path.join(data_path, json_files[0])
    else:
        json_path = data_path

    print(f"[INFO] Loading raw JSON from: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    print(f"[INFO] Parsing JSON ({len(raw_text):,} chars)...")
    data = json.loads(raw_text)
    if limit:
        data = data[:limit]
        print(f"[INFO] Limited to first {limit} items.")

    # Build entries
    if dataset == "longmemeval_s":
        entries = _build_longmemeval_manifest(json_path, raw_text, data)
    elif dataset == "locomo":
        entries = _build_locomo_manifest(json_path, raw_text, data)
    else:
        raise ValueError(f"Unsupported dataset: {dataset}. Choose 'longmemeval_s' or 'locomo'.")

    manifest = {
        "manifest_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset,
        "source_file": os.path.normpath(json_path),
        "total_entries": len(entries),
        "entries": entries,
    }

    # Write with atomic replace
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)

    print(f"[INFO] Manifest saved to {output_path}")
    print(f"[INFO] Total entries: {len(entries)}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Build Pointer Manifest for External Benchmarks")
    parser.add_argument("--dataset", type=str, required=True, choices=["longmemeval_s", "locomo"])
    parser.add_argument("--data-path", type=str, required=True)
    parser.add_argument("--output-path", type=str, default="data/external/indexes/pointer_manifest.json")
    parser.add_argument("--limit", type=int, default=None, help="Limit examples/personas to process (for debugging)")
    args = parser.parse_args()

    manifest = build_pointer_manifest(
        dataset=args.dataset,
        data_path=args.data_path,
        output_path=args.output_path,
        limit=args.limit,
    )

    # Write a small summary report
    report_dir = "outputs/benchmarks"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "pointer_manifest_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Pointer Manifest Report\n\n")
        f.write(f"- **Dataset:** {manifest['dataset']}\n")
        f.write(f"- **Source file:** {manifest['source_file']}\n")
        f.write(f"- **Total entries:** {manifest['total_entries']:,}\n")
        f.write(f"- **Created at:** {manifest['created_at']}\n")
        f.write(f"- **Manifest file:** {args.output_path}\n\n")

        # Sample entries
        f.write("## Sample Entries\n\n")
        sample_keys = list(manifest['entries'].keys())[:3]
        for key in sample_keys:
            entry = manifest['entries'][key]
            f.write(f"### {key}\n")
            for k, v in entry.items():
                if k == "preview":
                    v = str(v)[:120] + ("..." if len(str(v)) > 120 else "")
                f.write(f"- {k}: {v}\n")
            f.write("\n")

    print(f"[INFO] Report saved to {report_path}")


if __name__ == "__main__":
    main()
