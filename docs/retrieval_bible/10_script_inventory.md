# Relevant Script Inventory

## Classification Rules

| Status | Meaning |
| --- | --- |
| Canonical | Directly implements or validates the frozen cleaned-500 benchmark path |
| Supporting | Builds inputs, caches, provenance, or reports used by canonical work |
| Experimental | Relevant research path not adopted as the canonical final matrix |
| Legacy | Historical path retained for reproducibility or prior diagnostics |
| Archived / Legacy | Historical script moved to `app/benchmarks/archive/`; preserved, not active |
| Quarantined / Non-retrieval | Removed from active codebase into `app/archive_non_retrieval/` or `archive_non_retrieval/`; preserved, not active |
| Archive candidate | Useful record but not a preferred active entry point |
| Unknown / needs review | Relevance is visible but current compatibility or intended ownership is unclear |

## Inventory

| File path | Purpose | Status | Used by which mode | Safe to refactor later? | Notes |
| --- | --- | --- | --- | --- | --- |
| `app/benchmarks/run_external_benchmark.py` | Thin CLI wrapper and compatibility exports for the canonical external benchmark runner | Canonical | All four canonical modes | Yes | Phase 7 moved orchestration into DDD application services; keeps legacy import names for validators/scripts |
| `app/benchmarks/longmemeval_s_adapter.py` | Thin compatibility wrapper for LongMemEval-S adapter imports | Canonical | All canonical LongMemEval-S modes | Yes | Phase 8 moved mapping into Dataset Context adapters |
| `app/benchmarks/external_benchmark_adapter.py` | Shared benchmark example/result data classes and base evaluator | Canonical | All adapter-driven modes | Needs review | Boundary between cleaned strict evaluator and base behavior matters |
| `app/benchmarks/clean_hybrid_retriever.py` | Fixed-weight external hybrid, temporal, multihop scoring | Canonical | `clean_hybrid`, `clean_hybrid_temporal`, `clean_hybrid_temporal_multihop_v2` | Needs review | Benchmark-only; metadata scoring no longer consumes expected session/evidence IDs |
| `app/benchmarks/validate_benchmark_integrity.py` | Static guard against ground-truth leakage into retrieval scoring | Canonical | Benchmark validation | Yes | Fails if clean-hybrid request/scoring accepts expected session/evidence hints; allows `example_id` haystack filtering |
| `app/benchmarks/chroma_smoke_test.py` | Persistent Chroma reliability validation | Canonical | Storage validation | Yes | Rejects production and legacy benchmark directories |
| `app/benchmarks/clear_benchmark_chroma.py` | Clears only the isolated cleaned-500 benchmark Chroma persist directory | Canonical | Benchmark preflight/storage cleanup | Yes | Use before validation reruns to shrink deleted Chroma collections and avoid disk-full failures; refuses production path |
| `app/benchmarks/requirements_chroma063.txt` | Pinned isolated benchmark dependencies | Canonical | Environment | Yes | Python 3.11.9 required in accompanying doc |
| `app/retrieval_domain/*.py` | Lightweight Phase 1 DDD contracts for Dataset, Retrieval, Evaluation, and Storage | Supporting | Future refactor boundary contracts | Yes | Not a runner; introduced without changing current retrieval behavior |
| `app/retrieval_domain/applications/build_benchmark_index.py` | Phase 2 application service for isolated Chroma setup, collection naming, fresh add ingestion, primitive metadata, and count validation | Supporting | Canonical cleaned benchmark orchestration | Yes | Extracted from runner; still calls existing embedding/indexing helpers and rejects production paths |
| `app/retrieval_domain/applications/run_benchmark_suite.py` | Phase 2 application service for retrieval/evaluation loop orchestration | Supporting | Canonical cleaned benchmark orchestration | Yes | Calls existing `run_retrieval` and adapter evaluator; does not score candidates itself |
| `app/retrieval_domain/applications/evaluate_retrieval_run.py` | Phase 2 application service for adapter evaluation calls, metric summarization, and diagnostics attachment | Supporting | Canonical cleaned benchmark orchestration | Yes | Uses ground truth only through existing evaluator after retrieval returns |
| `app/retrieval_domain/applications/generate_benchmark_report.py` | Phase 2 application service for Markdown/JSON report generation from result objects | Supporting | Canonical cleaned benchmark reporting | Yes | Reporting-only; does not run retrieval |
| `app/retrieval_domain/applications/external_benchmark_runner.py` | Phase 7 application service for end-to-end external benchmark workflow orchestration | Supporting | Canonical cleaned benchmark CLI workflow | Yes | Owns argument parser, dataset load coordination, cache preparation, preflight, index build, suite run, reporting, registry write |
| `app/retrieval_domain/applications/retrieval_dispatcher.py` | Phase 7 retrieval-mode dispatcher around existing vector/hybrid/temporal functions | Supporting | All benchmark retrieval modes | Needs review | Dispatch-only; scoring remains in existing retrievers |
| `app/retrieval_domain/evaluation/hit_policies.py` | Phase 6 evaluation hit-policy contracts, cleaned strict session matching, and legacy fuzzy evidence setup policy | Supporting | Cleaned LongMemEval-S evaluation; legacy default setup | Yes | `StrictSessionIdHitPolicy` owns cleaned hit logic; legacy fuzzy policy is non-canonical |
| `app/retrieval_domain/evaluation/metric_aggregation.py` | Phase 6 Recall@K and MRR aggregation service | Supporting | Evaluation context | Yes | Formula-compatible with previous inline cleaned adapter evaluator |
| `app/retrieval_domain/evaluation/evaluation_service.py` | Phase 6 service coordinating hit policy and metric aggregation after retrieval | Supporting | Evaluation context | Yes | Does not import retrievers or Chroma |
| `app/benchmarks/validate_adapter_evaluation_boundary.py` | Static guard for Dataset/Evaluation/Retrieval boundary rules | Canonical | Boundary validation | Yes | Ensures cleaned path avoids fuzzy setup and evaluation cannot mutate candidate scores |
| `app/retrieval_domain/dataset/ports.py` | Phase 8 Dataset Context repository/adapter protocols | Supporting | Dataset adapters | Yes | Defines ports without retrieval or storage dependencies |
| `app/retrieval_domain/dataset/json_dataset_repository.py` | Raw JSON dataset discovery/loading/hash repository | Supporting | LongMemEval-S dataset loading | Yes | No app retrieval/storage imports |
| `app/retrieval_domain/dataset/longmemeval_cleaned_adapter.py` | Cleaned 500-example LongMemEval-S mapping | Supporting | Cleaned LongMemEval-S | Yes | No fuzzy matching; preserves `question_date` in metadata |
| `app/retrieval_domain/dataset/longmemeval_legacy_adapter.py` | Legacy/default LongMemEval-S mapping and non-canonical fuzzy evidence setup | Supporting | Legacy 147 path | Needs review | Only allowed owner of `fuzzy_match_evidence()` |
| `app/retrieval_domain/dataset/longmemeval_adapter_facade.py` | Backward-compatible facade for current benchmark runner | Supporting | LongMemEval-S CLI compatibility | Yes | Dispatches schema adapters and delegates cleaned evaluation to Evaluation Context |
| `app/retrieval_domain/retrieval/candidate_mapper.py` | Phase 3 mapper normalizing vector, clean-hybrid, temporal, multihop, and pointer-aware candidates into one `RetrievalCandidate` contract | Supporting | All canonical benchmark retrieval modes | Yes | Drops forbidden ground-truth fields; preserves dict compatibility through `to_dict()` |
| `app/benchmarks/validate_candidate_schema.py` | Tiny cleaned LongMemEval-S candidate schema validation for vector and multihop-v2 modes | Canonical | Candidate schema validation | Yes | Uses isolated benchmark Chroma path; evaluator consumes normalized `to_dict()` output |
| `app/retrieval_domain/indexing/metadata_contracts.py` | Phase 4 benchmark Chroma metadata contract | Supporting | Indexing/storage | Yes | Allows only primitive benchmark metadata and rejects ground-truth fields |
| `app/retrieval_domain/indexing/collection_names.py` | Phase 4 Chroma collection-name policy | Supporting | Indexing/storage | Yes | Enforces Chroma 0.6.3 name limits and preserves `ch_temporal_mh_v2` alias |
| `app/retrieval_domain/indexing/registry_models.py` | Phase 4 registry dataclasses for benchmark index/run provenance | Supporting | Registry/reporting | Yes | Captures environment, collection, cache, artifact, and validation metadata |
| `app/retrieval_domain/indexing/registry_io.py` | Phase 4 registry JSON read/write helpers | Supporting | Registry/reporting | Yes | Writes `outputs/benchmarks/registry/*_registry.json` |
| `app/retrieval_domain/infrastructure/chroma_index_repository.py` | Phase 4 benchmark-only Chroma infrastructure repository | Supporting | Indexing/storage | Yes | Owns PersistentClient creation, path rejection, collection create/reuse, `collection.add()`, count validation |
| `app/retrieval_domain/infrastructure/path_config.py` | Retrieval-owned path constants for benchmark and compatibility code | Supporting | Infrastructure/path configuration | Yes | Added during post-cleanup stabilization; `app/paths.py` now re-exports this module for compatibility |
| `app/benchmarks/validate_index_registry.py` | Validates registry files, collection names, metadata keys, paths, versions, counts, and artifacts | Canonical | Registry validation | Yes | Must pass before full reruns or cache/index refactors |
| `app/retrieval_domain/features/cache_models.py` | Phase 5 feature-cache provenance dataclasses | Supporting | Feature cache provenance | Yes | Defines cache identities, parser versions, compatibility results, and manifest shape |
| `app/retrieval_domain/features/cache_registry.py` | Builds feature-cache manifest entries for grammar, temporal, temporal graph, and pointer manifest artifacts | Supporting | Feature cache provenance | Yes | Records hashes, versions, compatibility, warnings, and inferred provenance |
| `app/retrieval_domain/features/cache_registry_io.py` | Reads/writes `outputs/benchmarks/registry/feature_cache_registry.json` | Supporting | Feature cache provenance | Yes | Registry is additive and referenced by index registry entries |
| `app/retrieval_domain/features/cache_validation.py` | Benchmark preflight for feature-cache compatibility | Supporting | Feature cache validation | Yes | Fails before retrieval on incompatible required caches; does not touch production DB |
| `app/retrieval_domain/features/temporal_versions.py` | Explicit parser/cache/scorer version labels | Supporting | Temporal/multihop modes | Yes | Labels current behavior without changing parser/scorer logic |
| `app/retrieval_domain/features/grammar_frame_extractor.py` | Retrieval-owned grammar/action-frame extraction implementation | Supporting | Cache builders, temporal parsers, clean-hybrid support | Yes | Extracted from `app/dynamic_action_frame_extractor.py`; snapshot before/after matched exactly; full cleaned-500 wrapper gate matched baseline exactly |
| `app/benchmarks/validate_feature_cache_registry.py` | Validates feature cache registry compatibility before retrieval | Canonical | Feature cache validation | Yes | Reports unknown provenance as warnings; fails incompatible cache use |
| `app/benchmarks/temporal_query_parser.py` | Base temporal-frame extraction | Supporting | `clean_hybrid_temporal`; base fields for multihop-v2 | Needs review | Still active dependency, not replaced by v2 |
| `app/benchmarks/temporal_query_parser_v2.py` | Multi-event target extraction with relcl/acl support | Canonical | `clean_hybrid_temporal_multihop_v2` | Needs review | Noun-phrase-only comparisons remain weak |
| `app/benchmarks/temporal_multihop_scorer.py` | Event pair/graph scoring and link-index lookup | Canonical | `clean_hybrid_temporal_multihop_v2` | Needs review | Uses `original_memory_id`; pair score gated |
| `app/benchmarks/build_grammar_cache.py` | Builds grammar frame cache | Supporting | Temporal canonical modes; optional grammar experiments | Needs review | `clean_hybrid` exact dispatch does not pass this cache |
| `app/benchmarks/build_temporal_cache.py` | Builds memory temporal-event cache | Supporting | `clean_hybrid_temporal`, multihop-v2 | Needs review | Required input to event graph |
| `app/benchmarks/build_temporal_event_graph.py` | Builds temporal event-card/link graph | Supporting | Multihop-v2 | Needs review | Graph is large; cache registry work is warranted |
| `app/benchmarks/pointer_manifest.py` | Builds pointer provenance manifest | Supporting | Provenance layer, not scoring | Needs review | Current builder documents legacy/default LME format, not cleaned-session format |
| `app/benchmarks/pointer_resolver.py` | Resolves pointers to original text with optional hash verification | Supporting | Provenance/debug path | Yes | Not used as canonical deferred-text retrieval |
| `app/benchmarks/validate_pointer_manifest.py` | Pointer resolution/hash validation | Supporting | Provenance validation | Yes | Relevant for future provenance migration |
| `app/benchmarks/locomo_adapter.py` | LoCoMo adapter and pointer support | Experimental | LoCoMo experiments | Needs review | LoCoMo is not canonical yet |
| `app/benchmarks/archive/run_temporal_multihop_v2_full.py` | Older full-147 temporal parser comparison runner | Archived / Legacy | Historical 147 multihop analysis | No | Historical diagnostic, superseded by refactored DDD runner and canonical validations |
| `app/benchmarks/archive/run_targeted_multihop_diagnostic.py` | Targeted multihop diagnostic runner | Archived / Legacy | Historical multihop debugging | No | Historical diagnostic, superseded by refactored DDD runner and canonical validations |
| `app/benchmarks/archive/smoke_test_runner.py` | Older multi-mode external smoke runner | Archived / Legacy | Older baseline modes | No | Superseded by canonical runner and Chroma smoke test |
| `app/benchmarks/schema_exploration/longmemeval/explore_cleaned_schema.py` | Generates cleaned schema summary/report | Supporting | Dataset preparation | Yes | Produced current schema exploration artifact |
| `app/benchmarks/schema_exploration/longmemeval/compare_with_current_schema.py` | Generates compatibility proposal | Supporting | Dataset preparation | Needs review | Report is historical proposal; adapter implementation is source of truth |
| `app/benchmarks/schema_exploration/longmemeval/download_cleaned_longmemeval.py` | Downloads cleaned dataset | Supporting | Dataset acquisition | Yes | Not involved in retrieval behavior |

## Canonical Script Set

The smallest active canonical path is:

```text
app/benchmarks/run_external_benchmark.py
app/benchmarks/longmemeval_s_adapter.py
app/benchmarks/external_benchmark_adapter.py
app/benchmarks/clean_hybrid_retriever.py
app/benchmarks/validate_benchmark_integrity.py
app/benchmarks/validate_adapter_evaluation_boundary.py
app/benchmarks/temporal_query_parser_v2.py
app/benchmarks/temporal_multihop_scorer.py
app/benchmarks/chroma_smoke_test.py
app/benchmarks/clear_benchmark_chroma.py
app/benchmarks/requirements_chroma063.txt
```

Supporting temporal/cache builders and the base temporal parser remain
required dependencies for reproducing temporal modes. The
`app/retrieval_domain/*.py` files are Phase 1 supporting contracts for the
future refactor. The `app/retrieval_domain/applications/*.py` files are Phase 2
application-service extraction points now delegated to by the CLI wrapper. The
`app/retrieval_domain/retrieval/candidate_mapper.py` file is the Phase 3
candidate-schema normalization path used before evaluation. The
`app/retrieval_domain/indexing/` and
`app/retrieval_domain/infrastructure/chroma_index_repository.py` files are the
Phase 4 registry and storage infrastructure layer used by `BuildBenchmarkIndex`.
The `app/retrieval_domain/features/` files are the Phase 5 feature-cache and
temporal/parser provenance layer used by benchmark preflight validation. The
`app/retrieval_domain/evaluation/` files are the Phase 6 evaluation isolation
layer; they own cleaned strict session-ID hit policy and metric aggregation
without changing metric formulas. Phase 7 adds
`external_benchmark_runner.py` and `retrieval_dispatcher.py` so the benchmark
CLI is mostly a wrapper around DDD application services. Phase 8 adds the
`app/retrieval_domain/dataset/` package so LongMemEval raw JSON loading,
cleaned mapping, legacy mapping, and facade compatibility are separated.

## Retrieval-Only Cleanup Status

The active repository has been narrowed to retrieval and benchmark code. The
following categories were moved out of active code without deletion:

- frontend/demo UI: `frontend/` -> `archive_non_retrieval/frontend/frontend/`
- non-canonical experiment/debug scripts: root scratch/debug runners,
  stale root launch wrappers, `scratch/`, and `app/experimental/`
- response/reengagement/chatbot runtime modules not used by canonical
  retrieval
- emotion planning, LLM judge, symbolic/rank-fusion/usage-graph experiments
  not reachable from the protected retrieval graph

Quarantine locations:

- `app/archive_non_retrieval/`
- `archive_non_retrieval/frontend/`

Intentionally kept because the canonical benchmark import graph still uses
them:

| File path | Reason kept |
| --- | --- |
| `app/memory_retriever.py` | Imported by canonical benchmark runner path |
| `app/hybrid_memory_retriever.py` | Imported by canonical benchmark runner path |
| `app/dynamic_action_frame_extractor.py` | Compatibility wrapper around `app/retrieval_domain/features/grammar_frame_extractor.py`; kept only for historical import path |
| `app/paths.py` | Compatibility wrapper around `app/retrieval_domain/infrastructure/path_config.py`; still imported by `app/vector_store.py` and `app/hybrid_memory_retriever.py` |
| `app/vector_store.py` | Imported by canonical/supporting retrieval modules |

Cleanup evidence:

- `outputs/benchmarks/non_retrieval_code_audit.md`
- `outputs/benchmarks/retrieval_only_cleanup_final_plan.md`
- `outputs/benchmarks/retrieval_only_cleanup_report.md`

## Post-Cleanup Stabilization Status

After retrieval-only cleanup, the full cleaned-500 matrix reproduced exactly
against `outputs/benchmarks/refactored_cleaned500_matrix_results.json`.

Stabilization artifacts:

- `outputs/benchmarks/post_cleanup_cleaned500_matrix_report.md`
- `outputs/benchmarks/post_cleanup_cleaned500_matrix_results.json`
- `outputs/benchmarks/remaining_dependency_surface_audit.md`
- `outputs/benchmarks/remaining_dependency_surface_audit.json`
- `outputs/benchmarks/top_level_dependency_migration_plan.md`
- `outputs/benchmarks/post_cleanup_stabilization_report.md`

The only extraction performed in this phase was path constants into
`app/retrieval_domain/infrastructure/path_config.py`. No scoring, ranking,
metrics, storage behavior, or quarantined files changed.

## Grammar / Action-Frame Extraction Status

Grammar/action-frame behavior has been moved into
`app/retrieval_domain/features/grammar_frame_extractor.py`.

- `app/dynamic_action_frame_extractor.py` remains as a compatibility wrapper.
- Active benchmark/cache imports now use the retrieval-owned module where safe.
- Before/after extractor snapshots matched exactly.
- Cache-builder smoke tests and limit-20 `user_only` / `all_turns`
  validations passed.
- Full cleaned-500 wrapper validation passed for `user_only` and `all_turns`;
  R@1, R@5, R@10, and MRR matched
  `outputs/benchmarks/post_cleanup_cleaned500_matrix_results.json` exactly.
- No active benchmark/cache imports from the wrapper remain. The only code
  import found is archived historical script
  `app/benchmarks/archive/smoke_test_runner.py`.
- The wrapper appears safe to remove later pending explicit approval and either
  updating or accepting the archived historical import.
