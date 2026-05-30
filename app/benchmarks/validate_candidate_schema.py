#!/usr/bin/env python3
"""Validate normalized benchmark retrieval candidate schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.benchmarks.longmemeval_s_adapter import LongMemEvalAdapter
from app.benchmarks.run_external_benchmark import (
    DEFAULT_BENCHMARK_CHROMA_DIR,
    run_retrieval,
    setup_isolated_env,
)
from app.retrieval_domain.applications import BuildBenchmarkIndex
from app.retrieval_domain.retrieval.candidate_mapper import normalize_candidate_list
from app.retrieval_domain.retrieval_models import FORBIDDEN_RETRIEVAL_HINT_KEYS


MODES = ["vector_only", "clean_hybrid_temporal_multihop_v2"]
REQUIRED_FIELDS = {
    "memory_id",
    "original_memory_id",
    "session_id",
    "source_session_id",
    "pointer_id",
    "source_text",
    "summary",
    "dia_ids",
    "score",
    "final_score",
    "score_breakdown",
    "metadata",
}


def _forbidden_paths(value: Any, path: str = "") -> list[str]:
    if not isinstance(value, Mapping):
        return []
    violations: list[str] = []
    for key, nested in value.items():
        key_text = str(key)
        current = f"{path}.{key_text}" if path else key_text
        if key_text in FORBIDDEN_RETRIEVAL_HINT_KEYS:
            violations.append(current)
        violations.extend(_forbidden_paths(nested, current))
    return violations


def _validate_candidate_dict(candidate: dict[str, Any], mode: str) -> None:
    missing = sorted(REQUIRED_FIELDS - set(candidate))
    if missing:
        raise AssertionError(f"{mode} candidate missing canonical fields: {missing}")
    forbidden = _forbidden_paths(candidate)
    if forbidden:
        raise AssertionError(f"{mode} candidate contains forbidden fields: {forbidden}")
    if not candidate["memory_id"]:
        raise AssertionError(f"{mode} candidate has empty memory_id")
    if not candidate["original_memory_id"]:
        raise AssertionError(f"{mode} candidate has empty original_memory_id")
    if not candidate["session_id"] and not candidate["source_session_id"]:
        raise AssertionError(f"{mode} candidate has no stable session field")
    if not isinstance(candidate["dia_ids"], list):
        raise AssertionError(f"{mode} dia_ids must be a list")
    if not isinstance(candidate["score_breakdown"], dict):
        raise AssertionError(f"{mode} score_breakdown must be present as a dict")
    if "pointer_id" not in candidate:
        raise AssertionError(f"{mode} pointer_id field must be present")


def main() -> int:
    print("Candidate schema validation")
    print("- Dataset: cleaned LongMemEval-S")
    print("- Limit: 5")
    print("- Turns mode: user_only")
    print("- Modes: vector_only, clean_hybrid_temporal_multihop_v2")

    adapter = LongMemEvalAdapter()
    examples = adapter.load_dataset(
        str(ROOT / "data" / "external" / "longmemeval_cleaned"),
        limit=5,
        schema="cleaned",
        turns_mode="user_only",
    )
    if not examples:
        raise RuntimeError("No examples loaded for candidate schema validation")

    client, temp_mem_path = setup_isolated_env("longmemeval_s", DEFAULT_BENCHMARK_CHROMA_DIR)
    index_builder = BuildBenchmarkIndex()
    collections = index_builder.build_collections(
        client,
        temp_mem_path,
        examples,
        MODES,
        "longmemeval_s",
        "cleaned",
        "user_only",
        batch_size=50,
        validate_batch_count=True,
        use_existing_index=True,
    )

    output: dict[str, Any] = {"modes": {}}
    for mode in MODES:
        print(f"[PHASE] Validating mode: {mode}")
        raw_candidates = run_retrieval(
            examples[0].query,
            mode,
            10,
            "benchmark_stable_user",
            example_id=examples[0].example_id,
            collection=collections[mode],
        )
        candidates = normalize_candidate_list(raw_candidates)
        if not candidates:
            raise AssertionError(f"{mode} returned no candidates")

        candidate_dicts = [candidate.to_dict() for candidate in candidates]
        for candidate in candidate_dicts:
            _validate_candidate_dict(candidate, mode)

        result = adapter.evaluate_retrieval(examples[0], candidate_dicts)
        output["modes"][mode] = {
            "candidate_count": len(candidate_dicts),
            "top_candidate_keys": sorted(candidate_dicts[0].keys()),
            "evaluator_consumed_to_dict": True,
            "hit_at_1": result.hit_at_1,
            "hit_at_5": result.hit_at_5,
            "mrr": result.mrr,
        }

    output_path = ROOT / "outputs" / "benchmarks" / "ddd_phase3_candidate_schema_validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"PASS: candidate schema validation passed. Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
