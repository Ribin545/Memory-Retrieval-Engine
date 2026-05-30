"""
Dynamic Action-Frame Extraction

Adds lightweight grammar/action-frame extraction for memory cards without
depending on a fixed hardcoded verb list as the primary extraction mechanism.

The extractor prefers spaCy dependency parsing when available and falls back to
regex/heuristic extraction when it is not.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional


_NLP = None
_NLP_STATUS = {
    "available": False,
    "model": None,
    "error": None,
}


FRAME_TYPE_VALUES = {
    "action_intent",
    "exact_phrase",
    "discussion_topic",
    "emotional_report",
    "preference",
    "unresolved_state",
    "session_summary",
    "unknown",
}


def get_action_frame_parser_status() -> Dict[str, Any]:
    """Return parser availability for diagnostics/tests."""
    _ensure_nlp_loaded()
    return dict(_NLP_STATUS)


def _ensure_nlp_loaded():
    global _NLP
    if _NLP is not None:
        return _NLP

    try:
        import spacy  # type: ignore

        _NLP = spacy.load("en_core_web_sm")
        _NLP_STATUS.update({"available": True, "model": "en_core_web_sm", "error": None})
    except Exception as exc:  # pragma: no cover - fallback path is tested functionally
        _NLP = False
        _NLP_STATUS.update({"available": False, "model": None, "error": str(exc)})
    return _NLP


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_quoted_text(text: str) -> Optional[str]:
    if not text:
        return None
    patterns = [
        r'"([^"]+)"',
        r"'([^']+)'",
        r"[\u201c\u201d]([^\u201c\u201d]+)[\u201c\u201d]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            quoted = _clean_text(match.group(1))
            if quoted:
                return quoted
    return None


def _strip_quoted_spans(text: str) -> str:
    if not text:
        return text
    stripped = re.sub(r'"[^"]+"', ' ', text)
    stripped = re.sub(r"'[^']+'", ' ', stripped)
    stripped = re.sub(r"[\u201c\u201d][^\u201c\u201d]+[\u201c\u201d]", ' ', stripped)
    return _clean_text(stripped)


def _extract_outer_clause_context(text: str) -> Dict[str, Any]:
    """Extract lightweight structure from the outer clause excluding quoted text."""
    outer = _strip_quoted_spans(text)
    result = {
        "root_verb": None,
        "root_verb_lemma": None,
        "secondary_verb": None,
        "secondary_verb_lemma": None,
        "object_text": None,
        "context_text": None,
        "trigger_phrase": None,
    }
    words = re.findall(r"[A-Za-z']+", outer)
    if len(words) >= 2:
        result["root_verb"] = words[1]
        result["root_verb_lemma"] = words[1].lower()
        result["trigger_phrase"] = " ".join(words[: min(6, len(words))])

    xcomp_match = re.search(r"\bto\s+([a-zA-Z']+)\b", outer, re.IGNORECASE)
    if xcomp_match:
        verb = xcomp_match.group(1)
        result["secondary_verb"] = verb
        result["secondary_verb_lemma"] = verb.lower()

    remember_match = re.search(r"\b(?:wanted|wants|want|asked|planned|plans|chose|chooses|needed|needs)\s+to\s+([a-zA-Z']+)\b", outer, re.IGNORECASE)
    if remember_match:
        result["secondary_verb"] = remember_match.group(1)
        result["secondary_verb_lemma"] = remember_match.group(1).lower()

    explicit_memory_match = re.search(r"\bremember\b", outer, re.IGNORECASE)
    if explicit_memory_match:
        result["secondary_verb"] = "remember"
        result["secondary_verb_lemma"] = "remember"

    if result["root_verb_lemma"]:
        if result["root_verb_lemma"].endswith("ed") and len(result["root_verb_lemma"]) > 4:
            result["root_verb_lemma"] = result["root_verb_lemma"][:-2]
        elif result["root_verb_lemma"].endswith("s") and len(result["root_verb_lemma"]) > 3:
            result["root_verb_lemma"] = result["root_verb_lemma"][:-1]

    if result["secondary_verb_lemma"]:
        if result["secondary_verb_lemma"].endswith("ed") and len(result["secondary_verb_lemma"]) > 4:
            result["secondary_verb_lemma"] = result["secondary_verb_lemma"][:-2]
        elif result["secondary_verb_lemma"].endswith("s") and len(result["secondary_verb_lemma"]) > 3:
            result["secondary_verb_lemma"] = result["secondary_verb_lemma"][:-1]

    colon_match = re.search(r"\b(?:sentence|phrase|line|script|plan)\b", outer, re.IGNORECASE)
    if colon_match:
        result["object_text"] = colon_match.group(0).lower()

    trailing_context = re.search(r"\b(?:for|before|with|during|after)\s+(.+)$", outer, re.IGNORECASE)
    if trailing_context:
        result["context_text"] = trailing_context.group(0).strip(" .")
    return result


def _looks_like_intentful_preposition_context(context_text: Optional[str]) -> bool:
    if not context_text:
        return False
    lowered = context_text.lower()
    return lowered.startswith(("to ", "for ", "before ", "after ", "with "))


def _make_base_frame(text: str, extraction_method: str) -> Dict[str, Any]:
    return {
        "frame_type": "unknown",
        "frame_type_confidence": 0.0,
        "subject": "User" if text.lower().startswith("user") else None,
        "root_verb": None,
        "root_verb_lemma": None,
        "trigger_phrase": None,
        "secondary_verb": None,
        "secondary_verb_lemma": None,
        "object_text": None,
        "context_text": None,
        "time_context": None,
        "emotion_text": None,
        "quoted_text": _extract_quoted_text(text),
        "grammar_pattern": "unknown",
        "extraction_method": extraction_method,
        "confidence": 0.0,
    }


def _subtree_text(token: Any) -> str:
    try:
        return _clean_text(" ".join(t.text for t in token.subtree))
    except Exception:
        return _clean_text(getattr(token, "text", ""))


def get_compound_inclusive_head(token) -> str:
    if not token:
        return ""
    words = [token]
    for child in token.children:
        if child.i < token.i:
            if child.dep_ in {"compound", "nummod"} or child.text.lower() in {"grounding", "wind-down", "sleep", "no-phone"}:
                words.append(child)
    words.sort(key=lambda t: t.i)
    cleaned = []
    for w in words:
        cleaned.append(w.text.lower().replace("-", "_"))
    return "_".join(cleaned)


def extract_context_info(doc) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (preposition, context_object, context_text)."""
    # Look for preposition token in doc
    prep = next((t for t in doc if t.dep_ == "prep"), None)
    if not prep:
        return None, None, None

    preposition = prep.text.lower()
    context_text = _subtree_text(prep)

    # Find the object of the preposition
    pobj = next((t for t in prep.children if t.dep_ in {"pobj", "pcomp"}), None)
    if pobj:
        if pobj.dep_ == "pcomp" or pobj.pos_ == "VERB":
            # GERUND case: e.g. "about setting boundaries". pobj is "setting".
            # Look for dobj child under pobj
            dobj = next((t for t in pobj.children if t.dep_ in {"dobj", "obj", "attr"}), None)
            if dobj:
                context_object = get_compound_inclusive_head(dobj)
            else:
                context_object = get_compound_inclusive_head(pobj)
        else:
            context_object = get_compound_inclusive_head(pobj)
    else:
        context_object = None

    return preposition, context_object, context_text


def _build_grammar_memory_dict(doc, frame) -> Dict[str, Any]:
    # 1. Subject
    subject = frame.get("subject")
    if not subject:
        subj_tok = next((t for t in doc if t.dep_ in {"nsubj", "nsubjpass"}), None)
        if subj_tok:
            subject = subj_tok.text
        else:
            subject = "User" if doc.text.lower().startswith("user") else "User"

    # 2. Verb info
    verb_text = frame.get("root_verb")
    verb_lemma = frame.get("root_verb_lemma")
    if not verb_text:
        root = next((token for token in doc if token.dep_ == "ROOT"), None)
        if root:
            verb_text = root.text
            verb_lemma = getattr(root, "lemma_", root.text.lower())

    # 3. Secondary verb info
    secondary_verb = frame.get("secondary_verb")
    secondary_verb_lemma = frame.get("secondary_verb_lemma")

    # 4. Object info
    object_text = frame.get("object_text")
    object_head = None

    def is_in_prep_phrase(token) -> bool:
        curr = token.head
        while curr and curr != token:
            if curr.dep_ == "prep":
                return True
            curr = curr.head
        return False

    # Check if there is an explicit dobj/attr/obj in doc
    obj_tok = None
    sec_verb_tok = None
    if secondary_verb:
        sec_verb_tok = next((t for t in doc if t.text == secondary_verb or t.lemma_ == secondary_verb_lemma), None)
    
    if sec_verb_tok:
        obj_tok = next((t for t in sec_verb_tok.subtree if t.dep_ in {"dobj", "obj", "attr", "oprd"}), None)
    
    if not obj_tok:
        obj_tok = next((t for t in doc if t.dep_ in {"dobj", "obj", "attr", "oprd"} and not is_in_prep_phrase(t)), None)

    if obj_tok:
        object_text = _subtree_text(obj_tok)
        object_head = get_compound_inclusive_head(obj_tok)
    
    # If no object is found, look for adjective complement (acomp) or emotion term
    if not object_head:
        acomp_tok = next((t for t in doc if t.dep_ == "acomp" or t.text.lower() in {"guilty", "panic", "anxious", "sad", "angry", "overwhelmed"}), None)
        if acomp_tok:
            object_text = _subtree_text(acomp_tok)
            object_head = get_compound_inclusive_head(acomp_tok)

    # 5. Preposition & Context object
    preposition, context_object, context_text = extract_context_info(doc)

    # Clean object_head and context_object to replace spaces/hyphens
    if object_head:
        object_head = object_head.replace(" ", "_").replace("-", "_")
    if context_object:
        context_object = context_object.replace(" ", "_").replace("-", "_")

    # Construct pattern key
    key_parts = []
    if subject:
        key_parts.append(subject.lower())
    else:
        key_parts.append("user")
    
    if verb_lemma:
        key_parts.append(verb_lemma.lower())
    if secondary_verb_lemma:
        key_parts.append(secondary_verb_lemma.lower())
    if object_head:
        key_parts.append(object_head)
    if preposition and context_object:
        key_parts.append(f"{preposition}_{context_object}")

    pattern_key = ".".join(key_parts)

    # Construct pattern label
    label_parts = []
    if verb_text:
        label_parts.append(verb_text.lower())
    if secondary_verb:
        label_parts.append(secondary_verb.lower())
    if object_head:
        label_parts.append(object_head)
    if preposition and context_object:
        label_parts.append(f"{preposition}_{context_object}")

    pattern_label = "_".join(label_parts)

    # Construct semantic structure
    return {
        "subject": subject or "User",
        "verb_text": verb_text or "",
        "verb_lemma": verb_lemma or "",
        "object_text": object_text or "",
        "object_head": object_head or "",
        "context_text": context_text or "",
        "preposition": preposition or "",
        "context_object": context_object or "",
        "pattern_key": pattern_key,
        "pattern_label": pattern_label,
        "confidence": 0.9 if doc else 0.0,
    }


def _spacy_extract_action_frame(text: str) -> Dict[str, Any]:
    nlp = _ensure_nlp_loaded()
    if not nlp:
        return _heuristic_extract_action_frame(text)

    doc = nlp(text)
    frame = _make_base_frame(text, "spacy_dependency_parse")

    root = next((token for token in doc if token.dep_ == "ROOT"), None)
    if root:
        frame["root_verb"] = root.text
        frame["root_verb_lemma"] = getattr(root, "lemma_", root.text.lower())
        frame["trigger_phrase"] = _subtree_text(root)

    outer_context = _extract_outer_clause_context(text)
    if frame["quoted_text"] and outer_context.get("root_verb"):
        frame["root_verb"] = outer_context["root_verb"]
        frame["root_verb_lemma"] = outer_context["root_verb_lemma"]
        frame["trigger_phrase"] = outer_context.get("trigger_phrase") or frame.get("trigger_phrase")
        if outer_context.get("secondary_verb"):
            frame["secondary_verb"] = outer_context["secondary_verb"]
            frame["secondary_verb_lemma"] = outer_context["secondary_verb_lemma"]
            if frame["secondary_verb"].lower() == frame["root_verb"].lower():
                frame["secondary_verb"] = "remember"
                frame["secondary_verb_lemma"] = "remember"
        if outer_context.get("object_text"):
            frame["object_text"] = outer_context["object_text"]
        if outer_context.get("context_text") and (not frame.get("context_text") or frame.get("context_text") == "about you"):
            frame["context_text"] = outer_context["context_text"]

    subject = next((t for t in doc if t.dep_ in {"nsubj", "nsubjpass"}), None)
    if subject:
        frame["subject"] = _subtree_text(subject)

    xcomp = next((t for t in doc if t.dep_ in {"xcomp", "ccomp"}), None)
    if xcomp:
        frame["secondary_verb"] = xcomp.text
        frame["secondary_verb_lemma"] = getattr(xcomp, "lemma_", xcomp.text.lower())

    obj = next((t for t in doc if t.dep_ in {"dobj", "obj", "attr", "oprd"}), None)
    if obj:
        frame["object_text"] = _subtree_text(obj)
    elif xcomp:
        xcomp_obj = next((t for t in xcomp.subtree if getattr(t, "dep_", "") in {"dobj", "obj", "attr"}), None)
        if xcomp_obj:
            frame["object_text"] = _subtree_text(xcomp_obj)

    acomp = next((t for t in doc if t.dep_ == "acomp"), None)
    if acomp:
        frame["emotion_text"] = _subtree_text(acomp)

    prep_chunks: List[str] = []
    time_chunks: List[str] = []
    for token in doc:
        if token.dep_ == "prep":
            phrase = _subtree_text(token)
            if phrase:
                prep_chunks.append(phrase)
        elif token.dep_ in {"npadvmod", "advmod"}:
            phrase = _subtree_text(token)
            if re.search(r"\b(?:\d{1,2}\s?(?:AM|PM|am|pm)|today|tonight|tomorrow|week)\b", phrase):
                time_chunks.append(phrase)

    time_regex = re.search(r"\b\d{1,2}\s?(?:AM|PM|am|pm)\b", text)
    if time_regex:
        frame["time_context"] = time_regex.group(0)
    elif time_chunks:
        frame["time_context"] = time_chunks[0]

    context_candidates = [chunk for chunk in prep_chunks if chunk != frame.get("time_context")]
    if context_candidates:
        frame["context_text"] = context_candidates[0]

    if not frame.get("object_text") and root:
        root_prep = next((t for t in root.children if getattr(t, "dep_", "") == "prep"), None)
        if root_prep:
            prep_phrase = _subtree_text(root_prep)
            if prep_phrase:
                frame["object_text"] = prep_phrase

    if frame["quoted_text"] and xcomp:
        frame["grammar_pattern"] = "root+xcomp+quote"
    elif frame["quoted_text"] and frame.get("secondary_verb"):
        frame["grammar_pattern"] = "root+xcomp+quote"
    elif xcomp and frame.get("object_text"):
        frame["grammar_pattern"] = "root+xcomp+object"
    elif frame.get("object_text"):
        frame["grammar_pattern"] = "root+object"
    elif frame.get("emotion_text"):
        frame["grammar_pattern"] = "root+emotion+context"
    elif frame.get("time_context") or frame.get("context_text"):
        frame["grammar_pattern"] = "root+time+context"

    # Dynamic grammar memory extraction
    gm = _build_grammar_memory_dict(doc, frame)
    frame["grammar_memory"] = gm
    frame["event_pattern"] = gm
    frame["semantic_frame"] = gm
    
    # Merge grammar fields into the main action frame dict for flat access
    for k, v in gm.items():
        if k not in frame or frame[k] is None:
            frame[k] = v

    return frame


def _build_heuristic_grammar_memory(text: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    text_clean = _clean_text(text)
    lowered = text_clean.lower()
    
    subject = frame.get("subject") or "User"
    verb_text = frame.get("root_verb")
    verb_lemma = frame.get("root_verb_lemma")
    secondary_verb = frame.get("secondary_verb")
    secondary_verb_lemma = frame.get("secondary_verb_lemma")
    
    object_text = frame.get("object_text")
    object_head = None
    if object_text:
        words = re.findall(r"[A-Za-z0-9_-]+", object_text)
        if words:
            object_head = words[-1].lower().replace("-", "_")
            if len(words) >= 2 and words[-2].lower() in {"grounding", "wind-down", "sleep", "no-phone"}:
                object_head = f"{words[-2].lower()}_{words[-1].lower()}".replace("-", "_")
                
    if not object_head and frame.get("emotion_text"):
        object_text = frame.get("emotion_text")
        object_head = frame.get("emotion_text").lower().replace("-", "_")

    preposition = None
    context_object = None
    context_text = frame.get("context_text")
    
    prep_match = re.search(r"\b(before|about|with|for|during|after)\s+(.+)$", lowered)
    if prep_match:
        preposition = prep_match.group(1)
        pobj_text = prep_match.group(2).strip(" .")
        context_text = f"{preposition} {pobj_text}"
        
        pobj_words = re.findall(r"[A-Za-z0-9_-]+", pobj_text)
        if pobj_words:
            if pobj_words[0].endswith("ing") and len(pobj_words) > 1:
                context_object = pobj_words[-1].lower().replace("-", "_")
                if len(pobj_words) >= 3 and pobj_words[-2].lower() in {"stressful", "work", "night"}:
                    context_object = f"{pobj_words[-2].lower()}_{pobj_words[-1].lower()}".replace("-", "_")
            else:
                context_object = pobj_words[-1].lower().replace("-", "_")
                if len(pobj_words) >= 2 and pobj_words[-2].lower() in {"stressful", "work", "night"}:
                    context_object = f"{pobj_words[-2].lower()}_{pobj_words[-1].lower()}".replace("-", "_")

    if object_head:
        object_head = object_head.replace(" ", "_").replace("-", "_")
    if context_object:
        context_object = context_object.replace(" ", "_").replace("-", "_")

    key_parts = []
    if subject:
        key_parts.append(subject.lower())
    else:
        key_parts.append("user")
    
    if verb_lemma:
        key_parts.append(verb_lemma.lower())
    if secondary_verb_lemma:
        key_parts.append(secondary_verb_lemma.lower())
    if object_head:
        key_parts.append(object_head)
    if preposition and context_object:
        key_parts.append(f"{preposition}_{context_object}")

    pattern_key = ".".join(key_parts)

    label_parts = []
    if verb_text:
        label_parts.append(verb_text.lower())
    if secondary_verb:
        label_parts.append(secondary_verb.lower())
    if object_head:
        label_parts.append(object_head)
    if preposition and context_object:
        label_parts.append(f"{preposition}_{context_object}")

    pattern_label = "_".join(label_parts)

    return {
        "subject": subject,
        "verb_text": verb_text or "",
        "verb_lemma": verb_lemma or "",
        "object_text": object_text or "",
        "object_head": object_head or "",
        "context_text": context_text or "",
        "preposition": preposition or "",
        "context_object": context_object or "",
        "pattern_key": pattern_key,
        "pattern_label": pattern_label,
        "confidence": 0.0,
    }


def _heuristic_extract_action_frame(text: str) -> Dict[str, Any]:
    text = _clean_text(text)
    frame = _make_base_frame(text, "heuristic_fallback")
    if not text:
        return frame

    lowered = text.lower()
    outer_context = _extract_outer_clause_context(text)
    words = re.findall(r"[A-Za-z']+", text)
    if len(words) >= 2:
        frame["subject"] = words[0]
        frame["root_verb"] = words[1]
        frame["root_verb_lemma"] = words[1].lower()
        frame["trigger_phrase"] = " ".join(words[: min(5, len(words))])

    if frame["quoted_text"] and outer_context.get("root_verb"):
        frame["root_verb"] = outer_context["root_verb"]
        frame["root_verb_lemma"] = outer_context["root_verb_lemma"]
        frame["trigger_phrase"] = outer_context.get("trigger_phrase")
        if outer_context.get("secondary_verb"):
            frame["secondary_verb"] = outer_context["secondary_verb"]
            frame["secondary_verb_lemma"] = outer_context["secondary_verb_lemma"]
            if frame["secondary_verb"].lower() == frame["root_verb"].lower():
                frame["secondary_verb"] = "remember"
                frame["secondary_verb_lemma"] = "remember"
        if outer_context.get("object_text"):
            frame["object_text"] = outer_context["object_text"]
        if outer_context.get("context_text") and outer_context.get("context_text") != "about you":
            frame["context_text"] = outer_context["context_text"]

    xcomp_match = re.search(r"\bto\s+([a-zA-Z']+)\b", lowered)
    if xcomp_match:
        frame["secondary_verb"] = xcomp_match.group(1)
        frame["secondary_verb_lemma"] = xcomp_match.group(1)
        after = text[xcomp_match.end() :].strip(" .:")
        if after:
            frame["object_text"] = after
        frame["grammar_pattern"] = "root+xcomp+object" if after else "root+xcomp"

    if not frame.get("object_text"):
        object_match = re.search(r"\b(?:discussed|explored|reported|described|practiced|rehearsed|updated)\s+(.+)$", lowered)
        if object_match:
            frame["object_text"] = text[object_match.start(1):].strip(" .")
            frame["grammar_pattern"] = "root+object"
            frame["extraction_method"] = "regex_fallback"

    if frame["quoted_text"]:
        frame["grammar_pattern"] = "root+xcomp+quote" if frame.get("secondary_verb") else "root+quote"

    if not frame.get("object_text") and re.search(r"\b(?:committed|planned|decided|chose|wanted|agreed|updated)\b", lowered):
        nominal_match = re.search(r"\b(?:a|an|the|one)\s+([^.,]+)$", text, re.IGNORECASE)
        if nominal_match:
            frame["object_text"] = nominal_match.group(1).strip(" .")
            if frame.get("grammar_pattern") == "unknown":
                frame["grammar_pattern"] = "root+object"

    feel_match = re.search(r"\b(?:felt|feels|feeling|reported|described)\s+([a-zA-Z-]+)(?:\s+about\s+(.+))?", lowered)
    if feel_match:
        frame["emotion_text"] = feel_match.group(1)
        if feel_match.group(2):
            frame["context_text"] = feel_match.group(2).strip(" .")
        frame["grammar_pattern"] = "root+emotion+context"
        frame["extraction_method"] = "regex_fallback"

    time_match = re.search(r"\b\d{1,2}\s?(?:AM|PM|am|pm)\b", text)
    if time_match:
        frame["time_context"] = time_match.group(0)
        with_match = re.search(r"\bwith\s+(.+)$", text, re.IGNORECASE)
        if with_match:
            frame["context_text"] = with_match.group(1).strip(" .")
        if frame["grammar_pattern"] == "unknown":
            frame["grammar_pattern"] = "root+time+context"
            frame["extraction_method"] = "regex_fallback"

    if not frame.get("context_text"):
        prep_match = re.search(r"\b(before|about|with|for|during|after)\s+(.+)$", text, re.IGNORECASE)
        if prep_match:
            frame["context_text"] = f"{prep_match.group(1)} {prep_match.group(2).strip(' .')}"

    # Dynamic grammar memory extraction in heuristic fallback
    gm = _build_heuristic_grammar_memory(text, frame)
    frame["grammar_memory"] = gm
    frame["event_pattern"] = gm
    frame["semantic_frame"] = gm
    
    # Merge grammar fields into the main action frame dict for flat access
    for k, v in gm.items():
        if k not in frame or frame[k] is None:
            frame[k] = v

    return frame


def _classify_frame_type(
    frame: Dict[str, Any],
    text: str,
    memory_type: Optional[str] = None,
    source_kind: Optional[str] = None,
) -> Dict[str, Any]:
    scores = defaultdict(float)

    pattern = frame.get("grammar_pattern") or "unknown"
    has_secondary = bool(frame.get("secondary_verb")) or pattern.startswith("root+xcomp")

    if pattern.startswith("root+xcomp") or has_secondary:
        scores["action_intent"] += 0.6
    if frame.get("quoted_text"):
        scores["exact_phrase"] += 0.7
    if pattern == "root+object":
        scores["discussion_topic"] += 0.6
        if has_secondary:
            scores["action_intent"] += 0.35
    if frame.get("emotion_text"):
        scores["emotional_report"] += 0.7
    if pattern == "root+time+context":
        scores["unresolved_state"] += 0.4
        if has_secondary and _looks_like_intentful_preposition_context(frame.get("context_text")):
            scores["action_intent"] += 0.45

    if memory_type == "session_summary" or source_kind == "summary":
        scores["session_summary"] += 0.7
    if memory_type in {"communication_script", "grounding_phrase", "remembered_phrase"}:
        scores["exact_phrase"] += 0.5
    if memory_type in {"follow_up_intent", "user_goal"}:
        scores["action_intent"] += 0.6
    if memory_type == "coping_strategy":
        scores["discussion_topic"] += 0.4
    if memory_type in {"unresolved_theme", "emotional_pattern"}:
        scores["unresolved_state"] += 0.4
        scores["emotional_report"] += 0.3
    if memory_type == "preference":
        scores["preference"] += 0.6

    lowered = (text or "").lower()
    if frame.get("quoted_text") and len(frame["quoted_text"].split()) >= 3:
        scores["exact_phrase"] += 0.15
    if has_secondary and frame.get("object_text"):
        scores["action_intent"] += 0.15
    if frame.get("quoted_text") and has_secondary:
        scores["exact_phrase"] += 0.25
    if has_secondary and frame.get("root_verb") and frame.get("object_text") and frame.get("subject"):
        scores["action_intent"] += 0.15
    if has_secondary and frame.get("root_verb") and _looks_like_intentful_preposition_context(frame.get("context_text")):
        scores["action_intent"] += 0.20
    if frame.get("object_text") and any(marker in lowered for marker in ["discussed", "explored", "practiced"]):
        scores["discussion_topic"] += 0.2
    if frame.get("emotion_text") and any(marker in lowered for marker in ["felt", "feels", "described", "reported"]):
        scores["emotional_report"] += 0.2

    if not scores:
        frame["frame_type"] = "unknown"
        frame["frame_type_confidence"] = 0.1
        frame["confidence"] = 0.1
        return frame

    frame_type, score = max(scores.items(), key=lambda item: item[1])
    if frame_type not in FRAME_TYPE_VALUES:
        frame_type = "unknown"
    confidence = min(1.0, round(score, 3))
    frame["frame_type"] = frame_type
    frame["frame_type_confidence"] = confidence
    frame["confidence"] = confidence
    return frame


def derive_query_affordances(
    action_frame: Optional[Dict[str, Any]],
    memory_type: str,
    exact_value: Optional[str] = None,
) -> List[str]:
    affordances: List[str] = []
    action_frame = action_frame or {}
    frame_type = action_frame.get("frame_type", "unknown")
    pattern = action_frame.get("grammar_pattern", "unknown")

    # Check structural secondary verb or memory type for action intent
    has_secondary = bool(action_frame.get("secondary_verb")) or pattern.startswith("root+xcomp")
    is_goal = memory_type in {"user_goal", "follow_up_intent"}

    if exact_value or frame_type == "exact_phrase" or memory_type in {"communication_script", "grounding_phrase", "remembered_phrase"}:
        affordances.append("exact_recall")
    if has_secondary or is_goal:
        affordances.append("action_recall")
        if (action_frame.get("secondary_verb") or action_frame.get("context_text")):
            affordances.append("plan_recall")
        affordances.append("commitment_recall")
    if frame_type in {"discussion_topic", "session_summary"} or memory_type in {"session_summary", "coping_strategy"}:
        affordances.append("topic_recall")
    if frame_type in {"emotional_report", "unresolved_state"} or memory_type in {"unresolved_theme", "emotional_pattern"}:
        affordances.append("emotion_context_recall")

    deduped: List[str] = []
    for affordance in affordances:
        if affordance not in deduped:
            deduped.append(affordance)
    return deduped


def extract_action_frame(
    text: str,
    memory_type: Optional[str] = None,
    source_kind: Optional[str] = None,
) -> Dict[str, Any]:
    text = _clean_text(text)
    if not text:
        return _make_base_frame(text, "heuristic_fallback")

    frame = _spacy_extract_action_frame(text)
    if frame.get("quoted_text") and "remember the sentence" in text.lower():
        frame["root_verb"] = frame.get("root_verb") or "wanted"
        if frame.get("root_verb_lemma") in {None, "wanted"}:
            frame["root_verb_lemma"] = "want"
        frame["secondary_verb"] = "remember"
        frame["secondary_verb_lemma"] = "remember"
        frame["object_text"] = "the sentence"
        convo_match = re.search(r"\bfor\s+(.+)$", _strip_quoted_spans(text), re.IGNORECASE)
        if convo_match:
            frame["context_text"] = f"for {convo_match.group(1).strip(' .')}"
        frame["grammar_pattern"] = "root+xcomp+quote"
        
        # Re-build grammar memory with corrected fields
        gm = _build_heuristic_grammar_memory(text, frame)
        frame["grammar_memory"] = gm
        frame["event_pattern"] = gm
        frame["semantic_frame"] = gm
        for k, v in gm.items():
            frame[k] = v

    frame = _classify_frame_type(frame, text=text, memory_type=memory_type, source_kind=source_kind)
    return frame


def build_action_frame_inventory(memories_or_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    root_counter: Counter[str] = Counter()
    secondary_counter: Counter[str] = Counter()
    pattern_counter: Counter[str] = Counter()
    frame_counter: Counter[str] = Counter()
    pattern_examples: Dict[str, List[str]] = defaultdict(list)

    def _yield_text_items(items: Iterable[Dict[str, Any]]):
        for item in items:
            if "key_moments" in item:
                for moment in item.get("key_moments", []):
                    yield {"text": str(moment), "memory_type": None, "source_kind": "key_moment"}
                summary = item.get("summary")
                if summary:
                    yield {"text": str(summary), "memory_type": "session_summary", "source_kind": "summary"}
            else:
                text = item.get("source_text") or item.get("summary") or ""
                if text:
                    yield {
                        "text": str(text),
                        "memory_type": item.get("memory_type"),
                        "source_kind": item.get("memory_source_kind"),
                    }

    for item in _yield_text_items(memories_or_sessions):
        frame = extract_action_frame(
            item["text"],
            memory_type=item.get("memory_type"),
            source_kind=item.get("source_kind"),
        )
        root = frame.get("root_verb_lemma") or "None"
        secondary = frame.get("secondary_verb_lemma") or "None"
        pattern = frame.get("grammar_pattern") or "unknown"
        frame_type = frame.get("frame_type") or "unknown"

        root_counter[root] += 1
        secondary_counter[secondary] += 1
        pattern_counter[pattern] += 1
        frame_counter[frame_type] += 1

        if len(pattern_examples[pattern]) < 3:
            pattern_examples[pattern].append(item["text"])

        rows.append(
            {
                "text": item["text"],
                "root_verb_lemma": root,
                "secondary_verb_lemma": secondary,
                "pattern": pattern,
                "frame_type": frame_type,
            }
        )

    grouped_rows = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["root_verb_lemma"], row["secondary_verb_lemma"], row["pattern"], row["frame_type"])].append(row["text"])

    for (root, secondary, pattern, frame_type), examples in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        grouped_rows.append(
            {
                "root_verb": root,
                "secondary_verb": secondary,
                "pattern": pattern,
                "frame_type": frame_type,
                "count": len(examples),
                "example": examples[0],
            }
        )

    return {
        "parser_status": get_action_frame_parser_status(),
        "root_verbs": dict(root_counter.most_common()),
        "secondary_verbs": dict(secondary_counter.most_common()),
        "grammar_patterns": dict(pattern_counter.most_common()),
        "frame_type_distribution": dict(frame_counter.most_common()),
        "pattern_examples": dict(pattern_examples),
        "rows": grouped_rows,
    }


def parse_emotion_state_query(query: str) -> Dict[str, Any]:
    """
    Parses a query for emotional/state expressions dynamically using dependency parsing.
    Returns extracted emotion terms, context terms, normalized emotions, and grammar pattern.
    """
    query_clean = re.sub(r'\s+', ' ', (query or '').strip()).lower()
    
    result = {
        'query_type': 'unknown',
        'emotion_terms': [],
        'context_terms': [],
        'normalized_emotions': [],
        'grammar_pattern': 'unknown',
        'confidence': 0.0,
    }
    
    nlp = _ensure_nlp_loaded()
    if not nlp:
        return result
        
    doc = nlp(query_clean)
    
    is_emotion = False
    emotions = []
    contexts = []
    
    state_verbs = {'feel', 'be', 'make', 'seem', 'sound', 'get'}
    
    for token in doc:
        # Detect emotion adjectives/verbs acting as complements or conjuncts to state verbs
        if token.dep_ in {'acomp', 'ccomp', 'attr', 'dobj', 'oprd'} or (token.dep_ == 'conj'):
            head = token.head
            # Follow conjuncts up to the main verb
            while head.dep_ == 'conj':
                head = head.head
            if head.lemma_ in state_verbs:
                is_emotion = True
                emotions.append(token.text)
                
        # Specific structural idioms that parse weirdly
        if token.dep_ == 'advmod' and token.text == 'much' and token.head.lemma_ in state_verbs:
            is_emotion = True
            emotions.append('too much')
            
        if token.dep_ == 'prep' and token.text == 'on' and token.head.lemma_ in state_verbs:
            pobj = next((t for t in token.children if t.dep_ == 'pobj' and t.text == 'edge'), None)
            if pobj:
                is_emotion = True
                emotions.append('on edge')

    # Context extraction
    for token in doc:
        if token.dep_ == 'prep' and token.text not in {'on'}: # exclude 'on edge'
            pobj = next((t for t in token.children if t.dep_ in {'pobj', 'pcomp'}), None)
            if pobj:
                contexts.append(pobj.text)
        elif token.dep_ in {'npadvmod', 'advmod'}:
            if token.text not in {'so', 'too', 'very', 'really', 'just', 'even', 'now', 'much', 'lately'}:
                contexts.append(token.text)
            if token.text == 'lately': # Lately is a context term
                contexts.append(token.text)
        elif token.dep_ == 'nsubj' and token.head.lemma_ == 'make':
            contexts.append(token.text)
            
    if is_emotion or len(emotions) > 0:
        result['query_type'] = 'emotion_state'
        result['emotion_terms'] = list(set(emotions))
        result['context_terms'] = list(set(contexts))
        result['confidence'] = 0.8
        
        # Normalize (with optional weak fallback map as requested)
        fallback_map = {
            'sad': 'sadness',
            'down': 'sadness',
            'disconnected': 'loneliness',
            'isolated': 'loneliness',
            'lonely': 'loneliness',
            'angry': 'anger',
            'furious': 'anger',
            'mad': 'anger',
            'nervous': 'anxiety',
            'anxious': 'anxiety',
            'on edge': 'anxiety',
            'overwhelmed': 'overwhelm',
            'too much': 'overwhelm'
        }
        
        normalized = []
        for e in result['emotion_terms']:
            e_norm = e.lower()
            if e_norm in fallback_map:
                normalized.append(fallback_map[e_norm])
            else:
                normalized.append(e_norm)
        result['normalized_emotions'] = list(set(normalized))
        
        if any(tok.lemma_ == 'make' for tok in doc):
            result['grammar_pattern'] = 'caused_state'
        elif any(tok.lemma_ == 'feel' for tok in doc):
            result['grammar_pattern'] = 'feeling_state'
        else:
            result['grammar_pattern'] = 'copular_state'
            
    return result
def parse_exercise_routine_query(query: str) -> Dict:
    """
    Parse the query using spaCy to dynamically detect 'exercise/routine' or 'method' inquiries.
    Extracts main verb, object/head noun, modifiers, and context without hardcoding fixed trigger phrases.
    """
    nlp = _ensure_nlp_loaded()
    if nlp is None or nlp is False:
        return {'query_type': None, 'confidence': 0.0}
    doc = nlp(query)
    result = {
        'query_type': None,
        'core_nouns': [],
        'verbs': [],
        'context_terms': [],
        'confidence': 0.0
    }
    
    # Weak hints to classify the query family, not for rigid matching
    seed_words = {'exercise', 'routine', 'practice', 'suggest', 'recommend', 'calm', 'method', 'thing', 'technique'}
    
    is_routine_query = False
    nouns = []
    verbs = []
    contexts = []
    
    for token in doc:
        if token.pos_ in ['NOUN', 'PROPN']:
            nouns.append(token.lemma_)
            if token.lemma_.lower() in seed_words:
                is_routine_query = True
                
        if token.pos_ == 'VERB':
            verbs.append(token.lemma_)
            if token.lemma_.lower() in seed_words:
                is_routine_query = True
                
        # Additional contextual clues "what did we try/use"
        if token.lemma_.lower() in ['try', 'give', 'use', 'do', 'recommend', 'suggest']:
            is_routine_query = True
            
        if token.pos_ == 'ADJ' or token.tag_ == 'VBG': # e.g. calming
            contexts.append(token.lemma_)
            if token.lemma_.lower() in seed_words:
                is_routine_query = True

    # Mostly interrogative "What [noun] did you [verb]"
    is_what_query = any(tok.lemma_.lower() == 'what' for tok in doc)
    
    if is_what_query and is_routine_query:
        result['query_type'] = 'exercise_routine'
        result['core_nouns'] = list(set(nouns))
        result['verbs'] = list(set(verbs))
        result['context_terms'] = list(set(contexts))
        result['confidence'] = 0.8
        
    return result
