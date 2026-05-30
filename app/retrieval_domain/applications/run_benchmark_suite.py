"""Application service for benchmark orchestration."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Callable

from tqdm import tqdm

from app.retrieval_domain.retrieval.candidate_mapper import normalize_candidate_list

from .evaluate_retrieval_run import EvaluateRetrievalRun


RetrieveFn = Callable[..., list[dict[str, Any]]]


class RunBenchmarkSuite:
    """Coordinate retrieval and evaluation without owning scoring logic."""

    def __init__(self, evaluator: EvaluateRetrievalRun | None = None) -> None:
        self.evaluator = evaluator or EvaluateRetrievalRun()

    def run_examples(
        self,
        *,
        examples: list[Any],
        modes: list[str],
        mode_collections: dict[str, Any],
        adapter: Any,
        retrieve_fn: RetrieveFn,
        top_k: int,
        grammar_cache: dict[str, Any] | None = None,
        temporal_cache: dict[str, Any] | None = None,
        temporal_graph_cache: dict[str, Any] | None = None,
        partial_output: str | None = None,
    ) -> dict[str, list[Any]]:
        all_results: dict[str, list[Any]] = {mode: [] for mode in modes}

        with tqdm(examples, desc="Running Retrieval Examples") as pbar:
            for i, example in enumerate(pbar):
                pbar.set_postfix({"id": example.example_id})
                last_latency = 0.0
                last_result = None

                for mode in modes:
                    collection = mode_collections[mode]
                    unique_user_id = "benchmark_stable_user"

                    start_t = time.time()
                    candidates = retrieve_fn(
                        example.query,
                        mode,
                        top_k,
                        unique_user_id,
                        example_id=example.example_id,
                        collection=collection,
                        grammar_cache=grammar_cache,
                        temporal_cache=temporal_cache,
                        temporal_graph_cache=temporal_graph_cache,
                    )
                    normalized_candidates = [
                        candidate.to_dict()
                        for candidate in normalize_candidate_list(candidates)
                    ]
                    latency = (time.time() - start_t) * 1000
                    last_latency = latency

                    if not normalized_candidates and example.memory_units:
                        raise RuntimeError(
                            "CRITICAL RETRIEVAL FAILURE: "
                            f"Mode '{mode}' returned 0 candidates for example "
                            f"'{example.example_id}' despite {len(example.memory_units)} "
                            "indexed memory units. "
                            f"Collection: {collection.name}, Filter: example_id == {example.example_id}"
                        )

                    result = self.evaluator.evaluate_example(
                        adapter,
                        example,
                        normalized_candidates,
                        mode,
                        latency,
                    )
                    all_results[mode].append(result)
                    last_result = result

                if last_result is not None:
                    print(
                        f"     Lat: {last_latency:.1f}ms | H@1: {last_result.hit_at_1} "
                        f"| H@5: {last_result.hit_at_5} | MRR: {last_result.mrr:.3f}"
                    )

                if partial_output:
                    self._append_partial_output(partial_output, example, i, modes, all_results)

        return all_results

    @staticmethod
    def _append_partial_output(
        partial_output: str,
        example: Any,
        index: int,
        modes: list[str],
        all_results: dict[str, list[Any]],
    ) -> None:
        os.makedirs(os.path.dirname(partial_output), exist_ok=True)
        partial_entry = {
            "example_id": example.example_id,
            "query": example.query,
            "index": index,
            "results": {},
        }
        for mode in modes:
            result = all_results[mode][-1]
            partial_entry["results"][mode] = {
                "hit_at_1": result.hit_at_1,
                "hit_at_5": result.hit_at_5,
                "hit_at_10": result.hit_at_10,
                "mrr": result.mrr,
                "latency_ms": result.latency_ms,
                "diagnostics": result.diagnostics,
            }
        with open(partial_output, "a", encoding="utf-8") as pf:
            pf.write(json.dumps(partial_entry, ensure_ascii=False) + "\n")
