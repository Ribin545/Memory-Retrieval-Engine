# Known Issues And Refactor Roadmap

## Known Issues

| Issue | Impact | Current guidance |
| --- | --- | --- |
| Chroma version fragility | Older benchmark ingestion failed during metadata compaction | Retain pinned Python 3.11.9 / Chroma 0.6.3 isolated environment |
| Production DB query-byte mutation | Query-only regression changed production SQLite bytes | Run future production validation against a snapshot/copy |
| Collection-name length constraint | Full multihop-v2 collection name exceeds Chroma 0.6.3 limit | Preserve documented `ch_temporal_mh_v2` storage alias |
| Legacy fuzzy evidence path | Older 147 path derives expected evidence heuristically | Keep for history only; use cleaned strict-ID track for canonical work |
| `all_turns` contextual noise | Assistant text provides useful context but can reduce raw retrieval accuracy | Treat as richer-context product track, not raw replacement |
| Noun-phrase-only temporal events | Parser cannot reliably infer event verbs from noun-only comparisons | Investigate parser/model improvements before weight changes |
| LoCoMo full evaluation not canonical | Existing LoCoMo runs do not define a frozen evaluation environment | Establish a separate canonical validation plan |
| LLM reranker not implemented | Cannot compare with LLM-assisted external modes | Do not claim LLM-rerank equivalence |
| Benchmark/production code boundaries | Benchmark modules call selected production helpers | Separate packages and contracts in a controlled refactor |
| Expected-session metadata hint in hybrid benchmarking | Fixed in Phase 1 by removing `query_session_id` / `query_evidence_ids` from retrieval construction and scoring | Keep `app/benchmarks/validate_benchmark_integrity.py` in the canonical validation path |
| Corrected benchmark matrix supersedes pre-integrity 99.0% result | The earlier hybrid comparison was inflated by a benchmark-only metadata hint | Use `outputs/benchmarks/benchmark_integrity_fix_results.json` for current comparison claims |
| Benchmark venv launcher target missing | `.venv_benchmark_chroma063` packages remain intact, but its `pyvenv.cfg` points to a missing `C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe` | Use a local Python 3.11 runtime with the existing benchmark site-packages or restore the canonical Python 3.11.9 interpreter before full reruns |
| Candidate schema drift | Vector, hybrid, temporal, and pointer-aware paths historically returned ad hoc dicts | Phase 3 added `RetrievalCandidate.to_dict()` and `candidate_mapper.py`; keep mapper in the validation path |
| Cache/index provenance drift | Benchmark collections and feature caches previously lacked a single registry artifact | Phase 4 writes `outputs/benchmarks/registry/*_registry.json` and validates it with `validate_index_registry.py` |
| Feature cache provenance partially inferred | Existing cache files do not embed full dataset/schema/turns provenance | Phase 5 writes `feature_cache_registry.json`; unknown provenance is reported as a warning and incompatible required caches fail preflight |
| Cleaned pointer manifest format gap | Cleaned adapter pointer IDs are not covered by the documented legacy manifest builder format | Normalize pointer formats or extend manifest builder and validate |
| `question_date` not mapped | Intended query timestamp is absent from current adapter output | Decide normalized query-time contract during schema refactor |
| Adapter/evaluation boundary still transitional | `LongMemEvalAdapter` remains a compatibility wrapper | Phase 8 split LongMemEval mapping into Dataset Context adapters; later phases can migrate callers from compatibility dataclasses to domain dataclasses |
| Runner migration still keeps compatibility exports | Legacy scripts import names from `run_external_benchmark.py` | Phase 7 keeps wrapper exports while moving canonical orchestration to DDD application services |
| Archived diagnostics are preserved, not active | Historical runners may still contain old assumptions | Keep them under `app/benchmarks/archive/`; do not use them for canonical validation |

## Proposed Refactor Roadmap

The architecture target for this roadmap is expanded in
[12_domain_driven_design_architecture.md](./12_domain_driven_design_architecture.md).

### Phase 0: Freeze Current Docs And Benchmark Results

- Treat this bible, the DDD proposal, and canonical benchmark artifacts as the
  baseline before code movement.
- Do not rerun production validation except against a copy/snapshot.
- Treat pre-integrity results as historical and superseded for hybrid
  comparison claims.

### Phase 1: Benchmark Integrity Boundary

- Treat this bible and canonical artifacts as the baseline.
- Added a benchmark-integrity guard prohibiting expected answer/session IDs from
  entering retrieval scoring inputs.
- Removed ground-truth-derived `query_session_id` and `query_evidence_ids`
  from clean-hybrid-family retrieval.
- Corrected cleaned-500 matrix completed for both `user_only` and `all_turns`;
  `user_only` still beats the external raw R@5/R@10 reference by a smaller margin, while
  `all_turns` does not.
- Introduce lightweight domain contract models under `app/retrieval_domain/`
  without migrating runners yet.
- Make production validation copy/snapshot-based before any further production
  run.

### Phase 2: Separate Benchmark Package

- Began separating benchmark orchestration into DDD application services:
  `BuildBenchmarkIndex`, `RunBenchmarkSuite`, `EvaluateRetrievalRun`, and
  `GenerateBenchmarkReport`.
- Kept `app/benchmarks/run_external_benchmark.py` as the stable CLI wrapper.
- Left scoring, evaluator metrics, adapters, cache loading, and retrieval mode
  implementation unchanged.
- Validated cleaned LongMemEval-S limit-20 `user_only` and `all_turns`
  multihop-v2 runs against the isolated benchmark Chroma path.

### Phase 3: Normalize Candidate Schema

- Added one candidate mapping path for vector, clean-hybrid, temporal,
  multihop-v2, and pointer-aware benchmark candidates.
- Canonical candidate fields are `memory_id`, `original_memory_id`,
  `session_id`, `source_session_id`, `pointer_id`, `source_text`, `summary`,
  `dia_ids`, `score`, `final_score`, `score_breakdown`, and `metadata`.
- Existing evaluators still consume dict-compatible `candidate.to_dict()`
  output; hit policy and metrics are unchanged.
- Candidate guards drop/reject ground-truth fields such as
  `expected_session_ids`, `answer_session_ids`, `expected_evidence`,
  `query_session_id`, `query_evidence_ids`, `_query_evidence_ids`, `answer`,
  and `correct_session_id`.
- Cleaned LongMemEval-S limit-20 `user_only` and `all_turns` validations passed
  after normalization with no intentional metric change.

### Phase 4: Cache/Index Registry

- Added registry models, metadata contract, collection-name policy, registry
  JSON writer/reader, and `ChromaIndexRepository`.
- `BuildBenchmarkIndex` now delegates benchmark-only Chroma client creation,
  collection create/reuse, `collection.add()` ingestion, primitive metadata
  validation, unique ID checks, and count validation to the infrastructure
  repository.
- Registry JSON is written under `outputs/benchmarks/registry/` for validated
  runs and includes dataset/schema/turns-mode, retrieval mode, Python/Chroma/
  PostHog versions, persist path, collection name/alias, batch size, indexed
  count, metadata keys, cache paths/hashes, pointer manifest path, run
  artifacts, and error flags.
- `validate_index_registry.py` validates registry files, paths, metadata keys,
  Chroma version, document counts, feature cache paths, run artifacts, and
  production DB isolation.
- Smoke-test status is recorded but still marked `not_run` for Phase 4
  limit-20 validations.

### Phase 5: Temporal/Parser Cleanup

- Added feature-cache provenance contracts, parser/cache/scorer version labels,
  feature cache registry IO, feature cache compatibility validation, and a
  preflight hook before benchmark retrieval.
- Current labels are `temporal_parser_v1`,
  `temporal_parser_v2_relcl_acl`, `temporal_multihop_scorer_v2`,
  `grammar_cache_v1`, `temporal_cache_v1`,
  `temporal_event_graph_v1`, and `pointer_manifest_v1_legacy`.
- `clean_hybrid_temporal_multihop_v2` now requires grammar, temporal, and
  temporal event graph cache provenance and parser version
  `temporal_parser_v2_relcl_acl` before retrieval starts.
- Feature registry output:
  `outputs/benchmarks/registry/feature_cache_registry.json`.
- Existing parser extraction, temporal scoring, multihop gates, evaluator
  metrics, and ranking behavior remain unchanged.
- Improve noun-phrase-only event handling later under a controlled ablation
  plan.
- Retain diagnostics for pair activation and graph lookup identity.

### Phase 6: Adapter / Evaluation Isolation

- Added `app/retrieval_domain/evaluation/` with `HitPolicy`,
  `StrictSessionIdHitPolicy`, `LegacyFuzzyEvidenceSetupPolicy`,
  `MetricAggregator`, and `EvaluationService`.
- Moved cleaned LongMemEval-S strict session-ID hit comparison out of inline
  adapter logic and into Evaluation Context, while keeping the adapter as a
  compatibility wrapper.
- Kept legacy fuzzy evidence derivation isolated and labeled as a non-canonical
  setup policy for the old default 147 path only.
- Added `validate_adapter_evaluation_boundary.py` and included it in the
  canonical integrity preflight list.
- Validation passed for integrity, candidate schema, index registry, feature
  cache registry, adapter/evaluation boundary, compile, and cleaned
  LongMemEval-S limit-20 `user_only` / `all_turns` multihop-v2 runs.

### Phase 7: Benchmark Runner Migration

- Reduced `app/benchmarks/run_external_benchmark.py` to a thin CLI wrapper
  with compatibility exports.
- Added `ExternalBenchmarkRunner` to own argument parsing, dataset loading
  coordination, cache preparation, feature preflight, index build, suite run,
  report generation, and registry write orchestration.
- Added `retrieval_dispatcher.py` to hold benchmark retrieval-mode dispatch
  while leaving scoring in existing retriever/scorer functions.
- Kept CLI arguments and output naming stable.
- No LoCoMo canonical work was added.
- Validation passed for integrity, candidate schema, index registry, feature
  cache registry, adapter/evaluation boundary, compile, and cleaned
  LongMemEval-S limit-20 `user_only` / `all_turns` multihop-v2 runs.

### Phase 8: Dataset Context Adapter Split

- Added `app/retrieval_domain/dataset/` with ports, raw JSON repository,
  cleaned LongMemEval adapter, legacy LongMemEval adapter, and compatibility
  facade.
- Reduced `app/benchmarks/longmemeval_s_adapter.py` to a thin wrapper that
  preserves `LongMemEvalAdapter` and `fuzzy_match_evidence` imports.
- Cleaned mapping now lives in `LongMemEvalCleanedAdapter` and does not call
  fuzzy evidence setup.
- Legacy/default mapping and fuzzy evidence setup now live only in
  `LongMemEvalLegacyAdapter`.
- `LongMemEvalAdapterFacade` keeps the current runner behavior and delegates
  cleaned evaluation to `EvaluationService` / `StrictSessionIdHitPolicy`.
- Boundary validation now checks the new dataset package for retrieval,
  Chroma, report-writer, and fuzzy-ownership violations.
- Validation passed for integrity, candidate schema, index registry, feature
  cache registry, adapter/evaluation boundary, compile, and cleaned
  LongMemEval-S limit-20 `user_only` / `all_turns` multihop-v2 runs.

### Phase 9: Controlled Script Archival

- Moved only approved non-canonical historical diagnostics into
  `app/benchmarks/archive/`.
- Archived scripts:
  `run_temporal_multihop_v2_full.py`,
  `run_targeted_multihop_diagnostic.py`, and `smoke_test_runner.py`.
- Added `app/benchmarks/archive/README.md`.
- Removed archived diagnostic scripts from active integrity validator coverage.
- Canonical and supporting scripts remain in place.
- No files were deleted.

### Phase 10A: Retrieval-Only Codebase Cleanup

- Converted the active repository into a retrieval-focused codebase.
- Moved frontend/demo code to `archive_non_retrieval/frontend/`.
- Moved non-retrieval Python/runtime/history code to
  `app/archive_non_retrieval/`.
- Quarantined emotional response/planning, LLM judge, response policy,
  reengagement, chatbot runtime, scratch, debug, and experiment modules that
  were not reachable from the protected retrieval graph.
- Kept `app/memory_retriever.py`, `app/hybrid_memory_retriever.py`,
  `app/dynamic_action_frame_extractor.py`, `app/paths.py`, and
  `app/vector_store.py` because canonical retrieval still imports them.
- No Python scripts were deleted.
- Validation passed after cleanup: compile checks, all benchmark guards, and
  cleaned LongMemEval-S limit-20 `user_only` / `all_turns` multihop-v2 runs.

### Post-Cleanup Stabilization

- Reproduced the full corrected cleaned LongMemEval-S 500-example matrix after
  retrieval-only cleanup.
- All 8 canonical cells matched
  `outputs/benchmarks/refactored_cleaned500_matrix_results.json` exactly for
  Recall@1, Recall@5, Recall@10, and MRR.
- Wrote post-cleanup matrix artifacts:
  `outputs/benchmarks/post_cleanup_cleaned500_matrix_report.md` and
  `outputs/benchmarks/post_cleanup_cleaned500_matrix_results.json`.
- Audited the remaining active top-level modules:
  `app/dynamic_action_frame_extractor.py`, `app/memory_retriever.py`,
  `app/hybrid_memory_retriever.py`, `app/paths.py`, and
  `app/vector_store.py`.
- Added retrieval-owned path constants in
  `app/retrieval_domain/infrastructure/path_config.py` and kept
  `app/paths.py` as a compatibility wrapper.
- Post-extraction compile checks, all guards, and limit-20 `user_only` /
  `all_turns` multihop-v2 validations passed.
- Next shrink target should be a behavior-preserving grammar/action-frame
  extraction, not dense/vector store code.

### Grammar / Action-Frame Extraction

- Added `app/retrieval_domain/features/grammar_frame_extractor.py` as the
  retrieval-owned grammar/action-frame implementation.
- Converted `app/dynamic_action_frame_extractor.py` into a compatibility
  wrapper that preserves the old import path, including `_ensure_nlp_loaded`.
- Updated active benchmark/cache imports to use the retrieval-domain module.
- Added cleaned-schema CLI options to grammar and temporal cache builders for
  smoke validation; defaults remain `schema=default` and `turns_mode=all_turns`
  for backward compatibility.
- Snapshot before/after outputs matched exactly in the canonical benchmark
  environment.
- Cache-builder smoke tests passed under
  `outputs/benchmarks/grammar_extraction_cache_smoke/`.
- Limit-20 validations passed with expected metrics:
  `user_only` R@1 95.00%, R@5 100.00%, R@10 100.00%, MRR 0.9750;
  `all_turns` R@1 65.00%, R@5 95.00%, R@10 95.00%, MRR 0.7667.
- Full cleaned-500 wrapper validation passed for the current best
  `clean_hybrid_temporal_multihop_v2` mode on both `user_only` and
  `all_turns`; R@1, R@5, R@10, and MRR matched
  `outputs/benchmarks/post_cleanup_cleaned500_matrix_results.json` exactly.
- No active benchmark/cache imports from `app/dynamic_action_frame_extractor.py`
  remain. The only code import found is archived historical script
  `app/benchmarks/archive/smoke_test_runner.py`.
- The compatibility wrapper can be considered for deletion after explicit
  approval and a decision on the archived import.

### Phase 10: LoCoMo Full Canonical Evaluation

- Freeze LoCoMo schema, unit type, pointer contract, environment, and metrics.
- Resolve composite pointer behavior before making LoCoMo canonical.

### Phase 11: Optional LLM Reranker/Reader Evaluation

- Add an explicitly separate LLM-assisted retrieval stage, if desired.
- Compare it only to equivalent assisted external baselines.
- Keep raw retrieval reporting separately visible.

## Recommended First Refactor Step

Before LoCoMo canonical work, keep the integrity guard, candidate schema
validator, index registry validator, feature cache registry validator, and
adapter/evaluation boundary validator as required preflights. Any future
deletion should first prove the quarantined files are unnecessary; the current
cleanup deliberately preserved them in archive form.
