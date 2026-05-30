"""
Clean Hybrid Retriever for External Benchmarks

Fuses isolated raw signals with fixed weights:
  - dense_raw: 1.0 - cosine_distance from direct Chroma query
  - sparse_raw: exact-phrase + all-terms overlap on source_text/summary only
  - grammar_score: overlap between query grammar frame and cached memory grammar frame
  - emotion_score: Jaccard overlap between query and cached emotion terms
  - metadata_score: simple session/evidence/type hint matches
  - temporal_score: overlap between query temporal frame and cached memory temporal events

Each signal is min-max normalized per-query over the candidate pool.
Weights are fixed (no tuning).
"""
import os
import sys
import json
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.memory_retriever import embed_query
from app.hybrid_memory_retriever import _exact_phrase_score, _all_terms_score
from app.benchmarks.temporal_query_parser import extract_temporal_frame
from app.benchmarks.temporal_query_parser_v2 import extract_temporal_frame_v2
from app.benchmarks.temporal_multihop_scorer import compute_multihop_scores
import re

def _extract_query_grammar(query: str) -> Dict[str, Any]:
    """
    Parse query with spaCy dependency parsing.
    Extracts: root verb, entities, object head, context terms, question type.
    Queries are short (<100 chars) so spaCy is safe and fast here.
    """
    if not query:
        return {
            "verb_lemma": "", "object_head": "", "context_object": "",
            "pattern_key": "", "entities": [], "question_type": "unknown",
            "context_terms": [],
        }

    try:
        from app.retrieval_domain.features.grammar_frame_extractor import _ensure_nlp_loaded
        nlp = _ensure_nlp_loaded()
        if not nlp or nlp is False:
            raise RuntimeError("spaCy unavailable")

        doc = nlp(query)

        # Question type detection
        q_lower = query.lower().strip()
        question_type = "unknown"
        wh_map = {
            "what": "what", "when": "when", "where": "where",
            "who": "who", "why": "why", "how": "how",
            "which": "which", "whose": "whose",
        }
        for wh, label in wh_map.items():
            if q_lower.startswith(wh):
                question_type = label
                break

        # Named entities
        entities = [ent.text.lower().replace(" ", "_") for ent in doc.ents if ent.label_ in {"PERSON", "ORG", "GPE", "NORP"}]

        # Root verb
        root_verb = ""
        root_verb_lemma = ""
        root = next((t for t in doc if t.dep_ == "ROOT"), None)
        if root:
            # If ROOT is auxiliary (did/is/was), look for xcomp or main verb child
            if root.pos_ == "AUX":
                main_verb = next((t for t in root.children if t.pos_ == "VERB"), None)
                if main_verb:
                    root_verb = main_verb.text.lower()
                    root_verb_lemma = getattr(main_verb, "lemma_", main_verb.text.lower())
                else:
                    root_verb = root.text.lower()
                    root_verb_lemma = getattr(root, "lemma_", root.text.lower())
            else:
                root_verb = root.text.lower()
                root_verb_lemma = getattr(root, "lemma_", root.text.lower())

        # Object head: direct object or attribute of root or main verb
        object_head = ""
        if root:
            target = root
            # If root is AUX, find the actual verb
            if root.pos_ == "AUX":
                vchild = next((t for t in root.children if t.pos_ == "VERB"), None)
                if vchild:
                    target = vchild
            obj_tok = next((t for t in target.children if t.dep_ in {"dobj", "attr", "oprd", "pobj"}), None)
            if obj_tok:
                object_head = obj_tok.text.lower()
                # Include compound modifiers
                compounds = [t.text.lower() for t in obj_tok.children if t.dep_ == "compound" and t.i < obj_tok.i]
                if compounds:
                    object_head = "_".join(compounds + [object_head])

        # Context terms: prepositional phrases
        context_terms = []
        context_object = ""
        for token in doc:
            if token.dep_ == "prep":
                prep_text = token.text.lower()
                pobj = next((t for t in token.children if t.dep_ in {"pobj", "pcomp"}), None)
                if pobj:
                    pobj_text = pobj.text.lower()
                    compounds = [t.text.lower() for t in pobj.children if t.dep_ == "compound" and t.i < pobj.i]
                    if compounds:
                        pobj_text = "_".join(compounds + [pobj_text])
                    context_terms.append(f"{prep_text}_{pobj_text}")
                    if not context_object:
                        context_object = pobj_text

        # Pattern key: subject.verb.object.context
        entity_part = entities[0] if entities else "user"
        pattern_key = f"{entity_part}.{root_verb_lemma}.{object_head}" if root_verb_lemma else f"{entity_part}.{object_head}"
        if context_object:
            pattern_key += f".context_{context_object}"

        return {
            "verb_lemma": root_verb_lemma,
            "object_head": object_head,
            "context_object": context_object,
            "pattern_key": pattern_key,
            "entities": entities,
            "question_type": question_type,
            "context_terms": context_terms,
        }

    except Exception:
        # Fallback: minimal regex-based extraction
        words = re.findall(r"[a-zA-Z']+", query)
        verb = words[1].lower() if len(words) >= 2 else ""
        if verb.endswith("ed") and len(verb) > 3:
            verb = verb[:-2]
        elif verb.endswith("s") and len(verb) > 2:
            verb = verb[:-1]
        object_head = words[-1].lower() if words else ""
        prep_match = re.search(r"\b(before|about|with|for|during|after|in|on|at)\s+([a-zA-Z']+)", query, re.IGNORECASE)
        context_object = prep_match.group(2).lower() if prep_match else ""
        pattern_key = f"user.{verb}.{object_head}" if verb else f"user.{object_head}"
        if context_object:
            pattern_key += f".context_{context_object}"
        return {
            "verb_lemma": verb,
            "object_head": object_head,
            "context_object": context_object,
            "pattern_key": pattern_key,
            "entities": [],
            "question_type": "unknown",
            "context_terms": [f"{prep_match.group(1).lower()}_{context_object}"] if prep_match else [],
        }


WEIGHTS = {
    "dense_raw": 0.35,
    "sparse_raw": 0.40,
    "grammar_score": 0.15,
    "metadata_score": 0.10,
    "emotion_score": 0.00,
}

WEIGHTS_TEMPORAL = {
    "dense_raw": 0.30,
    "sparse_raw": 0.35,
    "grammar_score": 0.10,
    "temporal_score": 0.15,
    "metadata_score": 0.10,
    "emotion_score": 0.00,
}

WEIGHTS_TEMPORAL_MULTIHOP = {
    "dense_raw": 0.25,
    "sparse_raw": 0.30,
    "grammar_score": 0.10,
    "temporal_score": 0.15,
    "temporal_pair_score": 0.10,
    "metadata_score": 0.10,
    "emotion_score": 0.00,
}


def _compute_sparse_raw_score(query: str, candidate: Dict[str, Any]) -> float:
    """Compute sparse raw score using only source_text and summary (no metadata subcomponents)."""
    text = candidate.get("source_text") or candidate.get("summary") or ""
    if not text:
        return 0.0
    exact = _exact_phrase_score(query, text)
    all_terms = _all_terms_score(query, text)
    return max(exact, all_terms)


def _compute_grammar_score_single(query_frame: Dict[str, Any], candidate_frame: Dict[str, Any]) -> float:
    """Compare query grammar frame against a single cached grammar frame."""
    if not candidate_frame:
        return 0.0

    q_verb = query_frame.get("verb_lemma", "")
    q_obj = query_frame.get("object_head", "")
    q_ctx = query_frame.get("context_object", "")
    q_pat = query_frame.get("pattern_key", "")
    q_entities = set(query_frame.get("entities", []))

    c_verb = candidate_frame.get("verb_lemma", "")
    c_obj = candidate_frame.get("object_head", "")
    c_ctx = candidate_frame.get("context_object", "")
    c_pat = candidate_frame.get("pattern_key", "")
    c_entities = set(candidate_frame.get("entities", []))

    matches = 0.0
    total = 0.0

    # Verb lemma match
    if q_verb:
        total += 1.0
        if q_verb.lower() == c_verb.lower():
            matches += 1.0

    # Object head match
    if q_obj:
        total += 1.0
        if q_obj.lower() == c_obj.lower():
            matches += 1.0

    # Context object match
    if q_ctx:
        total += 1.0
        if q_ctx.lower() == c_ctx.lower():
            matches += 1.0

    # Pattern component overlap
    if q_pat:
        total += 1.0
        q_parts = set(q_pat.lower().split("."))
        c_parts = set(c_pat.lower().split("."))
        overlap = q_parts & c_parts
        if overlap:
            matches += len(overlap) / max(len(q_parts), len(c_parts))

    # Entity overlap bonus (extra credit, doesn't penalize)
    if q_entities and c_entities:
        entity_overlap = q_entities & c_entities
        if entity_overlap:
            matches += 0.5 * (len(entity_overlap) / max(len(q_entities), len(c_entities)))

    if total == 0:
        return 0.0
    return min(1.0, matches / total)


def _compute_grammar_score(query_frame: Dict[str, Any], candidate_cache: Dict[str, Any]) -> float:
    """Compare query grammar frame against cached memory grammar frame(s).
    Handles both old flat format and new frames-array format."""
    if not query_frame or not candidate_cache:
        return 0.0

    # New format: frames array — compare against all frames, return max score
    frames = candidate_cache.get("frames")
    if frames and isinstance(frames, list):
        best_score = 0.0
        for frame in frames:
            score = _compute_grammar_score_single(query_frame, frame)
            if score > best_score:
                best_score = score
        return best_score

    # Old flat format (backward compatibility)
    return _compute_grammar_score_single(query_frame, candidate_cache)


def _compute_emotion_score(query_emotion: Dict[str, Any], candidate_cache: Dict[str, Any]) -> float:
    """Jaccard overlap between query emotion terms and cached emotion terms."""
    q_terms = set(query_emotion.get("emotion_terms", []))
    c_terms = set(candidate_cache.get("emotion_terms", []))
    if not q_terms or not c_terms:
        return 0.0
    intersection = q_terms & c_terms
    union = q_terms | c_terms
    if not union:
        return 0.0
    return len(intersection) / len(union)


def _compute_metadata_score(query: str, candidate: Dict[str, Any]) -> float:
    """
    Simple query-derived metadata hits.

    Ground-truth session IDs, evidence IDs, and answer-derived IDs must not
    enter retrieval scoring. Evaluation owns those fields after ranking.
    """
    score = 0.0
    hits = 0

    # Memory unit type relevance (simple heuristic: if query mentions "session" vs "turn")
    q_lower = query.lower()
    mu_type = candidate.get("memory_unit_type", "")
    if "turn" in q_lower and mu_type == "turn":
        hits += 1
        score += 0.5
    elif "session" in q_lower and mu_type == "session":
        hits += 1
        score += 0.5

    # Preserve the historical denominator so this integrity fix removes the
    # leakage channel without retuning the metadata signal's relative scale.
    return min(1.0, score / 3.0) if hits > 0 else 0.0


def _compute_temporal_score(query_temporal: Dict[str, Any], candidate_cache: Dict[str, Any]) -> float:
    """Compare query temporal frame against cached memory temporal events."""
    if not query_temporal or not candidate_cache:
        return 0.0

    query_dates = query_temporal.get("date_entities", [])
    query_prep = query_temporal.get("temporal_preposition", "")
    query_ref = query_temporal.get("reference_event", "")

    candidate_events = candidate_cache.get("temporal_events", [])
    candidate_dates = candidate_cache.get("date_entities", [])

    if not candidate_events and not candidate_dates:
        return 0.0

    scores = []

    # 1. Exact date text match
    for qd in query_dates:
        for ce in candidate_events:
            if ce.get("normalized_date") and qd["text"].lower() == ce["normalized_date"].lower():
                scores.append(1.0)
            elif ce.get("date_text") and qd["text"].lower() == ce["date_text"].lower():
                scores.append(1.0)

    # 2. Partial date overlap (year/month)
    for qd in query_dates:
        qtext = qd["text"]
        year_match = re.search(r"\b(\d{4})\b", qtext)
        month_match = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\b", qtext, re.IGNORECASE)
        for ce in candidate_events:
            cdate = ce.get("normalized_date") or ce.get("date_text", "")
            if year_match and year_match.group(1) in cdate:
                scores.append(0.5)
            if month_match and month_match.group(1).lower() in cdate.lower():
                scores.append(0.5)

    # 3. Preposition-aware relative scoring
    # If query asks "after X" and candidate event is X itself, boost slightly
    if query_prep and query_ref:
        for ce in candidate_events:
            event_span = ce.get("event_span", "").lower()
            related = [t.lower() for t in ce.get("related_tokens", [])]
            if query_ref.lower() in event_span or any(query_ref.lower() == r for r in related):
                if query_prep in {"after", "before", "during", "since", "until"}:
                    scores.append(0.3)

    # 4. Temporal modifier overlap
    query_mods = query_temporal.get("temporal_modifiers", [])
    for qm in query_mods:
        for ce in candidate_events:
            if qm.lower() in ce.get("event_span", "").lower():
                scores.append(0.2)

    if not scores:
        return 0.0
    return max(scores)


def _min_max_normalize(candidates: List[Dict[str, Any]], signal: str) -> None:
    """Normalize a signal across the candidate pool in-place."""
    values = [c.get(signal, 0.0) for c in candidates]
    min_s = min(values) if values else 0.0
    max_s = max(values) if values else 0.0
    norm_key = f"{signal}_norm"
    if max_s > min_s:
        for c in candidates:
            c[norm_key] = (c.get(signal, 0.0) - min_s) / (max_s - min_s)
    else:
        for c in candidates:
            c[norm_key] = 0.0


def clean_hybrid_retrieve(
    query: str,
    collection,
    unique_user_id: str,
    example_id: Optional[str] = None,
    grammar_cache: Optional[Dict[str, Any]] = None,
    temporal_cache: Optional[Dict[str, Any]] = None,
    temporal_graph_cache: Optional[Dict[str, Any]] = None,
    top_k_dense: int = 15,
    top_k_final: int = 10,
    mode: str = "clean_hybrid",
) -> List[Dict[str, Any]]:
    """
    Retrieve candidates using clean hybrid fusion of isolated raw signals.

    Args:
        query: The user query string.
        collection: ChromaDB collection (isolated benchmark collection).
        unique_user_id: Retained caller context for compatibility.
        example_id: Example ID used to restrict candidates in the stable benchmark collection.
        grammar_cache: Optional flat dict keyed by memory_id with cached grammar fields.
        temporal_cache: Optional flat dict keyed by memory_id with cached temporal events.
        temporal_graph_cache: Optional event graph dict with event_cards, events_by_memory, links.
        top_k_dense: Number of dense candidates to fetch from Chroma.
        top_k_final: Final number of candidates to return.
        mode: "clean_hybrid", "clean_hybrid_temporal", or "clean_hybrid_temporal_multihop".

    Returns:
        List of candidate dicts with all raw and normalized scores attached.
    """
    # --- 1. Dense raw: direct Chroma query ---
    query_embedding = embed_query(query)
    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k_dense,
        where={"example_id": {"$eq": example_id}} if example_id else None,
        include=["metadatas", "distances", "documents"],
    )

    ids = raw_results.get("ids", [[]])[0]
    metadatas = raw_results.get("metadatas", [[]])[0]
    documents = raw_results.get("documents", [[]])[0]
    distances = raw_results.get("distances", [[]])[0]

    candidates: List[Dict[str, Any]] = []
    for idx, raw_id in enumerate(ids):
        metadata = metadatas[idx] or {}
        document = documents[idx] or ""
        distance = float(distances[idx])

        # Parse dia_ids / evidence_ids from metadata JSON strings
        dia_ids_raw = metadata.get("dia_ids_json") or metadata.get("contained_dia_ids_json") or "[]"
        evidence_ids_raw = metadata.get("evidence_ids_json") or "[]"
        try:
            dia_ids = json.loads(dia_ids_raw) if dia_ids_raw else []
        except Exception:
            dia_ids = []
        try:
            evidence_ids = json.loads(evidence_ids_raw) if evidence_ids_raw else []
        except Exception:
            evidence_ids = []

        source_text = metadata.get("source_text") or document
        session_id = metadata.get("session_id") or metadata.get("source_session_id") or ""

        candidate = {
            "memory_id": metadata.get("memory_id", raw_id),
            "original_memory_id": metadata.get("original_memory_id", metadata.get("memory_id", raw_id)),
            "pointer_id": metadata.get("pointer_id", ""),
            "benchmark_name": metadata.get("benchmark_name", ""),
            "example_id": metadata.get("example_id", ""),
            "session_id": session_id,
            "source_session_id": session_id,
            "source_text": source_text,
            "summary": metadata.get("summary") or source_text,
            "dia_ids": dia_ids,
            "contained_dia_ids": dia_ids,
            "evidence_ids": evidence_ids,
            "memory_unit_type": metadata.get("memory_unit_type", "unknown"),
            "user_id": metadata.get("user_id", ""),
            "distance": round(distance, 6),
            "dense_raw": round(1.0 - distance, 6),
        }
        candidates.append(candidate)

    if not candidates:
        return []

    # --- 2. Extract query frames ---
    query_grammar = _extract_query_grammar(query)

    # Use v2 parser for multihop mode; v1 parser otherwise
    if mode == "clean_hybrid_temporal_multihop":
        query_temporal = extract_temporal_frame_v2(query, parser_version="v1") if temporal_cache else {"has_temporal_signal": False, "is_multi_event": False}
    elif mode == "clean_hybrid_temporal_multihop_v2":
        query_temporal = extract_temporal_frame_v2(query, parser_version="v2") if temporal_cache else {"has_temporal_signal": False, "is_multi_event": False}
    else:
        query_temporal = extract_temporal_frame(query) if temporal_cache else {"has_temporal_signal": False}

    # Emotion signal disabled until structural extractor is benchmark-proven
    query_emotion = {"emotion_terms": []}

    # --- 3. Compute raw scores for each candidate ---
    for c in candidates:
        c["sparse_raw"] = _compute_sparse_raw_score(query, c)

        grammar_entry = grammar_cache.get(c.get("original_memory_id", c["memory_id"])) if grammar_cache else None
        c["grammar_score"] = _compute_grammar_score(query_grammar, grammar_entry) if grammar_entry else 0.0
        c["emotion_score"] = _compute_emotion_score(query_emotion, grammar_entry) if grammar_entry else 0.0
        c["metadata_score"] = _compute_metadata_score(query, c)

        temporal_entry = temporal_cache.get(c.get("original_memory_id", c["memory_id"])) if temporal_cache else None
        c["temporal_score"] = _compute_temporal_score(query_temporal, temporal_entry) if temporal_entry else 0.0

    # --- 4. Multi-hop temporal scoring (only for multihop modes) ---
    multihop_scores = {}
    if mode in ("clean_hybrid_temporal_multihop", "clean_hybrid_temporal_multihop_v2") and temporal_graph_cache:
        multihop_scores = compute_multihop_scores(candidates, query_temporal, temporal_graph_cache, return_diagnostics=True)
        for c in candidates:
            mem_id = c["memory_id"]
            mh = multihop_scores.get(mem_id, {})
            c["temporal_event_score"] = mh.get("temporal_event_score", 0.0)
            c["temporal_pair_score"] = mh.get("temporal_pair_score", 0.0)
            c["supporting_event_ids"] = mh.get("supporting_event_ids", [])
            c["supporting_memory_ids"] = mh.get("supporting_memory_ids", [])
            # Pass through diagnostics
            for diag_key in ["_diag_gate_reason", "_diag_events_found", "_diag_pair_scores", "_diag_event_targets"]:
                if diag_key in mh:
                    c[diag_key] = mh[diag_key]
    else:
        for c in candidates:
            c["temporal_event_score"] = 0.0
            c["temporal_pair_score"] = 0.0
            c["supporting_event_ids"] = []
            c["supporting_memory_ids"] = []

    # --- 5. Per-query min-max normalization ---
    signals = ["dense_raw", "sparse_raw", "grammar_score", "emotion_score", "metadata_score"]
    if temporal_cache and any(c.get("temporal_score", 0.0) > 0.0 for c in candidates):
        signals.append("temporal_score")

    # Gated temporal_pair_score inclusion
    temporal_pair_active = False
    if mode in ("clean_hybrid_temporal_multihop", "clean_hybrid_temporal_multihop_v2") and temporal_graph_cache:
        temporal_pair_active = any(c.get("temporal_pair_score", 0.0) > 0.5 for c in candidates)
        if temporal_pair_active:
            signals.append("temporal_pair_score")

    for signal in signals:
        _min_max_normalize(candidates, signal)

    # --- 6. Fuse with fixed weights ---
    if mode in ("clean_hybrid_temporal_multihop", "clean_hybrid_temporal_multihop_v2"):
        weights = WEIGHTS_TEMPORAL_MULTIHOP
    elif mode == "clean_hybrid_temporal":
        weights = WEIGHTS_TEMPORAL
    else:
        weights = WEIGHTS

    for c in candidates:
        final = (
            c.get("dense_raw_norm", 0.0) * weights["dense_raw"] +
            c.get("sparse_raw_norm", 0.0) * weights["sparse_raw"] +
            c.get("grammar_score_norm", 0.0) * weights["grammar_score"] +
            c.get("emotion_score_norm", 0.0) * weights["emotion_score"] +
            c.get("metadata_score_norm", 0.0) * weights["metadata_score"]
        )
        if "temporal_score" in signals:
            final += c.get("temporal_score_norm", 0.0) * weights.get("temporal_score", 0.0)
        if "temporal_pair_score" in signals:
            final += c.get("temporal_pair_score_norm", 0.0) * weights.get("temporal_pair_score", 0.0)
        c["final_score"] = round(final, 6)
        c["score"] = c["final_score"]

    # --- 7. Rank and return top_k_final ---
    candidates.sort(key=lambda x: x["final_score"], reverse=True)
    return candidates[:top_k_final]


if __name__ == "__main__":
    print("Clean Hybrid Retriever module loaded.")
    print("Weights:", WEIGHTS)
