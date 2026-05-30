"""Benchmark retrieval dispatch without owning scoring formulas."""

from __future__ import annotations

from typing import Any

from app.benchmarks.clean_hybrid_retriever import clean_hybrid_retrieve
from app.retrieval_domain.retrieval.candidate_mapper import (
    from_chroma_result,
    normalize_candidate_list,
)


def reconstruct_vector_candidates(raw_results: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert Chroma vector query results into normalized candidate dicts."""

    ids = raw_results.get("ids", [[]])[0]
    candidates = []
    for idx, _raw_id in enumerate(ids):
        candidates.append(from_chroma_result(raw_results, idx).to_dict())
    return candidates


def run_retrieval(
    query: str,
    mode: str,
    top_k: int,
    unique_user_id: str,
    example_id: str,
    collection: Any = None,
    grammar_cache: dict[str, Any] | None = None,
    temporal_cache: dict[str, Any] | None = None,
    temporal_graph_cache: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Run the selected retrieval mode using the existing scoring functions."""

    if mode == "vector_only":
        from app.memory_retriever import embed_query

        query_embedding = embed_query(query)
        if collection is None:
            from app.vector_store import query_index

            raw_results = query_index(
                query_embedding=query_embedding,
                user_id=unique_user_id,
                top_k=max(top_k, 10),
            )
        else:
            raw_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=max(top_k, 10),
                where={"example_id": {"$eq": example_id}},
                include=["metadatas", "distances", "documents"],
            )
        return reconstruct_vector_candidates(raw_results)[:top_k]

    if mode == "bm25_only":
        from app.hybrid_memory_retriever import hybrid_retrieve_memory_candidates

        candidates = hybrid_retrieve_memory_candidates(
            user_id=unique_user_id,
            query=query,
            top_k_dense=top_k,
            top_k_sparse=top_k,
            final_k=top_k,
        )
        for candidate in candidates:
            candidate["final_score"] = candidate.get("_sparse_score", 0.0)
            candidate["score"] = candidate["final_score"]
        candidates.sort(key=lambda item: item["final_score"], reverse=True)
        return [candidate.to_dict() for candidate in normalize_candidate_list(candidates)]

    if mode == "hybrid_dense_sparse":
        from app.hybrid_memory_retriever import hybrid_retrieve_memory_candidates

        candidates = hybrid_retrieve_memory_candidates(
            user_id=unique_user_id,
            query=query,
            top_k_dense=top_k,
            top_k_sparse=top_k,
            final_k=top_k,
        )
        return [candidate.to_dict() for candidate in normalize_candidate_list(candidates)]

    if mode == "grammar_emotion_reranker":
        from app.hybrid_memory_retriever import hybrid_retrieve_memory_candidates

        candidates = hybrid_retrieve_memory_candidates(
            user_id=unique_user_id,
            query=query,
            detected_emotion={"primary": "neutral", "intent": "specific_episode_recall"},
            topic_hints={"topic_family": "general", "topic_hints": []},
            top_k_dense=top_k,
            top_k_sparse=top_k,
            final_k=top_k,
        )
        return [candidate.to_dict() for candidate in normalize_candidate_list(candidates)]

    if mode in (
        "clean_hybrid",
        "clean_hybrid_grammar",
        "clean_hybrid_temporal",
        "clean_hybrid_temporal_multihop",
        "clean_hybrid_temporal_multihop_v2",
    ):
        cache = (
            grammar_cache
            if mode
            in (
                "clean_hybrid_grammar",
                "clean_hybrid_temporal",
                "clean_hybrid_temporal_multihop",
                "clean_hybrid_temporal_multihop_v2",
            )
            else None
        )
        candidates = clean_hybrid_retrieve(
            query=query,
            collection=collection,
            unique_user_id=unique_user_id,
            example_id=example_id,
            grammar_cache=cache,
            temporal_cache=temporal_cache
            if mode
            in (
                "clean_hybrid_temporal",
                "clean_hybrid_temporal_multihop",
                "clean_hybrid_temporal_multihop_v2",
            )
            else None,
            temporal_graph_cache=temporal_graph_cache
            if mode in ("clean_hybrid_temporal_multihop", "clean_hybrid_temporal_multihop_v2")
            else None,
            top_k_dense=max(top_k, 15),
            top_k_final=top_k,
            mode=mode,
        )
        return [candidate.to_dict() for candidate in normalize_candidate_list(candidates)]

    return []
