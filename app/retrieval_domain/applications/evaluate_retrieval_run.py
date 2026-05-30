"""Application service for retrieval evaluation orchestration."""

from __future__ import annotations

from typing import Any

from app.retrieval_domain.retrieval.candidate_mapper import normalize_candidate_list


class EvaluateRetrievalRun:
    """Evaluate ranked candidates after retrieval has completed."""

    CLEAN_HYBRID_MODES = {
        "clean_hybrid",
        "clean_hybrid_grammar",
        "clean_hybrid_temporal",
        "clean_hybrid_temporal_multihop",
        "clean_hybrid_temporal_multihop_v2",
    }
    MULTIHOP_MODES = {
        "clean_hybrid_temporal_multihop",
        "clean_hybrid_temporal_multihop_v2",
    }

    def evaluate_example(
        self,
        adapter: Any,
        example: Any,
        candidates: list[dict[str, Any]],
        mode: str,
        latency_ms: float,
    ) -> Any:
        """Call the existing evaluator without changing metrics or ranking.

        Cleaned LongMemEval-S evaluation is delegated by its adapter to the
        Evaluation Context hit policy. Legacy adapters remain dict-compatible.
        """

        normalized_candidates = [
            candidate.to_dict()
            for candidate in normalize_candidate_list(candidates)
        ]
        result = adapter.evaluate_retrieval(example, normalized_candidates)
        result.latency_ms = latency_ms
        self.attach_diagnostics(result, mode, normalized_candidates)
        return result

    def attach_diagnostics(
        self,
        result: Any,
        mode: str,
        candidates: list[dict[str, Any]],
    ) -> None:
        if mode not in self.CLEAN_HYBRID_MODES or not candidates:
            return

        top_candidate = candidates[0]
        diag_scores = {
            "dense_raw": top_candidate.get("dense_raw"),
            "sparse_raw": top_candidate.get("sparse_raw"),
            "grammar_score": top_candidate.get("grammar_score"),
            "emotion_score": top_candidate.get("emotion_score"),
            "metadata_score": top_candidate.get("metadata_score"),
            "temporal_score": top_candidate.get("temporal_score"),
            "dense_raw_norm": top_candidate.get("dense_raw_norm"),
            "sparse_raw_norm": top_candidate.get("sparse_raw_norm"),
            "grammar_score_norm": top_candidate.get("grammar_score_norm"),
            "emotion_score_norm": top_candidate.get("emotion_score_norm"),
            "metadata_score_norm": top_candidate.get("metadata_score_norm"),
            "temporal_score_norm": top_candidate.get("temporal_score_norm"),
            "final_score": top_candidate.get("final_score"),
        }

        if mode in self.MULTIHOP_MODES:
            diag_scores["temporal_event_score"] = top_candidate.get("temporal_event_score")
            diag_scores["temporal_pair_score"] = top_candidate.get("temporal_pair_score")
            diag_scores["temporal_pair_score_norm"] = top_candidate.get(
                "temporal_pair_score_norm"
            )
            diag_scores["supporting_event_ids"] = top_candidate.get("supporting_event_ids")
            diag_scores["supporting_memory_ids"] = top_candidate.get("supporting_memory_ids")
            diag_scores["_diag_gate_reason"] = top_candidate.get("_diag_gate_reason")
            diag_scores["_diag_events_found"] = top_candidate.get("_diag_events_found")
            diag_scores["_diag_pair_scores"] = top_candidate.get("_diag_pair_scores")
            diag_scores["_diag_event_targets"] = top_candidate.get("_diag_event_targets")

        result.diagnostics = {
            "top_candidate_scores": diag_scores,
            "candidate_count": len(candidates),
        }

    @staticmethod
    def summarize_results(results: list[Any]) -> dict[str, float | int]:
        total = len(results)
        if total == 0:
            return {
                "recall_at_1": 0.0,
                "recall_at_5": 0.0,
                "recall_at_10": 0.0,
                "mrr": 0.0,
                "avg_latency_ms": 0.0,
                "total_examples": 0,
            }
        return {
            "recall_at_1": sum(1 for r in results if r.hit_at_1) / total,
            "recall_at_5": sum(1 for r in results if r.hit_at_5) / total,
            "recall_at_10": sum(1 for r in results if r.hit_at_10) / total,
            "mrr": sum(r.mrr for r in results) / total,
            "avg_latency_ms": sum(r.latency_ms for r in results) / total,
            "total_examples": total,
        }
