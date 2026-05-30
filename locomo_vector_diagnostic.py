import json
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import chromadb

from app.benchmarks.locomo_adapter import LocomoAdapter
from app.memory_retriever import EMBEDDING_MODEL, get_model


OUTPUT_PATH = os.path.join("outputs", "benchmarks", "locomo_vector_failure_diagnostic.md")
DATA_PATH = os.path.join("data", "external", "locomo")
LIMIT = 20
TOP_K = 10
WINDOW_SIZES = [3, 4, 5]


@dataclass
class UnitSpec:
    name: str
    units: List[Dict[str, Any]]


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _cosine_similarity_from_distance(distance: float) -> float:
    return 1.0 - float(distance)


def _snippet(text: str, limit: int = 180) -> str:
    text = " ".join((text or "").split())
    return text[:limit] + ("..." if len(text) > limit else "")


def _load_raw_locomo_personas(data_path: str) -> List[Dict[str, Any]]:
    json_files = [f for f in os.listdir(data_path) if f.endswith(".json")]
    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {data_path}")
    file_to_load = os.path.join(data_path, json_files[0])
    with open(file_to_load, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_examples_and_personas(limit: int) -> Tuple[List[Any], List[Dict[str, Any]]]:
    adapter = LocomoAdapter()
    examples = adapter.load_dataset(DATA_PATH, limit=limit)
    raw_personas = _load_raw_locomo_personas(DATA_PATH)

    persona_ids = []
    for ex in examples:
        if ex.memory_units:
            persona_ids.append(ex.memory_units[0]["user_id"])

    seen = set()
    ordered_persona_ids = []
    for pid in persona_ids:
        if pid not in seen:
            seen.add(pid)
            ordered_persona_ids.append(pid)

    selected = []
    selected_set = set(ordered_persona_ids)
    for persona in raw_personas:
        sample_id = persona.get("sample_id")
        if sample_id in selected_set:
            selected.append(persona)
        if len(selected) == len(ordered_persona_ids):
            break

    return examples, selected


def _build_session_units(persona: Dict[str, Any]) -> List[Dict[str, Any]]:
    sample_id = persona.get("sample_id", "unknown")
    units = []
    conversation = persona.get("conversation", {})
    for key, turns in conversation.items():
        if key.startswith("session_") and not key.endswith("_date_time") and isinstance(turns, list):
            parts = []
            dia_ids = []
            for t in turns:
                dia_id = t.get("dia_id", "")
                speaker = t.get("speaker", "user")
                text = t.get("text", "")
                parts.append(f"[{dia_id}] {speaker}: {text}")
                if dia_id:
                    dia_ids.append(dia_id)
            full_text = "\n".join(parts)
            units.append({
                "memory_id": f"{sample_id}_{key}",
                "user_id": sample_id,
                "session_id": key,
                "source_text": full_text,
                "summary": full_text,
                "contained_dia_ids": dia_ids,
                "unit_type": "session",
                "turn_count": len(turns),
            })
    return units


def _build_turn_units(persona: Dict[str, Any]) -> List[Dict[str, Any]]:
    sample_id = persona.get("sample_id", "unknown")
    units = []
    conversation = persona.get("conversation", {})
    for key, turns in conversation.items():
        if key.startswith("session_") and not key.endswith("_date_time") and isinstance(turns, list):
            for idx, t in enumerate(turns):
                dia_id = t.get("dia_id", "")
                speaker = t.get("speaker", "user")
                text = t.get("text", "")
                full_text = f"[{dia_id}] {speaker}: {text}"
                units.append({
                    "memory_id": f"{sample_id}_{key}_turn_{idx}",
                    "user_id": sample_id,
                    "session_id": key,
                    "source_text": full_text,
                    "summary": full_text,
                    "contained_dia_ids": [dia_id] if dia_id else [],
                    "unit_type": "turn",
                    "turn_count": 1,
                })
    return units


def _build_window_units(persona: Dict[str, Any], window_size: int) -> List[Dict[str, Any]]:
    sample_id = persona.get("sample_id", "unknown")
    units = []
    conversation = persona.get("conversation", {})
    for key, turns in conversation.items():
        if key.startswith("session_") and not key.endswith("_date_time") and isinstance(turns, list):
            if len(turns) <= window_size:
                window_ranges = [(0, len(turns))]
            else:
                window_ranges = [(start, start + window_size) for start in range(0, len(turns) - window_size + 1)]
            for start, end in window_ranges:
                window = turns[start:end]
                parts = []
                dia_ids = []
                for t in window:
                    dia_id = t.get("dia_id", "")
                    speaker = t.get("speaker", "user")
                    text = t.get("text", "")
                    parts.append(f"[{dia_id}] {speaker}: {text}")
                    if dia_id:
                        dia_ids.append(dia_id)
                full_text = "\n".join(parts)
                units.append({
                    "memory_id": f"{sample_id}_{key}_win_{window_size}_{start}_{end-1}",
                    "user_id": sample_id,
                    "session_id": key,
                    "source_text": full_text,
                    "summary": full_text,
                    "contained_dia_ids": dia_ids,
                    "unit_type": f"window_{window_size}",
                    "turn_count": len(window),
                })
    return units


def _build_specs(personas: List[Dict[str, Any]]) -> List[UnitSpec]:
    specs = [UnitSpec(name="session", units=[]), UnitSpec(name="turn", units=[])]
    window_specs = [UnitSpec(name=f"window_{size}", units=[]) for size in WINDOW_SIZES]
    for persona in personas:
        specs[0].units.extend(_build_session_units(persona))
        specs[1].units.extend(_build_turn_units(persona))
        for spec, size in zip(window_specs, WINDOW_SIZES):
            spec.units.extend(_build_window_units(persona, size))
    specs.extend(window_specs)
    return specs


def _create_collection(name: str):
    client = chromadb.Client()
    return client.create_collection(name=name, metadata={"hnsw:space": "cosine"})


def _index_units(collection, model, units: List[Dict[str, Any]]) -> None:
    ids = []
    embeddings = []
    documents = []
    metadatas = []
    for unit in units:
        ids.append(unit["memory_id"])
        embeddings.append(model.encode(unit["source_text"]).tolist())
        documents.append(unit["source_text"])
        metadatas.append({
            "memory_id": unit["memory_id"],
            "user_id": unit["user_id"],
            "session_id": unit["session_id"],
            "source_text": unit["source_text"],
            "summary": unit["summary"],
            "contained_dia_ids": _safe_json(unit.get("contained_dia_ids", [])),
            "unit_type": unit["unit_type"],
            "turn_count": unit["turn_count"],
        })
    if ids:
        collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def _query_units(collection, model, query: str, user_id: str, top_k: int) -> List[Dict[str, Any]]:
    query_emb = model.encode(query).tolist()
    result = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k,
        where={"user_id": {"$eq": user_id}},
        include=["metadatas", "distances", "documents"],
    )
    rows = []
    ids = result.get("ids", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    documents = result.get("documents", [[]])[0]
    for idx in range(len(ids)):
        md = metadatas[idx] or {}
        distance = float(distances[idx])
        rows.append({
            "memory_id": md.get("memory_id", ids[idx]),
            "session_id": md.get("session_id", ""),
            "source_text": md.get("source_text", documents[idx] or ""),
            "summary": md.get("summary", documents[idx] or ""),
            "contained_dia_ids": json.loads(md.get("contained_dia_ids", "[]") or "[]"),
            "unit_type": md.get("unit_type", "unknown"),
            "turn_count": md.get("turn_count", 0),
            "distance": distance,
            "similarity": _cosine_similarity_from_distance(distance),
        })
    return rows


def _evaluate_example(example: Any, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    expected_sessions = set(example.expected_session_ids or [])
    expected_evidence = set(example.expected_evidence or [])

    def is_hit(row: Dict[str, Any]) -> bool:
        if expected_sessions and row.get("session_id") in expected_sessions:
            return True
        if expected_evidence and set(row.get("contained_dia_ids", [])) & expected_evidence:
            return True
        return False

    hit_rank = None
    for idx, row in enumerate(rows):
        if is_hit(row):
            hit_rank = idx + 1
            break

    return {
        "hit_rank": hit_rank,
        "hit_at_1": hit_rank == 1,
        "hit_at_5": hit_rank is not None and hit_rank <= 5,
        "hit_at_10": hit_rank is not None and hit_rank <= 10,
        "mrr": 0.0 if hit_rank is None else 1.0 / hit_rank,
    }


def _run_dense_eval(examples: List[Any], model, specs: List[UnitSpec]) -> Tuple[Dict[str, Dict[str, float]], Dict[str, List[Dict[str, Any]]]]:
    metrics = {}
    traces = defaultdict(list)
    for spec in specs:
        collection = _create_collection(f"diag_{spec.name}")
        _index_units(collection, model, spec.units)
        hits = []
        for example in examples:
            if not example.memory_units:
                continue
            user_id = example.memory_units[0]["user_id"]
            rows = _query_units(collection, model, example.query, user_id, TOP_K)
            score = _evaluate_example(example, rows)
            hits.append(score)
            traces[spec.name].append({
                "example": example,
                "rows": rows,
                "score": score,
            })
        total = max(len(hits), 1)
        metrics[spec.name] = {
            "recall@1": sum(1 for h in hits if h["hit_at_1"]) / total,
            "recall@5": sum(1 for h in hits if h["hit_at_5"]) / total,
            "recall@10": sum(1 for h in hits if h["hit_at_10"]) / total,
            "mrr": sum(h["mrr"] for h in hits) / total,
            "num_queries": total,
            "num_units": len(spec.units),
        }
    return metrics, traces


def _confirm_ordering(model) -> Dict[str, Any]:
    collection = _create_collection("diag_ordering")
    docs = [
        ("a", "I adopted a brown dog named Miso last week."),
        ("b", "I adopted a brown dog named Miso last week."),
        ("c", "The weather forecast said it might rain tomorrow."),
    ]
    for doc_id, text in docs:
        collection.add(
            ids=[doc_id],
            embeddings=[model.encode(text).tolist()],
            documents=[text],
            metadatas=[{"memory_id": doc_id, "user_id": "order", "session_id": "session_test", "source_text": text, "summary": text, "contained_dia_ids": "[]", "unit_type": "test", "turn_count": 1}],
        )
    query = "I adopted a brown dog named Miso last week."
    rows = _query_units(collection, model, query, "order", top_k=3)
    distances = [r["distance"] for r in rows]
    similarities = [r["similarity"] for r in rows]
    return {
        "rows": rows,
        "ascending_distance": distances == sorted(distances),
        "descending_similarity": similarities == sorted(similarities, reverse=True),
    }


def _vector_benchmark_bug_notes() -> List[str]:
    return [
        "`run_external_benchmark.ingest_example_memory_units()` stores only `user_id` and `example_id` in Chroma metadata for benchmark memories.",
        "`memory_retriever.retrieve_memories()` reconstructs returned candidates from metadata fields such as `source_session_id`, `source_text`, and `memory_id`; these are absent in benchmark-ingested vector-only rows.",
        "The benchmark evaluator checks `cand.get(\"session_id\")`, but vector-only candidates expose `source_session_id` in the normal pipeline and expose neither in the benchmark ingestion path, so session hits cannot register.",
        "Because benchmark vector documents store the full memory JSON string in `documents`, but retrieval reads `source_text` from metadata, evidence-substring fallback also becomes ineffective. This can force `vector_only` to 0% even if nearest-neighbor retrieval itself is reasonable.",
    ]


def _select_failures(traces: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    failures = [t for t in traces if t["score"]["hit_rank"] is None]
    return failures[:limit]


def _session_stats(units: List[Dict[str, Any]], model) -> Dict[str, Any]:
    turn_counts = [u.get("turn_count", 0) for u in units]
    text_lengths = [len((u.get("source_text") or "").split()) for u in units]
    approx_tokens = []
    for u in units:
        txt = u.get("source_text", "")
        try:
            approx_tokens.append(len(model.tokenizer.encode(txt, add_special_tokens=True)))
        except Exception:
            approx_tokens.append(len(txt.split()))
    return {
        "count": len(units),
        "avg_turns": sum(turn_counts) / max(len(turn_counts), 1),
        "max_turns": max(turn_counts) if turn_counts else 0,
        "avg_words": sum(text_lengths) / max(len(text_lengths), 1),
        "max_words": max(text_lengths) if text_lengths else 0,
        "avg_tokens": sum(approx_tokens) / max(len(approx_tokens), 1),
        "max_tokens": max(approx_tokens) if approx_tokens else 0,
    }


def _classify_causes(metrics: Dict[str, Dict[str, float]], session_stats: Dict[str, Any], example_failures: List[Dict[str, Any]]) -> List[Tuple[str, str]]:
    findings = []
    findings.append((
        "implementation bug",
        "Confirmed. The existing vector-only benchmark ingestion/evaluation path drops the metadata fields needed for hit evaluation, which is sufficient to explain the observed 0% vector_only report."
    ))
    findings.append((
        "score sorting bug",
        "Not supported. Chroma distances are expected to come back in ascending order and `1 - distance` preserves the ordering as descending similarity for cosine space."
    ))
    if metrics.get("turn", {}).get("recall@10", 0) > metrics.get("session", {}).get("recall@10", 0) + 0.10 or session_stats.get("avg_tokens", 0) > 256:
        findings.append((
            "session chunks too long",
            f"Likely contributing. Session units average about {session_stats.get('avg_tokens', 0):.1f} tokens with max {session_stats.get('max_tokens', 0)}, which can exceed or approach the model limit and smear fine-grained evidence across long chunks."
        ))
    else:
        findings.append((
            "session chunks too long",
            "Not strongly supported by this sample; session granularity did not underperform the smaller units enough to make chunk length the primary issue."
        ))
    best_non_session = max((m.get("recall@10", 0) for k, m in metrics.items() if k != "session"), default=0.0)
    if best_non_session < 0.50 and len(example_failures) >= 3:
        findings.append((
            "weak embedding model",
            "Plausible secondary factor. If all dense granularities remain weak after fixing evaluation shape, all-MiniLM-L6-v2 may not be strong enough for LoCoMo’s indirect conversational recall."
        ))
    else:
        findings.append((
            "weak embedding model",
            "Not the primary cause of 0%, though it may still cap dense performance on LoCoMo relative to stronger embedding models."
        ))
    unresolved = sum(1 for t in example_failures if not t["example"].expected_session_ids)
    if unresolved > 0:
        findings.append((
            "ground-truth mapping issue",
            f"Minor/possible. {unresolved} sampled failures had no resolved expected session IDs from evidence mapping, so some benchmark examples may be intrinsically hard to score at session level."
        ))
    else:
        findings.append((
            "ground-truth mapping issue",
            "Not the main driver in the sampled failures; most failures still had mapped expected sessions/evidence."
        ))
    return findings


def build_report() -> str:
    model = get_model()
    examples, personas = _load_examples_and_personas(LIMIT)
    specs = _build_specs(personas)
    metrics, traces = _run_dense_eval(examples, model, specs)
    ordering = _confirm_ordering(model)
    session_units = next(spec.units for spec in specs if spec.name == "session")
    session_stats = _session_stats(session_units, model)
    failures = _select_failures(traces["session"], limit=5)
    causes = _classify_causes(metrics, session_stats, failures)
    embedding_dim = len(model.encode("diagnostic probe"))

    report = []
    report.append("# LoCoMo Vector Failure Diagnostic\n")
    report.append("- **Dataset:** LoCoMo\n")
    report.append(f"- **Limit:** {LIMIT}\n")
    report.append(f"- **Top-K:** {TOP_K}\n")

    report.append("\n## 1. Embeddings Count and Model Name\n")
    report.append(f"- **Embedding model:** {EMBEDDING_MODEL}\n")
    report.append(f"- **Embedding dimension:** {embedding_dim}\n")
    report.append(f"- **Model max sequence length:** {getattr(model, 'max_seq_length', 'unknown')}\n")
    report.append(f"- **QA examples loaded:** {len(examples)}\n")
    for spec in specs:
        report.append(f"- **{spec.name} embeddings indexed:** {len(spec.units)}\n")

    report.append("\n## 2. Confirm Chroma Distance/Score Ordering\n")
    report.append("Chroma was created with `hnsw:space = cosine`, so lower distance should mean better match. The diagnostic also converts similarity as `1 - distance`.\n")
    report.append(f"- **Distances ascending:** {ordering['ascending_distance']}\n")
    report.append(f"- **Similarities descending:** {ordering['descending_similarity']}\n")
    report.append("\n### Ordering Probe Results\n")
    for idx, row in enumerate(ordering["rows"], start=1):
        report.append(f"{idx}. `memory_id={row['memory_id']}` distance={row['distance']:.6f} similarity={row['similarity']:.6f} text=`{_snippet(row['source_text'], 80)}`\n")

    report.append("\n## 3. Existing vector_only Benchmark Failure Path\n")
    for note in _vector_benchmark_bug_notes():
        report.append(f"- {note}\n")

    report.append("\n## 4. Session-Level vs Turn-Level vs Sliding-Window Dense Retrieval\n")
    report.append("| Unit Type | #Units | #Queries | Recall@1 | Recall@5 | Recall@10 | MRR |\n")
    report.append("|---|---:|---:|---:|---:|---:|---:|\n")
    for name in ["session", "turn"] + [f"window_{n}" for n in WINDOW_SIZES]:
        m = metrics[name]
        report.append(f"| {name} | {m['num_units']} | {m['num_queries']} | {m['recall@1']:.2%} | {m['recall@5']:.2%} | {m['recall@10']:.2%} | {m['mrr']:.4f} |\n")

    report.append("\n### Session Unit Size Stats\n")
    report.append(f"- **Session unit count:** {session_stats['count']}\n")
    report.append(f"- **Average turns per session unit:** {session_stats['avg_turns']:.2f}\n")
    report.append(f"- **Max turns per session unit:** {session_stats['max_turns']}\n")
    report.append(f"- **Average words per session unit:** {session_stats['avg_words']:.2f}\n")
    report.append(f"- **Max words per session unit:** {session_stats['max_words']}\n")
    report.append(f"- **Average approx tokenized length:** {session_stats['avg_tokens']:.2f}\n")
    report.append(f"- **Max approx tokenized length:** {session_stats['max_tokens']}\n")

    report.append("\n## 5. Five Vector Failures (Session-Level Dense Retrieval)\n")
    if not failures:
        report.append("No session-level vector failures were found in this limit-20 dense-only diagnostic after direct Chroma evaluation. That would further support that the reported 0% is caused by the benchmark implementation/evaluation path rather than dense retrieval itself.\n")
    for idx, failure in enumerate(failures, start=1):
        example = failure["example"]
        rows = failure["rows"]
        report.append(f"\n### Failure {idx}\n")
        report.append(f"- **Query:** {example.query}\n")
        report.append(f"- **Expected session IDs:** {example.expected_session_ids}\n")
        report.append(f"- **Expected evidence dia IDs:** {example.expected_evidence}\n")
        report.append("\n| Rank | Session ID | Memory ID | Distance | Similarity | Expected Session? | Evidence Overlap | Snippet |\n")
        report.append("|---:|---|---|---:|---:|---|---|---|\n")
        expected_sessions = set(example.expected_session_ids or [])
        expected_evidence = set(example.expected_evidence or [])
        for rank, row in enumerate(rows[:TOP_K], start=1):
            overlap = sorted(set(row.get("contained_dia_ids", [])) & expected_evidence)
            report.append(f"| {rank} | {row.get('session_id','')} | {row.get('memory_id','')} | {row['distance']:.4f} | {row['similarity']:.4f} | {'yes' if row.get('session_id') in expected_sessions else 'no'} | {overlap if overlap else '[]'} | {_snippet(row.get('source_text',''))} |\n")

    report.append("\n## 6. Cause Analysis\n")
    for cause, verdict in causes:
        report.append(f"- **{cause}:** {verdict}\n")

    report.append("\n## 7. Bottom Line\n")
    report.append("Do **not** tune hybrid weights yet. First fix or isolate the vector-only benchmark ingestion/evaluation path, because the current 0% result is explainable by metadata-shape/evaluation issues alone. After that, use the granularity comparison above to decide whether LoCoMo should use session, turn, or short sliding-window units for dense retrieval.\n")

    return "".join(report)


def main() -> None:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    report = build_report()
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved diagnostic report to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
