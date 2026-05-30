# Current System State

## Scope

The canonical benchmark work lives in `app/benchmarks/` and uses an isolated
external benchmark store. It is adjacent to production retrieval code because
it calls production embedding and selected helper functions, but its benchmark
collections, adapters, evaluation tracks, and `example_id` partitioning are
external-evaluation concerns.

## Production Retrieval Modules

The production regression suite imports these retrieval modules:

| Module | Role in the verified production path |
| --- | --- |
| `app/memory_retriever.py` | Embedding/model and base retrieval dependency |
| `app/hybrid_memory_retriever.py` | Hybrid candidate retrieval dependency |
| `app/adaptive_memory_retriever.py` | Adaptive retrieval path exercised by regression |

The suite does not import `app/benchmarks/clean_hybrid_retriever.py`.

## External Benchmark Modules

| Module | Current purpose |
| --- | --- |
| `app/benchmarks/run_external_benchmark.py` | Thin CLI wrapper for canonical external benchmark execution |
| `app/benchmarks/longmemeval_s_adapter.py` | Legacy and cleaned LongMemEval-S loading/evaluation |
| `app/benchmarks/clean_hybrid_retriever.py` | Benchmark clean-hybrid/temporal/multihop retrieval implementation |
| `app/benchmarks/temporal_query_parser_v2.py` | Multi-event temporal target extraction |
| `app/benchmarks/temporal_multihop_scorer.py` | Event graph pair scoring |
| `app/benchmarks/chroma_smoke_test.py` | Isolated Chroma reliability smoke test |
| `app/retrieval_domain/applications/external_benchmark_runner.py` | Phase 7 application service for CLI workflow orchestration |
| `app/retrieval_domain/applications/retrieval_dispatcher.py` | Phase 7 retrieval-mode dispatch wrapper around existing scoring functions |

See [10_script_inventory.md](./10_script_inventory.md) for complete relevant
classification.

## Changes Made During Benchmark Stabilization

- Added cleaned LongMemEval-S schema handling with strict expected-session ID
  evaluation.
- Added `user_only` and `all_turns` cleaned evaluation tracks.
- Added benchmark-only `example_id` collection query filtering.
- Minimized Chroma metadata and stored source text as document text.
- Switched fresh benchmark collections to `collection.add()` with unique IDs
  and batch count validation.
- Pinned a Python 3.11 / Chroma 0.6.3 isolated benchmark environment.
- Added the `ch_temporal_mh_v2` collection-name alias to stay within Chroma's
  63-character collection identifier limit.
- Added temporal event graph, v2 parser, and pointer foundation work used by
  external benchmark modes.

## What Was Not Changed For The Storage Fix

- No in-memory or parallel retrieval backend was added.
- No production database migration was performed.
- No retrieval scoring weights were changed as part of the Chroma reliability
  stabilization.
- No evaluator logic was changed as part of the Chroma reliability
  stabilization.
- Benchmark Chroma commands were directed to an isolated benchmark persist
  path, not the production path.

## Chroma Compaction Fix Status

The original failure occurred in a Python `3.13.1` / Chroma `1.5.5` benchmark
path while applying metadata segment logs. The stabilized path uses Python
`3.11.9`, `chromadb==0.6.3`, `posthog<3`, a fresh isolated persist directory,
primitive metadata, `add()` ingestion, and batch size `50`.

The smoke test and the final cleaned-500 canonical matrix completed without a
Chroma compaction error. See
[02_canonical_benchmark_environment.md](./02_canonical_benchmark_environment.md).

## Internal Regression Status

The normal internal suite was executed as:

```powershell
python app\full_retrieval_regression_test.py --skip-model-reload --use-existing-index
```

It passed with 65 cases executed. This confirms that the benchmark-only
`example_id` filter is not on the production retrieval import path exercised
by that suite.

## Production Database Caveat

> **Warning:** The production regression suite passed, but Chroma changed
> SQLite bytes during query-only access. Future production validation should
> use a snapshot/copy.

No explicit production add, upsert, delete, or index-build operation was
issued in that validation run. Nevertheless, the production SQLite SHA-256
changed from
`C174AF65274EE1CBA608C860F38EC5DA43555B8C3ED68ACE49F90BC212423731`
to
`AF78F0592BFFF3257A2816A26CA8F5233BE38A1D5F164A6844C9B9CA3538716B`
while the observed last-write timestamp remained unchanged. Later benchmark
work was confined to the isolated external directory.

## Benchmark Integrity Status

Phase 1 removed the clean-hybrid-family path that passed
ground-truth-derived `query_session_id` / `query_evidence_ids` into retrieval.
The corrected cleaned-500 matrix supersedes the earlier pre-integrity 99.0%
`user_only` Recall@5 result.

`app/benchmarks/validate_benchmark_integrity.py` remains a required preflight
and checks the current CLI wrapper, DDD application services, retrieval
dispatcher, and clean-hybrid scoring code.

## Runner Migration Status

Phase 7 reduced `app/benchmarks/run_external_benchmark.py` to a thin CLI and
compatibility wrapper. Benchmark orchestration now lives primarily in:

- `app/retrieval_domain/applications/external_benchmark_runner.py`
- `app/retrieval_domain/applications/retrieval_dispatcher.py`
- `app/retrieval_domain/applications/build_benchmark_index.py`
- `app/retrieval_domain/applications/run_benchmark_suite.py`
- `app/retrieval_domain/applications/evaluate_retrieval_run.py`
- `app/retrieval_domain/applications/generate_benchmark_report.py`

The migration did not change scoring, evaluator metrics, candidate schemas, or
Chroma storage behavior.
