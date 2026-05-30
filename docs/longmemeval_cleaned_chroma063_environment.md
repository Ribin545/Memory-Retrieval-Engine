# Cleaned LongMemEval-S Canonical Benchmark Environment

This document freezes the supported environment for cleaned LongMemEval-S
external evaluation. It is benchmark-only and must not be used to open the
the legacy production Chroma database.

## Required Runtime

| Item | Required Value |
| --- | --- |
| Python | `3.11.9` |
| Dependency file | `app/benchmarks/requirements_chroma063.txt` |
| Chroma | `chromadb==0.6.3` |
| Telemetry compatibility pin | `posthog<3` |
| Persist path | `data/external/indexes/chroma_cleaned_500_py311_chroma063/` |
| Default add batch size | `50` |

Create and populate the environment with Python 3.11.9:

```powershell
py -3.11 -m venv .venv_benchmark_chroma063
.\.venv_benchmark_chroma063\Scripts\python.exe -m pip install -r app\benchmarks\requirements_chroma063.txt
```

## Storage Contract

- Use only `chromadb.PersistentClient` against the benchmark persist path.
- Recreate each fresh benchmark collection before ingestion and use
  `collection.add()`, not `upsert()`.
- Validate unique IDs before add and validate Chroma counts after each batch.
- Fail immediately on any Chroma write, count, or query failure.
- Use `ch_temporal_mh_v2` in collection IDs for
  `clean_hybrid_temporal_multihop_v2` to satisfy Chroma's name-length limit.
- Store `source_text` as document text only.
- Store only these primitive metadata fields:

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

## Evaluation Tracks

| Track | Meaning |
| --- | --- |
| `user_only` | MemPalace-compatible raw apples-to-apples track |
| `all_turns` | richer-context track |

Canonical cleaned-500 reporting covers:

```text
vector_only
clean_hybrid
clean_hybrid_temporal
clean_hybrid_temporal_multihop_v2
```

## Production Isolation

`app/benchmarks/clean_hybrid_retriever.py` is imported only by external
benchmark modules. Its `example_id` Chroma filter partitions candidates inside
the stable external benchmark collection; legacy production retrieval
continues to use `app/memory_retriever.py`,
`app/hybrid_memory_retriever.py`, and `app/adaptive_memory_retriever.py`.

Do not point this environment at `data/protected_legacy_chroma_db/`. The
benchmark runner and Chroma smoke test reject that path.
