"""
Temporal Multi-Hop Scorer for External Benchmarks

Computes temporal_pair_score for candidate memory pairs.
Matches query event targets to candidate events, scores pairs using
event similarity + graph link bonus.

Gating: temporal_pair_score only activates when query.is_multi_event=True
and at least one candidate achieves pair_score > 0.5.
"""
from typing import Dict, Any, List, Optional, Set, Tuple


def _token_overlap(a: str, b: str) -> float:
    """Compute word overlap ratio between two strings."""
    if not a or not b:
        return 0.0
    words_a = set(a.lower().replace("_", " ").split())
    words_b = set(b.lower().replace("_", " ").split())
    if not words_a or not words_b:
        return 0.0
    inter = words_a & words_b
    return len(inter) / max(len(words_a), len(words_b))


def _match_event_to_target(
    event_card: Dict[str, Any],
    target: Dict[str, Any],
) -> float:
    """
    Score how well a single event card matches an event target.
    Returns 0..1 score.
    """
    # Verb match
    verb_score = 0.0
    evt_verb = event_card.get("event_verb", "")
    tgt_verb = target.get("event_verb", "")
    if evt_verb and tgt_verb:
        if evt_verb == tgt_verb:
            verb_score = 1.0
        else:
            verb_score = _token_overlap(evt_verb, tgt_verb) * 0.3
    elif evt_verb or tgt_verb:
        verb_score = 0.3  # partial credit if only one side has verb

    # Object match
    obj_score = 0.0
    evt_obj = event_card.get("event_object", "")
    tgt_obj = target.get("event_object", "")
    if evt_obj and tgt_obj:
        if evt_obj == tgt_obj:
            obj_score = 1.0
        else:
            obj_score = _token_overlap(evt_obj, tgt_obj)
    elif evt_obj or tgt_obj:
        obj_score = 0.2

    # Entity overlap
    evt_ents = set(event_card.get("entities", []))
    tgt_ents = set(target.get("entities", []))
    entity_score = 0.0
    if evt_ents and tgt_ents:
        inter = evt_ents & tgt_ents
        if inter:
            entity_score = len(inter) / max(len(evt_ents), len(tgt_ents))
    elif evt_ents or tgt_ents:
        entity_score = 0.1

    # Sentence overlap (full span text similarity via content words)
    span_score = 0.0
    evt_span = event_card.get("event_sentence", "").lower()
    tgt_span = target.get("full_span", "").lower()
    if evt_span and tgt_span:
        span_score = _token_overlap(evt_span, tgt_span)

    # Date constraint bonus
    date_bonus = 0.0
    date_constraint = target.get("date_constraint", "")
    if date_constraint:
        # Check if event's date_text or normalized_date matches constraint
        evt_date = event_card.get("date_text", "")
        evt_norm = event_card.get("normalized_date") or ""
        if evt_date and (evt_date.lower() in date_constraint.lower() or date_constraint.lower() in evt_date.lower()):
            date_bonus = 0.2
        elif evt_norm and (evt_norm.lower() in date_constraint.lower() or date_constraint.lower() in evt_norm.lower()):
            date_bonus = 0.2

    # Combine scores with weights
    combined = (
        verb_score * 0.30 +
        obj_score * 0.30 +
        entity_score * 0.15 +
        span_score * 0.15 +
        date_bonus
    )
    return min(1.0, combined)


def _build_link_index(links: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Index graph links by event_a for fast lookup."""
    index: Dict[str, List[Dict[str, Any]]] = {}
    for link in links:
        eid_a = link["event_a"]
        eid_b = link["event_b"]
        if eid_a not in index:
            index[eid_a] = []
        if eid_b not in index:
            index[eid_b] = []
        index[eid_a].append(link)
        # Add reverse link
        reverse_link = dict(link)
        reverse_link["event_a"] = eid_b
        reverse_link["event_b"] = eid_a
        # Adjust relation for reverse
        if reverse_link.get("relation") == "before":
            reverse_link["relation"] = "after"
        elif reverse_link.get("relation") == "after":
            reverse_link["relation"] = "before"
        index[eid_b].append(reverse_link)
    return index


def _compute_pair_graph_bonus(
    event_id_a: str,
    event_id_b: str,
    link_index: Dict[str, List[Dict[str, Any]]],
    temporal_relation: str,
) -> float:
    """
    Compute graph link bonus for a pair of events.
    Returns bonus in [0, 0.5].
    """
    bonus = 0.0
    links_a = link_index.get(event_id_a, [])
    for link in links_a:
        if link["event_b"] == event_id_b:
            lt = link["link_type"]
            if lt == "same_entity":
                bonus = max(bonus, 0.30)
            elif lt == "same_object":
                bonus = max(bonus, 0.20)
            elif lt == "same_verb":
                bonus = max(bonus, 0.15)
            elif lt == "same_topic":
                bonus = max(bonus, 0.15)
            elif lt == "date_ordering":
                relation = link.get("relation", "")
                # Bonus higher if ordering matches query relation
                if temporal_relation and relation in temporal_relation:
                    bonus = max(bonus, 0.25)
                else:
                    bonus = max(bonus, 0.15)
            elif lt == "same_session":
                bonus = max(bonus, 0.10)
    return min(bonus, 0.5)


def compute_multihop_scores(
    candidates: List[Dict[str, Any]],
    query_frame: Dict[str, Any],
    event_graph: Dict[str, Any],
    return_diagnostics: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """
    Compute multi-hop temporal scores for each candidate.

    Args:
        candidates: List of candidate dicts from dense retrieval.
        query_frame: Output from extract_temporal_frame_v2.
        event_graph: Dict with "event_cards", "events_by_memory", "links".
        return_diagnostics: If True, include diagnostic fields in results.

    Returns:
        Dict mapping memory_id -> {
            "temporal_event_score": float,
            "temporal_pair_score": float,
            "supporting_event_ids": list,
            "supporting_memory_ids": list,
            "best_target_matches": {target_id: score},
            # Optional diagnostics:
            "_diag_events_found": int,
            "_diag_pair_scores": list,
            "_diag_gate_reason": str,
        }
    """
    event_cards = event_graph.get("event_cards", {})
    events_by_memory = event_graph.get("events_by_memory", {})
    links = event_graph.get("links", [])
    # Use pre-built link_index if available, else build once
    link_index = event_graph.get("link_index")
    if link_index is None:
        link_index = _build_link_index(links)

    event_targets = query_frame.get("event_targets", [])
    is_multi_event = query_frame.get("is_multi_event", False)
    temporal_relation = query_frame.get("temporal_relation", "")

    # If not multi-event, return empty scores (no-op)
    if not is_multi_event or len(event_targets) < 2:
        reason = f"Gate closed: is_multi_event={is_multi_event}, event_targets={len(event_targets)}"
        return {c["memory_id"]: {
            "temporal_event_score": 0.0,
            "temporal_pair_score": 0.0,
            "supporting_event_ids": [],
            "supporting_memory_ids": [],
            "best_target_matches": {},
            "_diag_gate_reason": reason,
        } for c in candidates}

    # --- Step 1: Match each candidate's events to each target ---
    # Use original_memory_id for graph lookups if available
    candidate_event_matches: Dict[str, Dict[str, float]] = {}
    candidate_best_events: Dict[str, Dict[str, float]] = {}

    total_events_found = 0
    for cand in candidates:
        mem_id = cand.get("memory_id", "")
        # Use original_memory_id for graph lookup (graph uses raw IDs, not prefixed)
        lookup_id = cand.get("original_memory_id", mem_id)
        cand_events = events_by_memory.get(lookup_id, [])
        total_events_found += len(cand_events)
        candidate_event_matches[mem_id] = {}
        candidate_best_events[mem_id] = {}

        if not cand_events:
            for tgt in event_targets:
                candidate_event_matches[mem_id][tgt["target_id"]] = 0.0
                candidate_best_events[mem_id][tgt["target_id"]] = ""
            continue

        for target in event_targets:
            best_score = 0.0
            best_event_id = ""
            for eid in cand_events:
                card = event_cards.get(eid)
                if not card:
                    continue
                score = _match_event_to_target(card, target)
                if score > best_score:
                    best_score = score
                    best_event_id = eid
            candidate_event_matches[mem_id][target["target_id"]] = best_score
            candidate_best_events[mem_id][target["target_id"]] = best_event_id

    # --- Step 2: Compute pair scores ---
    # We assume targets are ordered: target 0 = A, target 1 = B, etc.
    # For simplicity, pair target A (first target) with target B (second target)
    # If more than 2 targets, we focus on the first two.
    target_ids = [t["target_id"] for t in event_targets]
    if len(target_ids) >= 2:
        primary_target = target_ids[0]
        secondary_target = target_ids[1]
    else:
        primary_target = target_ids[0] if target_ids else "A"
        secondary_target = target_ids[1] if len(target_ids) > 1 else "B"

    # Pre-compute pair scores: for each ordered pair (A_mem, B_mem)
    pair_scores: Dict[Tuple[str, str], float] = {}
    pair_support: Dict[Tuple[str, str], Tuple[List[str], List[str]]] = {}

    mem_ids = [c["memory_id"] for c in candidates]
    n = len(mem_ids)

    for i in range(n):
        mem_a = mem_ids[i]
        match_a = candidate_event_matches[mem_a].get(primary_target, 0.0)
        best_evt_a = candidate_best_events[mem_a].get(primary_target, "")

        for j in range(n):
            if i == j:
                continue
            mem_b = mem_ids[j]
            match_b = candidate_event_matches[mem_b].get(secondary_target, 0.0)
            best_evt_b = candidate_best_events[mem_b].get(secondary_target, "")

            base_pair = (match_a + match_b) / 2.0

            # Graph link bonus
            graph_bonus = 0.0
            if best_evt_a and best_evt_b:
                graph_bonus = _compute_pair_graph_bonus(
                    best_evt_a, best_evt_b, link_index, temporal_relation
                )

            pair_score = min(1.0, base_pair + graph_bonus)
            pair_scores[(mem_a, mem_b)] = pair_score
            pair_support[(mem_a, mem_b)] = ([best_evt_a, best_evt_b], [mem_b])

    # --- Step 3: Per-candidate aggregation ---
    results: Dict[str, Dict[str, Any]] = {}
    # Track all pair scores for diagnostics
    all_pair_scores_list = []
    for (ma, mb), ps in pair_scores.items():
        all_pair_scores_list.append({"mem_a": ma, "mem_b": mb, "pair_score": round(ps, 4)})
    all_pair_scores_list.sort(key=lambda x: x["pair_score"], reverse=True)
    top_pairs = all_pair_scores_list[:5]

    gate_reason = f"Gate evaluated: is_multi_event={is_multi_event}, targets={len(event_targets)}, events_found={total_events_found}, candidate_count={len(candidates)}, top_pair_score={top_pairs[0]['pair_score'] if top_pairs else 0}"

    for cand in candidates:
        mem_id = cand["memory_id"]

        # temporal_event_score: best single-target match across all targets
        all_matches = list(candidate_event_matches.get(mem_id, {}).values())
        temporal_event_score = max(all_matches) if all_matches else 0.0

        # temporal_pair_score: best pair score where this candidate participates
        best_pair_score = 0.0
        best_supporting_events: List[str] = []
        best_supporting_mems: List[str] = []

        # As primary participant
        for other_mem in mem_ids:
            if other_mem == mem_id:
                continue
            ps = pair_scores.get((mem_id, other_mem), 0.0)
            if ps > best_pair_score:
                best_pair_score = ps
                sup = pair_support.get((mem_id, other_mem), ([], []))
                best_supporting_events = list(filter(None, sup[0]))
                best_supporting_mems = list(filter(None, sup[1]))

        # As secondary participant
        for other_mem in mem_ids:
            if other_mem == mem_id:
                continue
            ps = pair_scores.get((other_mem, mem_id), 0.0)
            if ps > best_pair_score:
                best_pair_score = ps
                sup = pair_support.get((other_mem, mem_id), ([], []))
                best_supporting_events = list(filter(None, sup[0]))
                best_supporting_mems = list(filter(None, sup[1]))

        res = {
            "temporal_event_score": round(temporal_event_score, 6),
            "temporal_pair_score": round(best_pair_score, 6),
            "supporting_event_ids": best_supporting_events,
            "supporting_memory_ids": best_supporting_mems,
            "best_target_matches": candidate_event_matches.get(mem_id, {}),
            "_diag_gate_reason": gate_reason,
        }
        if return_diagnostics:
            res["_diag_events_found"] = total_events_found
            res["_diag_pair_scores"] = top_pairs
            res["_diag_event_targets"] = [{"target_id": t.get("target_id"), "verb": t.get("event_verb"), "obj": t.get("event_object")} for t in event_targets]
        results[mem_id] = res

    return results
