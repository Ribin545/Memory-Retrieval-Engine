"""
Document-Aware Grammar/Emotion Cache Builder for External Benchmarks

Steps:
  1. Clean document (remove date headers, markdown, boilerplate)
  2. Split into sentences
  3. Filter for event-like sentences (short, user-centric, action-oriented)
  4. Run spaCy dependency parsing on short sentences via nlp.pipe()
  5. Extract grammar frames per sentence
  6. Store multiple frames per memory unit

Output format per memory:
  {
    "memory_id": "...",
    "frames": [
      {
        "sentence": "...",
        "verb_lemma": "...",
        "object_head": "...",
        "object_text": "...",
        "context_object": "...",
        "entities": [...],
        "dates": [...],
        "pattern_key": "...",
      }
    ],
    "topic_terms": [...],
    "named_entities": [...],
    "emotion_terms": [...],
    # flat legacy fields preserved for backward compat
    "verb_lemma": "", "object_head": "", ...
  }
"""
import os
import sys
import json
import argparse
import re
import time
from typing import Dict, Any, List, Set, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.retrieval_domain.features.grammar_frame_extractor import _ensure_nlp_loaded
from app.benchmarks.longmemeval_s_adapter import LongMemEvalAdapter
from app.benchmarks.locomo_adapter import LocomoAdapter

# ---------------------------------------------------------------------------
# Document cleaning
# ---------------------------------------------------------------------------

_DATE_HEADER_RE = re.compile(
    r"\[Date:\s*\d{4}[/-]\d{1,2}[/-]\d{1,2}\s*(?:\([^)]+\))?\s*(?:\d{1,2}:\d{2})?\]",
    re.IGNORECASE,
)

_MARKDOWN_CODE_RE = re.compile(r"```[\s\S]*?```")
_MARKDOWN_HEADER_RE = re.compile(r"^#{1,6}\s+.+$", re.MULTILINE)
_MARKDOWN_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MARKDOWN_ITALIC_RE = re.compile(r"\*([^*]+)\*")

_SPEAKER_PREFIX_RE = re.compile(
    r"^(Assistant|User|Human|Bot|System|Client|Therapist|Customer|Agent)\s*[:\-]\s*",
    re.IGNORECASE | re.MULTILINE,
)

# URLs / filler
_URL_RE = re.compile(r"https?://\S+")
_EXCESS_WHITESPACE_RE = re.compile(r"[ \t]+|\n{3,}")


def _clean_document(text: str) -> str:
    """Remove date headers, markdown, boilerplate, and normalize speaker prefixes."""
    if not text:
        return ""

    # Remove markdown code blocks
    text = _MARKDOWN_CODE_RE.sub("", text)
    # Remove markdown headers
    text = _MARKDOWN_HEADER_RE.sub("", text)
    # Remove markdown bold/italic markers
    text = _MARKDOWN_BOLD_RE.sub(r"\1", text)
    text = _MARKDOWN_ITALIC_RE.sub(r"\1", text)
    # Remove date headers
    text = _DATE_HEADER_RE.sub("", text)
    # Remove URLs
    text = _URL_RE.sub("", text)
    # Normalize speaker prefixes to newline-separated turns
    text = _SPEAKER_PREFIX_RE.sub(lambda m: f"\n{m.group(1)}: ", text)
    # Collapse whitespace
    text = _EXCESS_WHITESPACE_RE.sub(" ", text)
    # Remove stray bracket fragments
    text = re.sub(r"\[\s*\]", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Sentence splitting (regex-based to avoid loading huge docs into spaCy)
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using regex. Conservative."""
    if not text:
        return []

    # Split on sentence-ending punctuation followed by space and uppercase
    # Also split on newlines that look like turn boundaries
    raw = re.split(r'(?<=[.!?])\s+(?=[A-Z])|\n+(?=(?:Assistant|User|Human|Bot|System|Client|Therapist|Customer|Agent)\s*[:\-])', text)
    sentences = []
    for r in raw:
        r = r.strip()
        if r:
            # Further split on remaining newlines if they create distinct short utterances
            for part in r.split("\n"):
                part = part.strip()
                if part and len(part) >= 10:  # skip fragments
                    sentences.append(part)
    return sentences


# ---------------------------------------------------------------------------
# Event-like sentence scoring
# ---------------------------------------------------------------------------

_USER_WORDS = {"i", "me", "my", "myself", "we", "our", "us", "mine", "ours"}
_ACTION_VERBS = {
    "bought", "purchased", "visited", "went", "did", "made", "planned",
    "decided", "chose", "committed", "agreed", "started", "finished",
    "reported", "mentioned", "said", "told", "asked", "discussed",
    "felt", "feel", "wants", "want", "needs", "need", "likes", "like",
    "prefers", "prefer", "hates", "hate", "loves", "love",
    "will", "going", "schedule", "book", "reserve", "appointment",
    "traveled", "moved", "changed", "joined", "left", "arrived",
    "worked", "studied", "learned", "tried", "attempted",
}
_TEMPORAL_WORDS = {
    "yesterday", "today", "tomorrow", "last", "next", "week", "month",
    "year", "morning", "afternoon", "evening", "night", "monday",
    "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "recently", "soon", "later", "earlier", "before", "after",
}
_EVENT_NOUNS = {
    "birthday", "wedding", "meeting", "interview", "trip", "travel",
    "vacation", "holiday", "party", "concert", "dinner", "lunch",
    "breakfast", "appointment", "visit", "call", "conversation",
    "session", "class", "course", "project", "task", "goal",
}

_BOILERPLATE_RE = re.compile(
    r"^(here are|there are|let me|i can|i will|this is|that is|these are|those are|"
    r"first|second|third|fourth|fifth|overall|in conclusion|to summarize|in summary|"
    r"according to|based on|here is|as follows|for example|such as)\b",
    re.IGNORECASE,
)

_CODE_LIKE_RE = re.compile(r"[=+\-*/\{\}\[\]\|<>~^`]{2,}|```|\bdef\b|\bclass\b|\bimport\b|\bfunction\b")


def _score_event_likeness(text: str) -> float:
    """Score a sentence for event-likeness. Higher = more likely to contain meaningful user events."""
    text_lower = text.lower()
    score = 0.0

    # Length check: too short = likely not useful
    if len(text) < 25:
        score -= 0.3
    if len(text) > 250:
        score -= 0.3

    words = set(re.findall(r"[a-zA-Z']+", text_lower))

    # User presence (strong signal for user memories)
    if words & _USER_WORDS:
        score += 0.35

    # Action verbs
    if words & _ACTION_VERBS:
        score += 0.35

    # Temporal markers
    if words & _TEMPORAL_WORDS:
        score += 0.2

    # Event nouns
    if words & _EVENT_NOUNS:
        score += 0.25

    # Named entity presence (heuristic)
    if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text):
        score += 0.15

    # Penalties
    if _BOILERPLATE_RE.search(text):
        score -= 0.6
    if _CODE_LIKE_RE.search(text):
        score -= 0.6
    if re.search(r"^\d+\.(?:\s|$)", text):  # numbered list item
        score -= 0.3

    return score


# ---------------------------------------------------------------------------
# Frame extraction from spaCy sentence doc
# ---------------------------------------------------------------------------

def _extract_frame_from_doc(doc, sentence_text: str) -> Optional[Dict[str, Any]]:
    """Extract a grammar frame from a single spaCy sentence doc."""
    if not doc or len(doc) == 0:
        return None

    # Must contain at least one verb
    if not any(t.pos_ in {"VERB", "AUX"} for t in doc):
        return None

    root = next((t for t in doc if t.dep_ == "ROOT"), None)
    if not root:
        return None

    # --- Root verb (handle AUX + VERB chains) ---
    root_verb = ""
    root_verb_lemma = ""
    target = root
    if root.pos_ == "AUX":
        main_verb = next((t for t in root.children if t.pos_ == "VERB"), None)
        if main_verb:
            root_verb = main_verb.text.lower()
            root_verb_lemma = getattr(main_verb, "lemma_", main_verb.text.lower())
            target = main_verb
        else:
            root_verb = root.text.lower()
            root_verb_lemma = getattr(root, "lemma_", root.text.lower())
    else:
        root_verb = root.text.lower()
        root_verb_lemma = getattr(root, "lemma_", root.text.lower())

    # --- Subject ---
    subject = ""
    subj_tok = next((t for t in doc if t.dep_ in {"nsubj", "nsubjpass"}), None)
    if subj_tok:
        subject = " ".join(t.text for t in subj_tok.subtree).lower()

    # --- Object head ---
    object_head = ""
    object_text = ""
    obj_tok = next((t for t in target.children if t.dep_ in {"dobj", "attr", "oprd", "pobj"}), None)
    if obj_tok:
        object_text = " ".join(t.text for t in obj_tok.subtree)
        object_head = obj_tok.text.lower()
        compounds = [t.text.lower() for t in obj_tok.children if t.dep_ == "compound" and t.i < obj_tok.i]
        if compounds:
            object_head = "_".join(compounds + [object_head])

    # --- Context (prepositional phrases) ---
    context_terms = []
    context_object = ""
    preposition = ""
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
                    preposition = prep_text

    # --- Entities ---
    entities = [ent.text.lower().replace(" ", "_") for ent in doc.ents
                if ent.label_ in {"PERSON", "ORG", "GPE", "NORP", "PRODUCT", "EVENT", "WORK_OF_ART"}]

    # --- Dates ---
    dates = [ent.text for ent in doc.ents if ent.label_ == "DATE"]

    # --- Pattern key ---
    entity_part = entities[0] if entities else (subject.split()[0] if subject else "user")
    pattern_key = f"{entity_part}.{root_verb_lemma}.{object_head}" if root_verb_lemma else f"{entity_part}.{object_head}"
    if context_object:
        pattern_key += f".context_{context_object}"

    return {
        "sentence": sentence_text,
        "subject": subject,
        "verb_text": root_verb,
        "verb_lemma": root_verb_lemma,
        "object_text": object_text,
        "object_head": object_head,
        "context_object": context_object,
        "context_text": " ".join(context_terms),
        "preposition": preposition,
        "entities": entities,
        "dates": dates,
        "pattern_key": pattern_key,
        "pattern_label": "",
        "confidence": 0.0,
    }


# ---------------------------------------------------------------------------
# Emotion extraction (regex-based, kept lightweight)
# ---------------------------------------------------------------------------

_EMOTION_WORDS_RE = re.compile(
    r"\b(felt|feels|feeling|feel|anxious|sad|depressed|angry|frustrated|"
    r"happy|excited|worried|stressed|overwhelmed|guilty|ashamed|panic|panicking|"
    r"lonely|disconnected|numb|tired|exhausted|scared|frightened|hopeless|helpless|"
    r"confused|disappointed|hurt|betrayed|jealous|embarrassed|insecure|vulnerable|"
    r"calm|relaxed|peaceful|grateful|proud|confident|motivated|energetic)\b",
    re.IGNORECASE,
)

_EMOTION_PHRASE_RE = re.compile(
    r"\b(?:feel|felt|feels|feeling|be|was|were|seem|seems|seemed|"
    r"get|got|gets|getting|make|makes|made|sound|sounds)\s+"
    r"(anxious|sad|depressed|angry|frustrated|happy|excited|worried|stressed|"
    r"overwhelmed|guilty|ashamed|panicked|lonely|disconnected|numb|tired|"
    r"exhausted|scared|frightened|hopeless|helpless|confused|disappointed|"
    r"hurt|betrayed|jealous|embarrassed|insecure|vulnerable|calm|relaxed|"
    r"peaceful|grateful|proud|confident|motivated|energetic)\b",
    re.IGNORECASE,
)

_STOPWORDS: Set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "and", "but", "if", "or",
    "because", "until", "while", "this", "that", "these", "those", "i",
    "me", "my", "myself", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "it", "its", "they", "them", "their", "what", "which",
    "who", "whom", "am", "s", "t", "don", "doesn", "didn", "wasn", "weren",
    "haven", "hasn", "hadn", "won", "wouldn", "couldn", "shouldn", "isn",
    "aren", "ain", "ve", "ll", "re", "d", "m", "o", "y", "ma", "mightn",
    "mustn", "needn", "shan", "yourselves",
}


def _extract_emotion_terms(text: str) -> List[str]:
    if not text:
        return []
    phrase_matches = _EMOTION_PHRASE_RE.findall(text)
    if phrase_matches:
        return sorted(list(set(m.lower() for m in phrase_matches)))
    word_matches = _EMOTION_WORDS_RE.findall(text)
    if word_matches:
        return sorted(list(set(m.lower() for m in word_matches)))
    return []


def _extract_topic_terms(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return sorted(list(set(t for t in tokens if t not in _STOPWORDS)))


def _extract_named_entities_heuristic(text: str) -> List[str]:
    entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}\b", text)
    return sorted(list(set(entities)))


# ---------------------------------------------------------------------------
# Cache entry builder
# ---------------------------------------------------------------------------

def _build_cache_entry_v2(
    mu: Dict[str, Any],
    frames: List[Dict[str, Any]],
    emotion_terms: List[str],
) -> Dict[str, Any]:
    """Build cache entry with frames array + flat legacy fields."""
    text = mu.get("source_text") or mu.get("summary") or ""

    # Flatten best frame for backward compatibility
    best_frame = frames[0] if frames else {}

    return {
        "memory_id": mu.get("memory_id", ""),
        "session_id": mu.get("session_id") or mu.get("source_session_id", ""),
        "source_session_id": mu.get("source_session_id") or mu.get("session_id", ""),
        "memory_unit_type": mu.get("memory_unit_type", mu.get("memory_type", "unknown")),
        "source_text": text,
        "summary": mu.get("summary", text),
        "frames": frames,
        # Legacy flat fields (from best frame)
        "verb_lemma": best_frame.get("verb_lemma", ""),
        "object_head": best_frame.get("object_head", ""),
        "context_object": best_frame.get("context_object", ""),
        "pattern_key": best_frame.get("pattern_key", ""),
        "entities": best_frame.get("entities", []),
        "emotion_terms": emotion_terms,
        "topic_terms": _extract_topic_terms(text),
        "named_entities": _extract_named_entities_heuristic(text),
    }


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_grammar_cache_for_examples(
    examples: List[Any],
) -> Dict[str, Any]:
    """Build document-aware grammar cache for a list of BenchmarkExamples."""
    nlp = _ensure_nlp_loaded()
    spacy_available = nlp is not None and nlp is not False
    if not spacy_available:
        print("[WARN] spaCy unavailable; falling back to heuristic extraction.")
    else:
        print("[INFO] spaCy loaded. Using sentence-level document-aware extraction.")

    # Collect all memory units
    units: List[Dict[str, Any]] = []
    for ex in examples:
        for mu in ex.memory_units:
            units.append({
                "example_id": ex.example_id,
                "memory_id": mu.get("memory_id", ""),
                "session_id": mu.get("session_id") or mu.get("source_session_id", ""),
                "source_session_id": mu.get("source_session_id") or mu.get("session_id", ""),
                "memory_unit_type": mu.get("memory_unit_type", mu.get("memory_type", "unknown")),
                "source_text": mu.get("source_text", ""),
                "summary": mu.get("summary", ""),
            })

    total = len(units)
    print(f"[INFO] Total memory units to process: {total}")

    cache: Dict[str, Any] = {}
    start_t = time.time()

    # Diagnostics
    stats = {
        "units_processed": 0,
        "sentences_total": 0,
        "sentences_event_like": 0,
        "sentences_skipped": 0,
        "frames_extracted": 0,
        "frames_from_spacy": 0,
        "frames_from_heuristic": 0,
        "good_frame_examples": [],
        "rejected_frame_examples": [],
    }

    for i, u in enumerate(units):
        text = u.get("source_text") or u.get("summary") or ""
        cleaned = _clean_document(text)
        sentences = _split_sentences(cleaned)
        stats["sentences_total"] += len(sentences)

        # Score and filter sentences
        scored = []
        for sent in sentences:
            score = _score_event_likeness(sent)
            if score > 0.15:  # event-like threshold
                scored.append((sent, score))
            else:
                stats["sentences_skipped"] += 1

        stats["sentences_event_like"] += len(scored)

        # Sort by score descending, keep top N per document
        scored.sort(key=lambda x: x[1], reverse=True)
        top_sentences = scored[:8]  # max 8 sentences per memory unit

        frames: List[Dict[str, Any]] = []

        if spacy_available and top_sentences:
            sentence_texts = [s[0] for s in top_sentences]
            try:
                docs = list(nlp.pipe(sentence_texts, batch_size=8))
                for doc, (sent_text, score) in zip(docs, top_sentences):
                    frame = _extract_frame_from_doc(doc, sent_text)
                    if frame:
                        frame["confidence"] = round(score, 3)
                        # Skip obvious garbage frames
                        if frame["verb_lemma"] not in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
                            frames.append(frame)
                            stats["frames_from_spacy"] += 1
                        else:
                            stats["rejected_frame_examples"].append({
                                "reason": "date_header_artifact",
                                "sentence": sent_text[:100],
                                "verb_lemma": frame["verb_lemma"],
                            })
            except Exception as e:
                print(f"[WARN] spaCy error on unit {u.get('memory_id', '?')}: {e}")

        # Fallback: if no frames from spaCy, use heuristic on the best sentence
        if not frames and scored:
            best_sent, best_score = scored[0]
            words = re.findall(r"[A-Za-z']+", best_sent)
            if len(words) >= 2:
                frame = {
                    "sentence": best_sent,
                    "subject": words[0].lower(),
                    "verb_text": words[1].lower(),
                    "verb_lemma": words[1].lower(),
                    "object_text": " ".join(words[2:]) if len(words) > 2 else "",
                    "object_head": words[-1].lower() if len(words) > 2 else "",
                    "context_object": "",
                    "context_text": "",
                    "preposition": "",
                    "entities": [],
                    "dates": [],
                    "pattern_key": f"user.{words[1].lower()}.{words[-1].lower()}",
                    "pattern_label": "",
                    "confidence": round(best_score, 3),
                }
                frames.append(frame)
                stats["frames_from_heuristic"] += 1

        stats["frames_extracted"] += len(frames)

        # Collect good examples for diagnostics
        if len(stats["good_frame_examples"]) < 10 and frames:
            stats["good_frame_examples"].append({
                "memory_id": u.get("memory_id", ""),
                "sentence": frames[0]["sentence"][:120],
                "verb_lemma": frames[0]["verb_lemma"],
                "object_head": frames[0]["object_head"],
                "pattern_key": frames[0]["pattern_key"],
            })

        # Emotion extraction from full text (not sentence-level)
        emotion_terms = _extract_emotion_terms(text)

        entry = _build_cache_entry_v2(u, frames, emotion_terms)
        cache[entry["memory_id"]] = entry
        stats["units_processed"] += 1

        if (i + 1) % 100 == 0 or i == total - 1:
            elapsed = time.time() - start_t
            per_unit = elapsed / (i + 1)
            eta = (total - (i + 1)) * per_unit
            print(
                f"[INFO] Processed {i + 1}/{total} ({(i+1)*100//total}%) | "
                f"{per_unit*1000:.1f}ms/unit | ETA: {eta:.0f}s | "
                f"frames: {stats['frames_extracted']}",
                flush=True,
            )

    total_elapsed = time.time() - start_t
    print(f"[INFO] Total cache build time: {total_elapsed:.1f}s ({total_elapsed/total*1000:.1f}ms/unit)")
    print(f"[INFO] Stats: {stats['sentences_total']} sentences, {stats['sentences_event_like']} event-like, "
          f"{stats['frames_extracted']} frames ({stats['frames_from_spacy']} spaCy, {stats['frames_from_heuristic']} heuristic)")

    return cache, stats


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_quality_report(stats: Dict[str, Any], output_path: str) -> None:
    units = stats["units_processed"] or 1
    frames = stats["frames_extracted"] or 1

    lines = [
        "# Grammar Cache Quality Report",
        "",
        f"- **Memory units processed:** {units}",
        f"- **Total sentences found:** {stats['sentences_total']}",
        f"- **Event-like sentences kept:** {stats['sentences_event_like']}",
        f"- **Sentences skipped/rejected:** {stats['sentences_skipped']}",
        f"- **Total frames extracted:** {stats['frames_extracted']}",
        f"- **Frames from spaCy:** {stats['frames_from_spacy']}",
        f"- **Frames from heuristic fallback:** {stats['frames_from_heuristic']}",
        f"- **Average frames per memory:** {frames / units:.2f}",
        "",
        "## Good Frame Examples",
        "",
    ]
    for ex in stats["good_frame_examples"]:
        lines.append(f"- **Memory:** `{ex['memory_id']}`")
        lines.append(f"  - Sentence: *{ex['sentence']}...*")
        lines.append(f"  - verb_lemma: `{ex['verb_lemma']}`")
        lines.append(f"  - object_head: `{ex['object_head']}`")
        lines.append(f"  - pattern_key: `{ex['pattern_key']}`")
        lines.append("")

    lines.append("## Rejected Bad Frames")
    lines.append("")
    if stats["rejected_frame_examples"]:
        for ex in stats["rejected_frame_examples"][:10]:
            lines.append(f"- **Reason:** {ex['reason']}")
            lines.append(f"  - Sentence: *{ex['sentence']}...*")
            lines.append(f"  - verb_lemma: `{ex['verb_lemma']}`")
            lines.append("")
    else:
        lines.append("No bad frames rejected.")
        lines.append("")

    lines.append("## Quality Confirmation")
    lines.append("")
    # Check if any verb_lemma = "mon" or other date artifacts exist
    has_date_artifacts = any(
        ex["verb_lemma"] in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
        for ex in stats["rejected_frame_examples"]
    )
    if has_date_artifacts:
        lines.append("- **Date header filtering:** ACTIVE — artifacts like `verb_lemma='mon'` were detected and rejected.")
    else:
        lines.append("- **Date header filtering:** No date artifacts detected in rejected frames.")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build Document-Aware Grammar Cache for External Benchmarks")
    parser.add_argument("--benchmark", type=str, required=True, choices=["longmemeval_s", "locomo"])
    parser.add_argument("--data-path", type=str, required=True)
    parser.add_argument("--unit-type", type=str, default="turn", choices=["turn", "window_3", "window_4", "window_5", "session"])
    parser.add_argument("--output-dir", type=str, default="data/external/indexes")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resolved-only", action="store_true")
    parser.add_argument("--schema", type=str, default="default", choices=["default", "cleaned"])
    parser.add_argument("--turns-mode", type=str, default="all_turns", choices=["user_only", "all_turns"])
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"[INFO] Loading {args.benchmark} dataset from {args.data_path}...")
    if args.benchmark == "longmemeval_s":
        adapter = LongMemEvalAdapter()
        examples = adapter.load_dataset(
            args.data_path,
            args.limit,
            resolved_only=args.resolved_only,
            schema=args.schema,
            turns_mode=args.turns_mode,
        )
        output_filename = "longmemeval_s_grammar_cache_v2.json"
    else:
        adapter = LocomoAdapter()
        examples = adapter.load_dataset(args.data_path, args.limit, unit_type=args.unit_type)
        output_filename = f"locomo_grammar_cache_{args.unit_type}_v2.json"

    print(f"[INFO] Building document-aware grammar cache for {len(examples)} examples...")
    t0 = time.time()
    cache, stats = build_grammar_cache_for_examples(examples)
    total_time = time.time() - t0

    output_path = os.path.join(args.output_dir, output_filename)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)

    print(f"[INFO] Grammar cache saved to {output_path} ({len(cache)} entries)")

    # Write reports
    report_dir = "outputs/benchmarks"
    os.makedirs(report_dir, exist_ok=True)

    # Build report
    build_report_path = os.path.join(report_dir, "grammar_cache_build_report.md")
    with open(build_report_path, "w", encoding="utf-8") as f:
        f.write("# Grammar Cache Build Report\n\n")
        f.write(f"- **Benchmark:** {args.benchmark}\n")
        f.write(f"- **Unit Type:** {args.unit_type if args.benchmark == 'locomo' else 'N/A'}\n")
        f.write(f"- **Examples:** {len(examples)}\n")
        f.write(f"- **Cache Entries:** {len(cache)}\n")
        f.write(f"- **Mode:** Document-aware sentence-level spaCy extraction\n")
        f.write(f"- **Total Time:** {total_time:.1f}s\n")
        if cache:
            f.write(f"- **Avg Time/Unit:** {total_time/len(cache)*1000:.1f}ms\n")
        f.write(f"- **Output:** `{output_path}`\n")
    print(f"[INFO] Build report saved to {build_report_path}")

    # Quality report
    quality_report_path = os.path.join(report_dir, "grammar_cache_quality_report.md")
    _write_quality_report(stats, quality_report_path)
    print(f"[INFO] Quality report saved to {quality_report_path}")


if __name__ == "__main__":
    main()
