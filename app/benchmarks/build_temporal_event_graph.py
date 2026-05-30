"""
Temporal Event Graph Builder for External Benchmarks

Reads the existing temporal cache, builds structured event cards per temporal event,
and creates cross-memory event graph links.

Event cards:
  - event_id, memory_id, session_id, source_doc_id
  - event_sentence, event_verb, event_object, entities
  - date_text, normalized_date, document_timestamp
  - confidence

Graph links:
  - same_entity: events share a PERSON/ORG/GPE entity
  - same_object: events share the same event_object or verb
  - same_topic: events share >2 content words
  - date_ordering: event_a.timestamp < event_b.timestamp
  - same_session: events belong to the same memory_id

Output: data/external/indexes/longmemeval_s_temporal_event_graph.json
"""
import os
import sys
import json
import argparse
import time
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.retrieval_domain.features.grammar_frame_extractor import _ensure_nlp_loaded


def _extract_fields_from_doc(doc) -> Dict[str, Any]:
    """Parse a spaCy doc to extract verb, object, entities."""
    if not doc:
        return {"event_verb": "", "event_object": "", "entities": []}

    # Extract verb: prefer ROOT verb, or first VERB
    event_verb = ""
    root = next((t for t in doc if t.dep_ == "ROOT"), None)
    if root and root.pos_ in {"VERB", "AUX"}:
        event_verb = getattr(root, "lemma_", root.text.lower())
    else:
        for token in doc:
            if token.pos_ == "VERB":
                event_verb = getattr(token, "lemma_", token.text.lower())
                break

    # Extract object: dobj or pobj of the verb
    event_object = ""
    if root and root.pos_ in {"VERB", "AUX"}:
        for child in root.children:
            if child.dep_ in {"dobj", "attr", "oprd"}:
                compounds = [t.text.lower() for t in child.children if t.dep_ == "compound" and t.i < child.i]
                event_object = "_".join(compounds + [child.text.lower()])
                break
        if not event_object:
            for child in root.children:
                if child.dep_ == "prep":
                    pobj = next((t for t in child.children if t.dep_ in {"pobj", "pcomp"}), None)
                    if pobj:
                        compounds = [t.text.lower() for t in pobj.children if t.dep_ == "compound" and t.i < pobj.i]
                        event_object = "_".join(compounds + [pobj.text.lower()])
                        break

    # Extract entities
    entities = []
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "NORP", "PRODUCT", "WORK_OF_ART", "EVENT"}:
            ent_text = ent.text.lower().replace(" ", "_")
            if ent_text not in entities:
                entities.append(ent_text)

    return {
        "event_verb": event_verb,
        "event_object": event_object,
        "entities": entities,
    }


def _build_event_cards(
    temporal_cache: Dict[str, Any],
    nlp=None,
) -> Tuple[Dict[str, Any], Dict[str, List[str]], int]:
    """Build flat event cards from temporal cache entries using batched spaCy processing."""
    event_cards: Dict[str, Any] = {}
    events_by_memory: Dict[str, List[str]] = defaultdict(list)

    # Collect all event records first
    event_records: List[Dict[str, Any]] = []
    total_events = 0
    for memory_id, entry in temporal_cache.items():
        temporal_events = entry.get("temporal_events", [])
        for idx, evt in enumerate(temporal_events):
            event_id = f"{memory_id}_evt_{idx}"
            event_span = evt.get("event_span", "")
            event_sentence = event_span.replace("...", "").strip()

            # Confidence based on normalization success
            confidence = 0.5
            if evt.get("normalized_date"):
                confidence = 0.9
            elif evt.get("event_type") == "verb":
                confidence = 0.7
            elif evt.get("event_type") == "noun":
                confidence = 0.6

            event_records.append({
                "event_id": event_id,
                "memory_id": memory_id,
                "session_id": entry.get("session_id", ""),
                "source_doc_id": memory_id.rsplit("_doc_", 1)[0] if "_doc_" in memory_id else memory_id,
                "event_sentence": event_sentence,
                "date_text": evt.get("date_text", ""),
                "normalized_date": evt.get("normalized_date"),
                "document_timestamp": entry.get("document_timestamp"),
                "confidence": confidence,
                "span_text": event_span,
            })
            total_events += 1

    # Batch-process all event spans with spaCy
    if nlp and event_records:
        spans = [r["span_text"] for r in event_records]
        print(f"[INFO] Processing {len(spans)} event spans with spaCy (batch_size=64)...")
        parsed_fields = []
        for doc in nlp.pipe(spans, batch_size=64):
            parsed_fields.append(_extract_fields_from_doc(doc))
        print(f"[INFO] spaCy processing complete.")

        for i, record in enumerate(event_records):
            parsed = parsed_fields[i]
            event_id = record["event_id"]
            memory_id = record["memory_id"]
            card = {
                "event_id": event_id,
                "memory_id": memory_id,
                "session_id": record["session_id"],
                "source_doc_id": record["source_doc_id"],
                "event_sentence": record["event_sentence"],
                "event_verb": parsed["event_verb"],
                "event_object": parsed["event_object"],
                "entities": parsed["entities"],
                "date_text": record["date_text"],
                "normalized_date": record["normalized_date"],
                "document_timestamp": record["document_timestamp"],
                "confidence": record["confidence"],
            }
            event_cards[event_id] = card
            events_by_memory[memory_id].append(event_id)
    else:
        # No spaCy: create cards with empty parsed fields
        for record in event_records:
            event_id = record["event_id"]
            memory_id = record["memory_id"]
            card = {
                "event_id": event_id,
                "memory_id": memory_id,
                "session_id": record["session_id"],
                "source_doc_id": record["source_doc_id"],
                "event_sentence": record["event_sentence"],
                "event_verb": "",
                "event_object": "",
                "entities": [],
                "date_text": record["date_text"],
                "normalized_date": record["normalized_date"],
                "document_timestamp": record["document_timestamp"],
                "confidence": record["confidence"],
            }
            event_cards[event_id] = card
            events_by_memory[memory_id].append(event_id)

    return event_cards, dict(events_by_memory), total_events


def _build_event_links(
    event_cards: Dict[str, Any],
    events_by_memory: Dict[str, List[str]],
) -> List[Dict[str, Any]]:
    """Build cross-event links."""
    links: List[Dict[str, Any]] = []

    # Index events by session and source_doc for locality pruning
    events_by_session: Dict[str, List[str]] = defaultdict(list)
    events_by_doc: Dict[str, List[str]] = defaultdict(list)
    for eid, card in event_cards.items():
        events_by_session[card["session_id"]].append(eid)
        events_by_doc[card["source_doc_id"]].append(eid)

    # Build a set of event IDs per memory for same_session links
    memory_event_sets = {mid: set(eids) for mid, eids in events_by_memory.items()}

    # Pre-compute content words for same_topic detection
    content_words: Dict[str, Set[str]] = {}
    for eid, card in event_cards.items():
        words = set()
        sent = card.get("event_sentence", "").lower()
        # Simple word extraction (nouns/verbs from sentence)
        for w in sent.split():
            w = w.strip(".,;:!?\"'")
            if len(w) > 2 and w.isalpha():
                words.add(w)
        content_words[eid] = words

    # Track pairs we've already linked to avoid duplicates
    linked_pairs: Set[str] = set()

    def _add_link(eid_a: str, eid_b: str, link_type: str, weight: float, **kwargs):
        key = tuple(sorted([eid_a, eid_b]))
        if key in linked_pairs:
            return
        linked_pairs.add(key)
        link = {
            "event_a": eid_a,
            "event_b": eid_b,
            "link_type": link_type,
            "weight": round(weight, 3),
        }
        link.update(kwargs)
        links.append(link)

    # Iterate over all event pairs within the same source document
    # (LongMemEval examples are isolated per user; cross-example links are not useful)
    for doc_id, doc_events in events_by_doc.items():
        doc_event_list = doc_events
        n = len(doc_event_list)
        for i in range(n):
            eid_a = doc_event_list[i]
            card_a = event_cards[eid_a]
            for j in range(i + 1, n):
                eid_b = doc_event_list[j]
                card_b = event_cards[eid_b]

                # same_session
                if card_a["memory_id"] == card_b["memory_id"]:
                    _add_link(eid_a, eid_b, "same_session", 0.5)

                # same_entity
                shared_entities = set(card_a.get("entities", [])) & set(card_b.get("entities", []))
                if shared_entities:
                    _add_link(eid_a, eid_b, "same_entity", 1.0, entity=list(shared_entities)[0])

                # same_object
                obj_a = card_a.get("event_object", "")
                obj_b = card_b.get("event_object", "")
                if obj_a and obj_b and obj_a == obj_b:
                    _add_link(eid_a, eid_b, "same_object", 0.8)

                # same_verb
                verb_a = card_a.get("event_verb", "")
                verb_b = card_b.get("event_verb", "")
                if verb_a and verb_b and verb_a == verb_b:
                    _add_link(eid_a, eid_b, "same_verb", 0.6)

                # same_topic (>2 shared content words)
                words_a = content_words.get(eid_a, set())
                words_b = content_words.get(eid_b, set())
                shared_words = words_a & words_b
                if len(shared_words) >= 2:
                    _add_link(eid_a, eid_b, "same_topic", min(0.7, 0.3 + 0.1 * len(shared_words)))

                # date_ordering
                ts_a = card_a.get("document_timestamp")
                ts_b = card_b.get("document_timestamp")
                if ts_a and ts_b:
                    if ts_a < ts_b:
                        _add_link(eid_a, eid_b, "date_ordering", 1.0, relation="before")
                    elif ts_b < ts_a:
                        _add_link(eid_a, eid_b, "date_ordering", 1.0, relation="after")

    return links


def build_temporal_event_graph(temporal_cache: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build event cards + event graph from temporal cache.

    Returns:
        {
            "event_cards": {event_id: {...}, ...},
            "events_by_memory": {memory_id: [event_id, ...], ...},
            "links": [{"event_a": ..., "event_b": ..., "link_type": ..., "weight": ...}, ...],
            "stats": {...},
        }
    """
    print("[INFO] Loading spaCy model...")
    nlp = _ensure_nlp_loaded()
    if nlp and nlp is not False:
        print("[INFO] spaCy model loaded.")
    else:
        print("[WARN] spaCy unavailable; event cards will have empty verb/object fields.")

    print("[INFO] Building temporal event cards...")
    t0 = time.time()
    event_cards, events_by_memory, total_events = _build_event_cards(temporal_cache, nlp=nlp)
    card_time = time.time() - t0
    print(f"[INFO] Built {len(event_cards)} event cards from {len(temporal_cache)} memory units ({card_time:.1f}s)")

    print("[INFO] Building event graph links...")
    t0 = time.time()
    links = _build_event_links(event_cards, events_by_memory)
    link_time = time.time() - t0
    print(f"[INFO] Built {len(links)} event links ({link_time:.1f}s)")

    # Compute stats
    link_type_counts = defaultdict(int)
    for link in links:
        link_type_counts[link["link_type"]] += 1

    normalized_count = sum(1 for c in event_cards.values() if c.get("normalized_date"))

    stats = {
        "memory_units": len(temporal_cache),
        "total_events": total_events,
        "event_cards": len(event_cards),
        "total_links": len(links),
        "links_by_type": dict(link_type_counts),
        "normalized_date_coverage": round(normalized_count / len(event_cards), 3) if event_cards else 0.0,
        "card_build_time_s": round(card_time, 2),
        "link_build_time_s": round(link_time, 2),
    }

    return {
        "event_cards": event_cards,
        "events_by_memory": events_by_memory,
        "links": links,
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(description="Build Temporal Event Graph for External Benchmarks")
    parser.add_argument("--benchmark", type=str, required=True, choices=["longmemeval_s", "locomo"])
    parser.add_argument("--temporal-cache-path", type=str, required=True)
    parser.add_argument("--output-dir", type=str, default="data/external/indexes")
    parser.add_argument("--limit", type=int, default=None, help="Limit memory units processed (for debugging)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"[INFO] Loading temporal cache from {args.temporal_cache_path}...")
    with open(args.temporal_cache_path, "r", encoding="utf-8") as f:
        temporal_cache = json.load(f)
    print(f"[INFO] Loaded {len(temporal_cache)} cache entries.")

    if args.limit:
        # Take first N entries
        limited = dict(list(temporal_cache.items())[:args.limit])
        print(f"[INFO] Limiting to {args.limit} entries for debugging.")
        temporal_cache = limited

    print(f"[INFO] Building temporal event graph for {args.benchmark}...")
    graph = build_temporal_event_graph(temporal_cache)

    output_filename = f"{args.benchmark}_temporal_event_graph.json"
    output_path = os.path.join(args.output_dir, output_filename)

    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, output_path)

    print(f"[INFO] Temporal event graph saved to {output_path}")
    print(f"[INFO] Stats: {json.dumps(graph['stats'], indent=2)}")

    # Write report
    report_dir = "outputs/benchmarks"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "temporal_event_graph_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Temporal Event Graph Report\n\n")
        f.write(f"- **Benchmark:** {args.benchmark}\n")
        f.write(f"- **Memory units:** {graph['stats']['memory_units']}\n")
        f.write(f"- **Event cards:** {graph['stats']['event_cards']}\n")
        f.write(f"- **Total links:** {graph['stats']['total_links']}\n")
        f.write(f"- **Normalized date coverage:** {graph['stats']['normalized_date_coverage'] * 100:.1f}%\n")
        f.write(f"- **Card build time:** {graph['stats']['card_build_time_s']:.1f}s\n")
        f.write(f"- **Link build time:** {graph['stats']['link_build_time_s']:.1f}s\n")
        f.write("\n## Links by Type\n\n")
        for lt, cnt in sorted(graph["stats"]["links_by_type"].items(), key=lambda x: -x[1]):
            f.write(f"- {lt}: {cnt}\n")
    print(f"[INFO] Report saved to {report_path}")


if __name__ == "__main__":
    main()
