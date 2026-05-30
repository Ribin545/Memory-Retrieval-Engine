# Agent Task Templates

Use these prompts as starting points for future agents. Replace bracketed
values before use.

## Safe Benchmark Validation Task

```text
Run a safe benchmark validation for Memory Retrieval Engine.

Source of truth:
- docs/retrieval_bible/13_developer_runbook.md
- outputs/benchmarks/refactored_cleaned500_matrix_results.json

Constraints:
- Do not touch production Chroma DB.
- Do not change scoring, metrics, candidate ranking, or evaluator logic.
- Do not delete/archive scripts.
- Use Python 3.11.9 + chromadb==0.6.3 + posthog<3.

Run:
- validate_benchmark_integrity.py
- validate_candidate_schema.py
- validate_index_registry.py
- validate_feature_cache_registry.py
- validate_adapter_evaluation_boundary.py
- limit-20 cleaned user_only multihop-v2
- limit-20 cleaned all_turns multihop-v2

Write report:
- outputs/benchmarks/[name]_validation_report.md
```

## Add New Retrieval Mode Task

```text
Add a new benchmark retrieval mode named [mode_name].

Source of truth:
- docs/retrieval_bible/04_retrieval_modes.md
- docs/retrieval_bible/13_developer_runbook.md
- app/retrieval_domain/applications/retrieval_dispatcher.py
- app/retrieval_domain/retrieval/candidate_mapper.py

Forbidden changes:
- Do not tune existing mode weights.
- Do not change existing scoring or evaluator metrics.
- Do not pass ground truth into retrieval.
- Do not touch production Chroma.

Required work:
- Add mode dispatch.
- Preserve canonical candidate shape.
- Update registry/mode docs.
- Run all guards.
- Run limit-20 user_only/all_turns validation.

Write report:
- outputs/benchmarks/[mode_name]_mode_addition_report.md
```

## Add New Dataset Adapter Task

```text
Add a new Dataset Context adapter for [dataset_name].

Source of truth:
- docs/retrieval_bible/05_adapters_and_schema.md
- docs/retrieval_bible/13_developer_runbook.md
- app/retrieval_domain/dataset/
- app/retrieval_domain/evaluation/

Forbidden changes:
- Do not use fuzzy evidence matching unless the path is explicitly legacy/non-canonical.
- Do not import retrievers, scoring services, Chroma, or report writers from dataset adapters.
- Do not change existing LongMemEval behavior.
- Do not touch production Chroma.

Required work:
- Add schema exploration notes.
- Add dataset adapter and explicit hit policy.
- Add boundary validation coverage.
- Run all guards and limit validation.

Write report:
- outputs/benchmarks/[dataset_name]_adapter_report.md
```

## Fix Chroma / Index Issue Task

```text
Investigate and fix a benchmark Chroma/index issue.

Source of truth:
- docs/retrieval_bible/02_canonical_benchmark_environment.md
- docs/retrieval_bible/13_developer_runbook.md
- app/retrieval_domain/infrastructure/chroma_index_repository.py
- app/retrieval_domain/indexing/

Forbidden changes:
- Do not add an in-memory backend.
- Do not touch production Chroma.
- Do not continue benchmark runs after Chroma write/query/count failure.
- Do not change scoring or metrics.

Required work:
- Verify Python 3.11.9, chromadb==0.6.3, posthog<3.
- Use isolated path data/external/indexes/chroma_cleaned_500_py311_chroma063/.
- Use batch size 50 and collection.add().
- Run Chroma smoke test if storage behavior changed.
- Run guards and limit validations.

Write report:
- outputs/benchmarks/[issue_name]_chroma_fix_report.md
```

## Refactor Without Changing Scoring Task

```text
Refactor [area] without changing retrieval scoring or evaluator metrics.

Source of truth:
- docs/retrieval_bible/12_domain_driven_design_architecture.md
- docs/retrieval_bible/13_developer_runbook.md
- outputs/benchmarks/refactored_cleaned500_matrix_results.json

Forbidden changes:
- No scoring changes.
- No metric formula changes.
- No candidate ranking changes.
- No production Chroma access.
- No script deletion/archive unless explicitly requested.

Validation:
- Compile touched Python files.
- Run all benchmark guards.
- Run limit-20 user_only/all_turns multihop-v2.
- If behavior surface changed, compare against corrected baseline.

Write report:
- outputs/benchmarks/[area]_refactor_report.md
```

## Controlled Script Archival Task

```text
Perform controlled move-only archival for approved scripts.

Source of truth:
- outputs/benchmarks/controlled_script_archival_plan.md
- docs/retrieval_bible/10_script_inventory.md

Constraints:
- Move only explicitly approved files.
- Do not delete files.
- Do not archive canonical/supporting scripts.
- Do not change scoring, metrics, CLI behavior, or production DB.

Validation:
- Run all guards before moving.
- Move approved files to app/benchmarks/archive/.
- Update archive README and script inventory.
- Compile active benchmark scripts.
- Run all guards after moving.
- Run limit-20 user_only/all_turns validation.

Write report:
- outputs/benchmarks/controlled_script_archival_report.md
```

## Update Benchmark Docs Task

```text
Update Retrieval Bible docs after [change].

Source of truth:
- docs/retrieval_bible/README.md
- docs/retrieval_bible/13_developer_runbook.md
- relevant phase report under outputs/benchmarks/

Forbidden changes:
- Do not change code behavior unless fixing a tiny broken link/path reference.
- Do not run production Chroma.
- Do not edit benchmark result artifacts except when intentionally regenerating.

Required docs to consider:
- README.md
- 10_script_inventory.md
- 11_known_issues_and_refactor_roadmap.md
- 12_domain_driven_design_architecture.md
- artifacts_index.md
- relevant mode/schema docs

Validation:
- Run markdown/link sanity check.
- Compile only if code changed.

Write report:
- outputs/benchmarks/[change]_docs_report.md
```
