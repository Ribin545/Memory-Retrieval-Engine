"""Normalize benchmark retrieval outputs into one candidate contract."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.retrieval_domain.retrieval_models import (
    FORBIDDEN_RETRIEVAL_HINT_KEYS,
    RetrievalCandidate,
    ScoreBreakdown,
)


CANONICAL_CANDIDATE_FIELDS = frozenset(
    {
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
)

LEGACY_LIST_FIELDS = ("dia_ids", "contained_dia_ids")

SCORE_COMPONENT_KEYS = {
    "dense_raw",
    "sparse_raw",
    "grammar_score",
    "emotion_score",
    "metadata_score",
    "temporal_score",
    "temporal_event_score",
    "temporal_pair_score",
    "dense_raw_norm",
    "sparse_raw_norm",
    "grammar_score_norm",
    "emotion_score_norm",
    "metadata_score_norm",
    "temporal_score_norm",
    "temporal_pair_score_norm",
    "semantic_similarity",
    "distance",
    "_sparse_score",
    "final_score",
    "score",
}


def _strip_forbidden(mapping: Mapping[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in dict(mapping or {}).items():
        if key in FORBIDDEN_RETRIEVAL_HINT_KEYS:
            continue
        if isinstance(value, Mapping):
            clean[key] = _strip_forbidden(value)
        else:
            clean[key] = value
    return clean


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item) for item in value]
    return [str(value)]


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_breakdown(candidate: Mapping[str, Any]) -> ScoreBreakdown:
    components = {
        key: float(value)
        for key, value in candidate.items()
        if key in SCORE_COMPONENT_KEYS and _as_float(value) is not None
    }
    return ScoreBreakdown(
        dense=_as_float(candidate.get("dense_raw")),
        sparse=_as_float(candidate.get("sparse_raw") or candidate.get("_sparse_score")),
        grammar=_as_float(candidate.get("grammar_score")),
        emotion=_as_float(candidate.get("emotion_score")),
        metadata=_as_float(candidate.get("metadata_score")),
        temporal=_as_float(candidate.get("temporal_score")),
        temporal_event=_as_float(candidate.get("temporal_event_score")),
        temporal_pair=_as_float(candidate.get("temporal_pair_score")),
        final=_as_float(candidate.get("final_score") or candidate.get("score")),
        components=components,
    )


def from_chroma_result(raw_results: Mapping[str, Any], index: int) -> RetrievalCandidate:
    """Create a candidate from one Chroma query result row."""

    ids = raw_results.get("ids", [[]])[0]
    metadatas = raw_results.get("metadatas", [[]])[0]
    documents = raw_results.get("documents", [[]])[0]
    distances = raw_results.get("distances", [[]])[0]

    raw_id = ids[index]
    metadata = _strip_forbidden(metadatas[index] or {})
    document = documents[index] or ""
    distance = float(distances[index])
    similarity = round(1.0 - distance, 6)
    session_id = metadata.get("session_id") or metadata.get("source_session_id")

    candidate = {
        "memory_id": metadata.get("memory_id", raw_id),
        "original_memory_id": metadata.get("original_memory_id") or metadata.get("memory_id") or raw_id,
        "benchmark_name": metadata.get("benchmark_name", ""),
        "example_id": metadata.get("example_id", ""),
        "session_id": session_id,
        "source_session_id": metadata.get("source_session_id") or session_id,
        "pointer_id": metadata.get("pointer_id"),
        "source_text": document,
        "summary": document,
        "dia_ids": [],
        "memory_unit_type": metadata.get("memory_unit_type", "unknown"),
        "user_id": metadata.get("user_id", ""),
        "distance": round(distance, 6),
        "semantic_similarity": similarity,
        "final_score": similarity,
        "score": similarity,
    }
    return normalize_candidate_dict(candidate)


def from_clean_hybrid_candidate(candidate: Mapping[str, Any]) -> RetrievalCandidate:
    """Create a candidate from the benchmark clean-hybrid-family retriever."""

    return normalize_candidate_dict(candidate)


def normalize_candidate_dict(candidate: Mapping[str, Any] | RetrievalCandidate) -> RetrievalCandidate:
    """Normalize one candidate mapping without changing ranking or scores."""

    if isinstance(candidate, RetrievalCandidate):
        return candidate

    clean = _strip_forbidden(candidate)
    session_id = clean.get("session_id") or clean.get("source_session_id")
    source_session_id = clean.get("source_session_id") or session_id
    memory_id = str(clean.get("memory_id") or clean.get("id") or "")
    original_memory_id = clean.get("original_memory_id") or memory_id
    source_text = clean.get("source_text") or clean.get("summary") or ""
    summary = clean.get("summary") or source_text

    dia_ids: list[str] = []
    for key in LEGACY_LIST_FIELDS:
        if clean.get(key):
            dia_ids = _as_list(clean.get(key))
            break

    final_score = _as_float(clean.get("final_score"))
    score = _as_float(clean.get("score"))
    if score is None:
        score = final_score if final_score is not None else _as_float(clean.get("semantic_similarity"))
    if final_score is None:
        final_score = score

    metadata = {
        key: value
        for key, value in clean.items()
        if key not in CANONICAL_CANDIDATE_FIELDS and key not in FORBIDDEN_RETRIEVAL_HINT_KEYS
    }

    return RetrievalCandidate(
        memory_id=memory_id,
        original_memory_id=str(original_memory_id) if original_memory_id is not None else None,
        session_id=str(session_id) if session_id is not None else None,
        source_session_id=str(source_session_id) if source_session_id is not None else None,
        pointer_id=str(clean["pointer_id"]) if clean.get("pointer_id") is not None else None,
        source_text=str(source_text),
        summary=str(summary) if summary is not None else None,
        dia_ids=tuple(dia_ids),
        score=score,
        final_score=final_score,
        score_breakdown=_score_breakdown(clean),
        metadata=metadata,
    )


def normalize_candidate_list(
    candidates: Sequence[Mapping[str, Any] | RetrievalCandidate],
) -> list[RetrievalCandidate]:
    """Normalize candidates while preserving their input order."""

    return [normalize_candidate_dict(candidate) for candidate in candidates]
