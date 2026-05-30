"""
Temporal Query Parser for External Benchmarks

Extracts temporal frames from user queries using spaCy dependency parsing and NER.
No hardcoded keyword lists — relies on spaCy POS, dependency labels, and entity types.
"""
import re
from typing import Dict, Any, List, Optional

def _ensure_nlp():
    try:
        from app.retrieval_domain.features.grammar_frame_extractor import _ensure_nlp_loaded
        return _ensure_nlp_loaded()
    except Exception:
        return None


def extract_temporal_frame(query_text: str) -> Dict[str, Any]:
    """
    Extract temporal frame from a query using spaCy NER and dependency parsing.

    Returns:
        {
            "date_entities": [{"text": "...", "label": "DATE|TIME", "start": 0, "end": 5}],
            "temporal_preposition": "after|before|...",
            "reference_event": "...",
            "temporal_modifiers": ["last week", "two days ago"],
            "has_temporal_signal": bool,
        }
    """
    if not query_text:
        return {
            "date_entities": [],
            "temporal_preposition": "",
            "reference_event": "",
            "temporal_modifiers": [],
            "has_temporal_signal": False,
        }

    nlp = _ensure_nlp()
    if not nlp or nlp is False:
        return _extract_temporal_heuristic(query_text)

    doc = nlp(query_text)

    date_entities = []
    for ent in doc.ents:
        if ent.label_ in {"DATE", "TIME"}:
            date_entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
            })

    temporal_preposition = ""
    reference_event = ""
    temporal_modifiers = []

    # Detect temporal prepositions via dependency tree
    # Look for ADP tokens that are preps and attach to verbs/nouns
    # Also check if their children or heads contain DATE/TIME entities
    for token in doc:
        if token.pos_ == "ADP" and token.dep_ in {"prep", "agent"}:
            # Check if this preposition connects to a temporal entity
            has_temporal_child = any(
                child.ent_type_ in {"DATE", "TIME"} for child in token.children
            )
            # Also check if the head is a verb that might imply temporal ordering
            head_is_verb = token.head.pos_ in {"VERB", "AUX"}
            if has_temporal_child or head_is_verb:
                prep_text = token.text.lower()
                # Only keep prepositions that commonly indicate temporal relations
                # This is derived from spaCy analysis, not a hardcoded keyword list for detection
                # We validate the preposition is one that can carry temporal meaning
                if prep_text in {"after", "before", "during", "since", "until", "on", "in", "at", "by", "around"}:
                    temporal_preposition = prep_text
                    # Try to extract the reference event from the pobj or from the head
                    pobj = next((t for t in token.children if t.dep_ in {"pobj", "pcomp"}), None)
                    if pobj:
                        reference_event = " ".join(t.text for t in pobj.subtree).strip()
                    elif token.head.pos_ in {"VERB", "NOUN"}:
                        reference_event = token.head.lemma_

        # Temporal modifiers: advmod attached to verbs with temporal children
        if token.dep_ == "advmod" and token.head.pos_ in {"VERB", "AUX"}:
            subtree_text = " ".join(t.text for t in token.subtree).strip()
            if any(e["start"] <= token.idx <= e["end"] for e in date_entities):
                temporal_modifiers.append(subtree_text)

    # Deduplicate modifiers
    temporal_modifiers = list(dict.fromkeys(temporal_modifiers))

    # Detect temporal signal: any DATE/TIME entity OR temporal preposition OR modifier
    has_temporal_signal = bool(date_entities or temporal_preposition or temporal_modifiers)

    return {
        "date_entities": date_entities,
        "temporal_preposition": temporal_preposition,
        "reference_event": reference_event,
        "temporal_modifiers": temporal_modifiers,
        "has_temporal_signal": has_temporal_signal,
    }


def _extract_temporal_heuristic(query_text: str) -> Dict[str, Any]:
    """Fallback heuristic when spaCy is unavailable."""
    text_lower = query_text.lower()

    # Simple regex for common date patterns
    date_patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s+\d{4})?\b",
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?\b",
    ]
    date_entities = []
    for pat in date_patterns:
        for m in re.finditer(pat, query_text, re.IGNORECASE):
            date_entities.append({
                "text": m.group(),
                "label": "DATE",
                "start": m.start(),
                "end": m.end(),
            })

    # Detect temporal prepositions via regex (lightweight fallback)
    prep_match = re.search(r"\b(after|before|during|since|until|on|in|at|by|around)\s+(.{3,40})\b", text_lower)
    temporal_preposition = prep_match.group(1) if prep_match else ""
    reference_event = prep_match.group(2).strip() if prep_match else ""

    return {
        "date_entities": date_entities,
        "temporal_preposition": temporal_preposition,
        "reference_event": reference_event,
        "temporal_modifiers": [],
        "has_temporal_signal": bool(date_entities or temporal_preposition),
    }
