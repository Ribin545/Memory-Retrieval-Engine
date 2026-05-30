# Canonical Benchmark Environment

## Required Environment

| Item | Required value |
| --- | --- |
| Python | `3.11.9` |
| Chroma | `chromadb==0.6.3` |
| Telemetry compatibility constraint | `posthog<3` |
| Virtual environment | `.venv_benchmark_chroma063` |
| Requirements file | `app/benchmarks/requirements_chroma063.txt` |
| Isolated persist path | `data/external/indexes/chroma_cleaned_500_py311_chroma063/` |
| Canonical add batch size | `50` |

The frozen source environment document is
[docs/longmemeval_cleaned_chroma063_environment.md](../longmemeval_cleaned_chroma063_environment.md).
The source list requested during documentation referenced an
`outputs/benchmarks/longmemeval_cleaned_chroma063_environment.md` path, but
that file is not present; the document under `docs/` is the current artifact.

## Storage Contract

- Use `ChromaIndexRepository` / `chromadb.PersistentClient` only with the
  isolated benchmark path.
- Create fresh benchmark collections and ingest with `collection.add()`, not
  `upsert()`.
- Use deterministic unique Chroma IDs.
- Validate collection count after each add batch.
- Propagate any write, count, or query failure.
- Keep source text in the Chroma document payload only.
- Do not open an existing store created by an incompatible Chroma version.
- Never point benchmark commands at `data/protected_legacy_chroma_db/`.
- Record benchmark index provenance in `outputs/benchmarks/registry/`.

## Metadata Stored In Chroma

The stable collection ingestion stores only these small primitive metadata
fields:

```text
example_id
memory_id
original_memory_id
session_id
source_session_id
pointer_id
timestamp
memory_unit_type
turns_mode
```

`source_text` is stored as document text, rather than duplicated in metadata.
`MetadataContract` rejects any ground-truth or answer-derived metadata fields,
including `expected_session_ids`, `answer_session_ids`, `expected_evidence`,
`answer`, `answer_text`, `correct_session_id`, `ground_truth`,
`query_session_id`, `query_evidence_ids`, and `_query_evidence_ids`.

## Collection Naming

Canonical collections include benchmark, schema, turns mode, mode, and a
stable suffix. The full string for
`clean_hybrid_temporal_multihop_v2` exceeds Chroma 0.6.3's 63-character
collection-name limit, so storage uses:

```text
ch_temporal_mh_v2
```

This is an identifier alias only; the requested retrieval mode remains
`clean_hybrid_temporal_multihop_v2`.

## Registry Artifacts

Phase 4 writes registry JSON files for benchmark validation runs:

```text
outputs/benchmarks/registry/longmemeval_s_cleaned_user_only_registry.json
outputs/benchmarks/registry/longmemeval_s_cleaned_all_turns_registry.json
```

Each registry records dataset/schema/turns mode, retrieval mode, Python and
Chroma versions, persist path, collection name and alias, batch size, indexed
document count, metadata keys, feature cache paths and hashes, pointer manifest
path, report artifacts, smoke-test status, and Chroma error flags.

Validate with:

```powershell
python app\benchmarks\validate_index_registry.py
```

## Reliability Status

The isolated smoke test created, added, counted, queried, deleted, and
recreated a persistent collection twice, including 1,000-document batched
adds. The final cleaned-500 run produced eight stable benchmark collections,
each with 23,867 documents and no compaction errors.

Evidence:

- [Chroma compaction fix report](../../outputs/benchmarks/chroma_compaction_fix_report.md)
- [Final canonical report](../../outputs/benchmarks/longmemeval_cleaned_chroma063_final_report.md)
- [Final canonical JSON](../../outputs/benchmarks/longmemeval_cleaned_chroma063_final_results.json)
- [Phase 4 index registry report](../../outputs/benchmarks/ddd_phase4_index_registry_report.md)
