"""
Temporal Event Cache Builder for External Benchmarks

Steps:
  1. Extract document-level timestamp from text headers (LongMemEval date headers)
  2. Run spaCy NER to collect DATE/TIME entities
  3. For each DATE/TIME entity, walk dependency tree to find associated verb/noun head
  4. Normalize dates relative to document timestamp where possible
  5. Store temporal event records per memory unit

Output format per memory:
  {
    "memory_id": "...",
    "session_id": "...",
    "document_timestamp": "2023-05-25T21:29:00",
    "date_entities": [
      {"text": "...", "label": "DATE|TIME", "start": 0, "end": 5}
    ],
    "temporal_events": [
      {
        "date_text": "...",
        "normalized_date": "2023-05-25",
        "event_span": "visited the museum",
        "event_type": "verb|noun",
        "related_tokens": ["visited", "museum"],
      }
    ]
  }
"""
import os
import sys
import json
import argparse
import re
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.retrieval_domain.features.grammar_frame_extractor import _ensure_nlp_loaded
from app.benchmarks.longmemeval_s_adapter import LongMemEvalAdapter
from app.benchmarks.locomo_adapter import LocomoAdapter

# Import document cleaning from grammar cache builder
from app.benchmarks.build_grammar_cache import _clean_document

# ---------------------------------------------------------------------------
# Document timestamp extraction
# ---------------------------------------------------------------------------

_LONGMEMEVAL_DATE_RE = re.compile(
    r"\[Date:\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*(?:\([^)]+\))?\s*(?:(\d{1,2}):(\d{2}))?\]",
    re.IGNORECASE,
)


def _extract_document_timestamp(text: str) -> Optional[str]:
    """Extract ISO timestamp from LongMemEval date header if present."""
    if not text:
        return None
    m = _LONGMEMEVAL_DATE_RE.search(text)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour = int(m.group(4)) if m.group(4) else 0
        minute = int(m.group(5)) if m.group(5) else 0
        try:
            dt = datetime(year, month, day, hour, minute)
            return dt.isoformat()
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Date normalization
# ---------------------------------------------------------------------------

def _normalize_date_entity(date_text: str, doc_timestamp: Optional[str]) -> Optional[str]:
    """Try to normalize a date entity text to ISO date string."""
    if not date_text:
        return None

    # Direct ISO-like match
    iso_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", date_text)
    if iso_match:
        try:
            return f"{int(iso_match.group(1))}-{int(iso_match.group(2)):02d}-{int(iso_match.group(3)):02d}"
        except ValueError:
            pass

    # Month name match
    month_match = re.match(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,\s+(\d{4}))?",
        date_text, re.IGNORECASE,
    )
    if month_match:
        months = {
            "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
            "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        }
        month = months.get(month_match.group(1).lower())
        day = int(month_match.group(2))
        year = int(month_match.group(3)) if month_match.group(3) else None
        if doc_timestamp and year is None:
            try:
                doc_dt = datetime.fromisoformat(doc_timestamp)
                year = doc_dt.year
            except Exception:
                pass
        if month and year:
            try:
                return f"{year}-{month:02d}-{day:02d}"
            except ValueError:
                pass

    # Relative day names
    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    day_lower = date_text.lower().strip()
    if day_lower in day_map and doc_timestamp:
        try:
            doc_dt = datetime.fromisoformat(doc_timestamp)
            # Just return the document date as best approximation
            return doc_dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# Temporal event extraction from spaCy doc
# ---------------------------------------------------------------------------

def _extract_temporal_events_from_doc(doc, doc_timestamp: Optional[str]) -> List[Dict[str, Any]]:
    """Extract temporal events from a spaCy doc."""
    events = []
    if not doc:
        return events

    for ent in doc.ents:
        if ent.label_ not in {"DATE", "TIME"}:
            continue

        # Walk dependency tree to find associated event head
        event_head = None
        event_type = ""
        related_tokens = []

        # Strategy 1: The entity's head is a verb or noun
        head = ent.root.head if ent.root else None
        if head:
            if head.pos_ in {"VERB", "AUX"}:
                event_head = head
                event_type = "verb"
                related_tokens = [t.text for t in head.subtree if t.pos_ in {"VERB", "NOUN", "PROPN"}]
            elif head.pos_ in {"NOUN", "PROPN"}:
                event_head = head
                event_type = "noun"
                related_tokens = [t.text for t in head.subtree if t.pos_ in {"VERB", "NOUN", "PROPN"}]

        # Strategy 2: If head is a prep, look at prep's head
        if not event_head and head and head.pos_ == "ADP":
            prep_head = head.head
            if prep_head and prep_head.pos_ in {"VERB", "NOUN"}:
                event_head = prep_head
                event_type = "verb" if prep_head.pos_ == "VERB" else "noun"
                related_tokens = [t.text for t in prep_head.subtree if t.pos_ in {"VERB", "NOUN", "PROPN"}]

        # Strategy 3: Look for closest verb in the sentence
        if not event_head:
            sent = ent.sent
            if sent:
                verbs = [t for t in sent if t.pos_ in {"VERB", "AUX"}]
                if verbs:
                    # Pick verb closest to entity
                    closest = min(verbs, key=lambda v: abs(v.i - ent.start))
                    event_head = closest
                    event_type = "verb"
                    related_tokens = [t.text for t in closest.subtree if t.pos_ in {"VERB", "NOUN", "PROPN"}]

        event_span = ""
        if event_head:
            event_span = " ".join(t.text for t in event_head.subtree).strip()
            if len(event_span) > 120:
                event_span = event_span[:120] + "..."

        normalized = _normalize_date_entity(ent.text, doc_timestamp)

        events.append({
            "date_text": ent.text,
            "normalized_date": normalized,
            "event_span": event_span,
            "event_type": event_type,
            "related_tokens": related_tokens[:10],
        })

    return events


# ---------------------------------------------------------------------------
# Cache entry builder
# ---------------------------------------------------------------------------

def _build_temporal_cache_entry(
    mu: Dict[str, Any],
    doc_timestamp: Optional[str],
    date_entities: List[Dict[str, Any]],
    temporal_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "memory_id": mu.get("memory_id", ""),
        "session_id": mu.get("session_id") or mu.get("source_session_id", ""),
        "source_session_id": mu.get("source_session_id") or mu.get("session_id", ""),
        "memory_unit_type": mu.get("memory_unit_type", mu.get("memory_type", "unknown")),
        "document_timestamp": doc_timestamp,
        "date_entities": date_entities,
        "temporal_events": temporal_events,
    }


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_temporal_cache_for_examples(
    examples: List[Any],
) -> Dict[str, Any]:
    """Build temporal cache for a list of BenchmarkExamples."""
    nlp = _ensure_nlp_loaded()
    spacy_available = nlp is not None and nlp is not False
    if not spacy_available:
        print("[WARN] spaCy unavailable; temporal cache will be empty.")
    else:
        print("[INFO] spaCy loaded. Extracting temporal events...")

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

    stats = {
        "units_processed": 0,
        "documents_with_timestamp": 0,
        "date_entities_found": 0,
        "temporal_events_extracted": 0,
    }

    for i, u in enumerate(units):
        text = u.get("source_text") or u.get("summary") or ""
        cleaned = _clean_document(text)

        # Extract document-level timestamp
        doc_timestamp = _extract_document_timestamp(text)
        if doc_timestamp:
            stats["documents_with_timestamp"] += 1

        date_entities = []
        temporal_events = []

        if spacy_available and cleaned:
            try:
                doc = nlp(cleaned)
                for ent in doc.ents:
                    if ent.label_ in {"DATE", "TIME"}:
                        date_entities.append({
                            "text": ent.text,
                            "label": ent.label_,
                            "start": ent.start_char,
                            "end": ent.end_char,
                        })
                temporal_events = _extract_temporal_events_from_doc(doc, doc_timestamp)
            except Exception as e:
                print(f"[WARN] spaCy error on unit {u.get('memory_id', '?')}: {e}")

        stats["date_entities_found"] += len(date_entities)
        stats["temporal_events_extracted"] += len(temporal_events)

        entry = _build_temporal_cache_entry(u, doc_timestamp, date_entities, temporal_events)
        cache[entry["memory_id"]] = entry
        stats["units_processed"] += 1

        if (i + 1) % 100 == 0 or i == total - 1:
            elapsed = time.time() - start_t
            per_unit = elapsed / (i + 1)
            eta = (total - (i + 1)) * per_unit
            print(
                f"[INFO] Processed {i + 1}/{total} ({(i + 1) * 100 // total}%) | "
                f"{per_unit * 1000:.1f}ms/unit | ETA: {eta:.0f}s | "
                f"events: {stats['temporal_events_extracted']}",
                flush=True,
            )

    total_elapsed = time.time() - start_t
    print(f"[INFO] Total cache build time: {total_elapsed:.1f}s ({total_elapsed / total * 1000:.1f}ms/unit)")
    print(f"[INFO] Stats: {stats['documents_with_timestamp']} docs with timestamp, "
          f"{stats['date_entities_found']} date entities, {stats['temporal_events_extracted']} temporal events")

    return cache, stats


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_quality_report(stats: Dict[str, Any], output_path: str) -> None:
    lines = [
        "# Temporal Cache Quality Report",
        "",
        f"- **Memory units processed:** {stats['units_processed']}",
        f"- **Documents with timestamp:** {stats['documents_with_timestamp']}",
        f"- **Date entities found:** {stats['date_entities_found']}",
        f"- **Temporal events extracted:** {stats['temporal_events_extracted']}",
        "",
    ]
    if stats['units_processed']:
        lines.append(f"- **Avg date entities per unit:** {stats['date_entities_found'] / stats['units_processed']:.2f}")
        lines.append(f"- **Avg temporal events per unit:** {stats['temporal_events_extracted'] / stats['units_processed']:.2f}")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build Temporal Cache for External Benchmarks")
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
        output_filename = "longmemeval_s_temporal_cache.json"
    else:
        adapter = LocomoAdapter()
        examples = adapter.load_dataset(args.data_path, args.limit, unit_type=args.unit_type)
        output_filename = f"locomo_temporal_cache_{args.unit_type}.json"

    print(f"[INFO] Building temporal cache for {len(examples)} examples...")
    t0 = time.time()
    cache, stats = build_temporal_cache_for_examples(examples)
    total_time = time.time() - t0

    output_path = os.path.join(args.output_dir, output_filename)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)

    print(f"[INFO] Temporal cache saved to {output_path} ({len(cache)} entries)")

    # Write reports
    report_dir = "outputs/benchmarks"
    os.makedirs(report_dir, exist_ok=True)

    build_report_path = os.path.join(report_dir, "temporal_cache_build_report.md")
    with open(build_report_path, "w", encoding="utf-8") as f:
        f.write("# Temporal Cache Build Report\n\n")
        f.write(f"- **Benchmark:** {args.benchmark}\n")
        f.write(f"- **Unit Type:** {args.unit_type if args.benchmark == 'locomo' else 'N/A'}\n")
        f.write(f"- **Examples:** {len(examples)}\n")
        f.write(f"- **Cache Entries:** {len(cache)}\n")
        f.write(f"- **Total Time:** {total_time:.1f}s\n")
        if cache:
            f.write(f"- **Avg Time/Unit:** {total_time / len(cache) * 1000:.1f}ms\n")
        f.write(f"- **Output:** `{output_path}`\n")
    print(f"[INFO] Build report saved to {build_report_path}")

    quality_report_path = os.path.join(report_dir, "temporal_cache_quality_report.md")
    _write_quality_report(stats, quality_report_path)
    print(f"[INFO] Quality report saved to {quality_report_path}")


if __name__ == "__main__":
    main()
