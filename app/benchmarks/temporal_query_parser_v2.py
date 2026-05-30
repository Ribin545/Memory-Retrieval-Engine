"""
Temporal Query Parser v2 — Multi-Target Event Extraction

Extends temporal_query_parser.py with multi-hop event target detection.
Uses spaCy dependency parsing (no hardcoded keywords) to find:
  - Coordinated events: "attended X and planted Y"
  - Comparatives: "Which happened first, A or B?"
  - Temporal preposition objects: "between [A] and [B]"
  - Conjoined noun phrases with event descriptions

Returns a TemporalFrame with event_targets[], temporal_relation, is_multi_event.
"""
import re
from typing import Dict, Any, List, Optional

from app.benchmarks.temporal_query_parser import extract_temporal_frame


def _ensure_nlp():
    try:
        from app.retrieval_domain.features.grammar_frame_extractor import _ensure_nlp_loaded
        return _ensure_nlp_loaded()
    except Exception:
        return None


def _extract_event_target_from_span(root_token) -> Dict[str, Any]:
    """
    Given a token that anchors an event description, extract:
      - event_verb (head VERB lemma)
      - event_object (dobj/pobj/dative head text, with compounds)
      - entities (PERSON/ORG/GPE in the subtree)
      - full_span (text of the subtree)
    """
    # Walk up to find the verb/noun head of this event description
    anchor = root_token

    # Strategy: if anchor is a noun that's part of a larger np, walk up
    if anchor.pos_ in {"NOUN", "PROPN"}:
        # Look for a verb that governs this noun
        # Either as direct object, or via appos/conj
        verb = None
        if anchor.head.pos_ in {"VERB", "AUX"}:
            verb = anchor.head
        else:
            # Try to find any verb ancestor
            ptr = anchor.head
            while ptr and ptr != ptr.head:
                if ptr.pos_ in {"VERB", "AUX"}:
                    verb = ptr
                    break
                ptr = ptr.head
        if verb:
            anchor = verb

    # Extract verb lemma
    event_verb = ""
    if anchor.pos_ in {"VERB", "AUX"}:
        event_verb = getattr(anchor, "lemma_", anchor.text.lower())
    elif anchor.head.pos_ in {"VERB", "AUX"}:
        event_verb = getattr(anchor.head, "lemma_", anchor.head.text.lower())

    # Extract object: direct object or prepositional object of anchor
    event_object = ""
    obj_tokens = []
    if anchor.pos_ in {"VERB", "AUX"}:
        # Look for direct object (dobj / obj)
        for child in anchor.children:
            if child.dep_ in {"dobj", "obj", "attr", "oprd"}:
                # Get compounds
                compounds = [t.text.lower() for t in child.children if t.dep_ == "compound" and t.i < child.i]
                obj_tokens = compounds + [child.text.lower()]
                event_object = "_".join(obj_tokens)
                break
        # If no direct object, look for dative (indirect object) — e.g. "give my neighbor"
        if not event_object:
            for child in anchor.children:
                if child.dep_ in {"dative", "iobj"}:
                    compounds = [t.text.lower() for t in child.children if t.dep_ == "compound" and t.i < child.i]
                    obj_tokens = compounds + [child.text.lower()]
                    event_object = "_".join(obj_tokens)
                    break
        # If still no object, look for prepositional object
        if not event_object:
            for child in anchor.children:
                if child.dep_ == "prep":
                    pobj = next((t for t in child.children if t.dep_ in {"pobj", "pcomp"}), None)
                    if pobj:
                        compounds = [t.text.lower() for t in pobj.children if t.dep_ == "compound" and t.i < pobj.i]
                        obj_tokens = compounds + [pobj.text.lower()]
                        event_object = "_".join(obj_tokens)
                        break
    elif anchor.pos_ in {"NOUN", "PROPN"}:
        # For noun anchors, the object is the noun itself (with compounds)
        compounds = [t.text.lower() for t in anchor.children if t.dep_ == "compound" and t.i < anchor.i]
        obj_tokens = compounds + [anchor.text.lower()]
        event_object = "_".join(obj_tokens)

    # Extract entities from the subtree
    subtree_tokens = list(anchor.subtree)
    # Create a mini-doc to get entities - but we can just collect named entities from the subtree
    entities = []
    for t in subtree_tokens:
        if t.ent_type_ in {"PERSON", "ORG", "GPE", "NORP", "PRODUCT", "WORK_OF_ART"}:
            ent_text = t.text.lower()
            if ent_text not in entities:
                entities.append(ent_text)

    # Full span text (capped)
    full_span = " ".join(t.text for t in subtree_tokens).strip()
    if len(full_span) > 120:
        full_span = full_span[:120] + "..."

    return {
        "event_verb": event_verb,
        "event_object": event_object,
        "entities": entities,
        "full_span": full_span,
        "anchor_token": anchor.text.lower(),
    }


def _target_quality(t: Dict[str, Any]) -> int:
    """Score a target's quality for ranking. Higher = more meaningful event."""
    q = 0
    # Base points for having verb and/or object
    if t.get("event_verb"):
        q += 1
    if t.get("event_object"):
        q += 1
    # Bonus for having entities
    if t.get("entities"):
        q += 1
    # Penalty for object being a generic temporal noun (not a content word)
    generic_temporal = {"day", "days", "week", "weeks", "month", "months", "year", "years", "time", "times", "event", "events"}
    if t.get("event_object") in generic_temporal:
        q -= 2
    # Penalty for verb being a structural/light verb
    light_verbs = {"be", "have", "do", "happen", "occur", "take", "pass", "make", "get", "go"}
    if t.get("event_verb") in light_verbs:
        q -= 1
    return q


def _find_event_targets_v1(doc) -> List[Dict[str, Any]]:
    """
    V1 parser: original multi-target event extraction (no relcl/acl strategy,
    no quality-based re-ranking).
    """
    targets: List[Dict[str, Any]] = []
    assigned_tokens = set()

    # --- Strategy 1: Coordinated verb phrases ---
    root = next((t for t in doc if t.dep_ == "ROOT"), None)
    if root and root.pos_ in {"VERB", "AUX"}:
        root_target = _extract_event_target_from_span(root)
        if root_target.get("event_verb") or root_target.get("event_object"):
            targets.append({**root_target, "target_id": "A", "strategy": "root_verb"})
            assigned_tokens.add(root.i)

        for child in root.children:
            if child.dep_ == "conj" and child.pos_ in {"VERB", "AUX"}:
                conj_target = _extract_event_target_from_span(child)
                if conj_target.get("event_verb") or conj_target.get("event_object"):
                    targets.append({**conj_target, "target_id": chr(66 + len(targets) - 1), "strategy": "conj_verb"})
                    assigned_tokens.add(child.i)

    # --- Strategy 2: Temporal preposition objects ---
    for token in doc:
        if token.pos_ != "ADP":
            continue
        pobjs = [c for c in token.children if c.dep_ in {"pobj", "pcomp"}]
        if len(pobjs) >= 2:
            for pobj in pobjs:
                if pobj.i in assigned_tokens:
                    continue
                pt = _extract_event_target_from_span(pobj)
                if pt.get("event_verb") or pt.get("event_object"):
                    tid = chr(65 + len(targets))
                    targets.append({**pt, "target_id": tid, "strategy": "prep_pobj"})
                    assigned_tokens.add(pobj.i)
        elif len(pobjs) == 1:
            pobj = pobjs[0]
            conj_siblings = [c for c in pobj.children if c.dep_ == "conj"]
            for cs in conj_siblings:
                if cs.i in assigned_tokens:
                    continue
                pt = _extract_event_target_from_span(cs)
                if pt.get("event_verb") or pt.get("event_object"):
                    tid = chr(65 + len(targets))
                    targets.append({**pt, "target_id": tid, "strategy": "prep_pobj_conj"})
                    assigned_tokens.add(cs.i)

    # --- Strategy 3: Comparative structures with appos/conj ---
    for token in doc:
        if token.pos_ in {"NOUN", "PROPN"}:
            for child in token.children:
                if child.dep_ == "appos" and child.pos_ in {"NOUN", "PROPN"}:
                    if child.i in assigned_tokens:
                        continue
                    pt = _extract_event_target_from_span(child)
                    if pt.get("event_verb") or pt.get("event_object"):
                        tid = chr(65 + len(targets))
                        targets.append({**pt, "target_id": tid, "strategy": "appos"})
                        assigned_tokens.add(child.i)

    # --- Strategy 4: Conjoined noun phrases ---
    for token in doc:
        if token.dep_ == "conj" and token.pos_ in {"NOUN", "PROPN"}:
            if token.i in assigned_tokens:
                continue
            pt = _extract_event_target_from_span(token)
            head_verb = token.head.pos_ in {"VERB", "AUX"} if token.head else False
            if (pt.get("event_verb") or pt.get("event_object")) and (head_verb or pt.get("event_object")):
                tid = chr(65 + len(targets))
                targets.append({**pt, "target_id": tid, "strategy": "conj_noun"})
                assigned_tokens.add(token.i)

    return targets


def _find_event_targets_v2(doc) -> List[Dict[str, Any]]:
    """
    V2 parser: adds relcl/acl embedded-verb extraction and quality-based
    target re-ranking.
    """
    targets: List[Dict[str, Any]] = []
    assigned_tokens = set()

    # --- Strategy 0: Verbs inside relative / adnominal clauses ---
    for token in doc:
        if token.pos_ in {"NOUN", "PROPN"}:
            for child in token.children:
                if child.dep_ in {"relcl", "acl"} and child.pos_ in {"VERB", "AUX"}:
                    has_subj = any(c.dep_ in {"nsubj", "nsubjpass", "expl"} for c in child.children)
                    if not has_subj and child.dep_ == "acl":
                        has_subj = True
                    if not has_subj:
                        continue
                    pt = _extract_event_target_from_span(child)
                    if pt.get("event_verb") or pt.get("event_object"):
                        if child.i not in assigned_tokens:
                            tid = chr(65 + len(targets))
                            targets.append({**pt, "target_id": tid, "strategy": "relcl_verb"})
                            assigned_tokens.add(child.i)
                            assigned_tokens.add(token.i)
                        for conj_child in child.children:
                            if conj_child.dep_ == "conj" and conj_child.pos_ in {"VERB", "AUX"}:
                                if conj_child.i in assigned_tokens:
                                    continue
                                cpt = _extract_event_target_from_span(conj_child)
                                if cpt.get("event_verb") or cpt.get("event_object"):
                                    tid2 = chr(65 + len(targets))
                                    targets.append({**cpt, "target_id": tid2, "strategy": "relcl_conj_verb"})
                                    assigned_tokens.add(conj_child.i)

    # --- Strategy 1: Coordinated verb phrases ---
    root = next((t for t in doc if t.dep_ == "ROOT"), None)
    if root and root.pos_ in {"VERB", "AUX"}:
        root_target = _extract_event_target_from_span(root)
        if root_target.get("event_verb") or root_target.get("event_object"):
            targets.append({**root_target, "target_id": "A", "strategy": "root_verb"})
            assigned_tokens.add(root.i)

        for child in root.children:
            if child.dep_ == "conj" and child.pos_ in {"VERB", "AUX"}:
                conj_target = _extract_event_target_from_span(child)
                if conj_target.get("event_verb") or conj_target.get("event_object"):
                    targets.append({**conj_target, "target_id": chr(66 + len(targets) - 1), "strategy": "conj_verb"})
                    assigned_tokens.add(child.i)

    # --- Strategy 2: Temporal preposition objects ---
    for token in doc:
        if token.pos_ != "ADP":
            continue
        pobjs = [c for c in token.children if c.dep_ in {"pobj", "pcomp"}]
        if len(pobjs) >= 2:
            for pobj in pobjs:
                if pobj.i in assigned_tokens:
                    continue
                pt = _extract_event_target_from_span(pobj)
                if pt.get("event_verb") or pt.get("event_object"):
                    tid = chr(65 + len(targets))
                    targets.append({**pt, "target_id": tid, "strategy": "prep_pobj"})
                    assigned_tokens.add(pobj.i)
        elif len(pobjs) == 1:
            pobj = pobjs[0]
            conj_siblings = [c for c in pobj.children if c.dep_ == "conj"]
            for cs in conj_siblings:
                if cs.i in assigned_tokens:
                    continue
                pt = _extract_event_target_from_span(cs)
                if pt.get("event_verb") or pt.get("event_object"):
                    tid = chr(65 + len(targets))
                    targets.append({**pt, "target_id": tid, "strategy": "prep_pobj_conj"})
                    assigned_tokens.add(cs.i)

    # --- Strategy 3: Comparative structures with appos/conj ---
    for token in doc:
        if token.pos_ in {"NOUN", "PROPN"}:
            for child in token.children:
                if child.dep_ == "appos" and child.pos_ in {"NOUN", "PROPN"}:
                    if child.i in assigned_tokens:
                        continue
                    pt = _extract_event_target_from_span(child)
                    if pt.get("event_verb") or pt.get("event_object"):
                        tid = chr(65 + len(targets))
                        targets.append({**pt, "target_id": tid, "strategy": "appos"})
                        assigned_tokens.add(child.i)

    # --- Strategy 4: Conjoined noun phrases ---
    for token in doc:
        if token.dep_ == "conj" and token.pos_ in {"NOUN", "PROPN"}:
            if token.i in assigned_tokens:
                continue
            pt = _extract_event_target_from_span(token)
            head_verb = token.head.pos_ in {"VERB", "AUX"} if token.head else False
            if (pt.get("event_verb") or pt.get("event_object")) and (head_verb or pt.get("event_object")):
                tid = chr(65 + len(targets))
                targets.append({**pt, "target_id": tid, "strategy": "conj_noun"})
                assigned_tokens.add(token.i)

    # Post-process: sort targets by quality
    if len(targets) >= 2:
        targets.sort(key=_target_quality, reverse=True)
        for i, t in enumerate(targets):
            t["target_id"] = chr(65 + i)

    return targets


def _detect_temporal_relation(doc) -> str:
    """
    Detect the temporal/comparative relation in the query.
    Uses spaCy tokens, not hardcoded regex on raw text.
    """
    for token in doc:
        # Prepositions that imply comparison/ordering
        if token.pos_ == "ADP" and token.dep_ in {"prep", "mark"}:
            if token.text.lower() in {"between", "from", "to"}:
                return token.text.lower()
        # Adverbs/adjectives indicating ordering
        if token.text.lower() in {"first", "last", "recently", "latest", "earliest"}:
            return token.text.lower()
        # Verbs that imply duration/comparison
        if token.pos_ == "VERB" and token.lemma_ in {"pass", "take", "happen", "occur", "compare"}:
            return token.lemma_
    return ""


def extract_temporal_frame_v2(query_text: str, parser_version: str = "v2") -> Dict[str, Any]:
    """
    Extract temporal frame with multi-target event detection.

    Args:
        query_text: The query string.
        parser_version: "v1" (original strategies 1-4) or "v2" (adds relcl/acl strategy 0 + quality re-ranking).

    Returns:
        {
            # -- base temporal fields (from v1) --
            "date_entities": [...],
            "temporal_preposition": "",
            "reference_event": "",
            "temporal_modifiers": [...],
            "has_temporal_signal": bool,

            # -- v2 multi-hop fields --
            "event_targets": [
                {
                    "target_id": "A",
                    "event_verb": "attended",
                    "event_object": "gardening_workshop",
                    "entities": [...],
                    "full_span": "...",
                    "date_constraint": "",
                    "strategy": "root_verb",
                }
            ],
            "temporal_relation": "between",
            "is_multi_event": bool,
        }
    """
    # Get base temporal frame from v1
    base = extract_temporal_frame(query_text)

    nlp = _ensure_nlp()
    if not nlp or nlp is False:
        return {
            **base,
            "event_targets": [],
            "temporal_relation": "",
            "is_multi_event": False,
        }

    doc = nlp(query_text)

    # Dispatch to requested parser version
    if parser_version == "v1":
        event_targets = _find_event_targets_v1(doc)
    else:
        event_targets = _find_event_targets_v2(doc)

    temporal_relation = _detect_temporal_relation(doc)

    date_entities = base.get("date_entities", [])
    for target in event_targets:
        target["date_constraint"] = ""
        if len(date_entities) == 1 and target["target_id"] == "A":
            target["date_constraint"] = date_entities[0]["text"]

    is_multi_event = len(event_targets) >= 2

    return {
        **base,
        "event_targets": event_targets,
        "temporal_relation": temporal_relation,
        "is_multi_event": is_multi_event,
    }
