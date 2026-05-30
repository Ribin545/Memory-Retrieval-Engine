# Artifacts Index

## Canonical And Current Evidence

Historical raw logs, ablation outputs, old exploratory reports, and
non-required validation run folders were removed from active handoff state.
`marked_for_delete/` is an ignored local deletion-staging folder and is
currently cleared. Current benchmark evidence, validator-required registries,
and docs-linked evidence remain in place.

| Artifact path | What it proves | Status | Referenced by |
| --- | --- | --- | --- |
| [`docs/longmemeval_cleaned_chroma063_environment.md`](../longmemeval_cleaned_chroma063_environment.md) | Required Python/Chroma/PostHog environment and storage contract | Canonical/current | [README](./README.md), [Environment](./02_canonical_benchmark_environment.md) |
| [`outputs/benchmarks/longmemeval_cleaned_chroma063_final_report.md`](../../outputs/benchmarks/longmemeval_cleaned_chroma063_final_report.md) | Human-readable cleaned-500 matrix, production regression note, storage result | Canonical/current | [README](./README.md), [System state](./01_current_system_state.md), [Results](./06_benchmark_results.md) |
| [`outputs/benchmarks/longmemeval_cleaned_chroma063_final_results.json`](../../outputs/benchmarks/longmemeval_cleaned_chroma063_final_results.json) | Machine-readable canonical metrics, collection names, counts, environment | Canonical/current | [README](./README.md), [Results](./06_benchmark_results.md), [External comparison](./07_mempalace_comparison.md) |
| [`outputs/benchmarks/longmemeval_cleaned_adapter_validation.md`](../../outputs/benchmarks/longmemeval_cleaned_adapter_validation.md) | Cleaned adapter loads 500 examples and evaluates with strict session IDs | Current supporting evidence | [Adapters](./05_adapters_and_schema.md) |
| [`outputs/benchmarks/chroma_compaction_fix_report.md`](../../outputs/benchmarks/chroma_compaction_fix_report.md) | Storage stabilization design and smoke/validation outcome | Current supporting evidence | [Environment](./02_canonical_benchmark_environment.md) |
| [`outputs/benchmarks/chroma_environment_audit.md`](../../outputs/benchmarks/chroma_environment_audit.md) | Failed versus stabilized Chroma environments | Current supporting evidence for failure investigation | [Environment](./02_canonical_benchmark_environment.md) |
| [`outputs/benchmarks/registry/feature_cache_registry.json`](../../outputs/benchmarks/registry/feature_cache_registry.json) | Phase 5 grammar/temporal/temporal graph/pointer cache identities and compatibility status | Current supporting evidence | [Retrieval modes](./04_retrieval_modes.md), [Temporal history](./08_temporal_and_multihop_history.md), [Pointer system](./09_pointer_system.md) |
| [`outputs/benchmarks/ddd_phase5_feature_cache_registry_report.md`](../../outputs/benchmarks/ddd_phase5_feature_cache_registry_report.md) | Phase 5 feature cache registry implementation, validation, and limit-20 metrics | Current supporting evidence | [Roadmap](./11_known_issues_and_refactor_roadmap.md), [DDD architecture](./12_domain_driven_design_architecture.md) |
| [`outputs/benchmarks/refactored_cleaned500_matrix_report.md`](../../outputs/benchmarks/refactored_cleaned500_matrix_report.md) | Refactored DDD runner reproduced the corrected cleaned-500 matrix exactly | Canonical/current reproduction proof | [Roadmap](./11_known_issues_and_refactor_roadmap.md), [Script inventory](./10_script_inventory.md) |
| [`outputs/benchmarks/refactored_cleaned500_matrix_results.json`](../../outputs/benchmarks/refactored_cleaned500_matrix_results.json) | Machine-readable refactored runner reproduction matrix and baseline comparison | Canonical/current reproduction proof | [Roadmap](./11_known_issues_and_refactor_roadmap.md), [Script inventory](./10_script_inventory.md) |
| [`outputs/benchmarks/controlled_script_archival_plan.md`](../../outputs/benchmarks/controlled_script_archival_plan.md) | Approved archival scope and stop conditions for historical benchmark scripts | Current supporting evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/controlled_script_archival_report.md`](../../outputs/benchmarks/controlled_script_archival_report.md) | Move-only archival result, guard status, and limit-20 validation after archival | Current supporting evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`app/benchmarks/archive/README.md`](../../app/benchmarks/archive/README.md) | Explains archived historical benchmark diagnostics and canonical entry point | Current supporting evidence | [Script inventory](./10_script_inventory.md), [Developer runbook](./13_developer_runbook.md) |
| [`outputs/benchmarks/non_retrieval_code_audit.md`](../../outputs/benchmarks/non_retrieval_code_audit.md) | Static import/reachability audit used to separate retrieval from non-retrieval code | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Developer runbook](./13_developer_runbook.md) |
| [`outputs/benchmarks/retrieval_only_cleanup_final_plan.md`](../../outputs/benchmarks/retrieval_only_cleanup_final_plan.md) | Final quarantine plan generated from the audit and product decision | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/retrieval_only_cleanup_report.md`](../../outputs/benchmarks/retrieval_only_cleanup_report.md) | Retrieval-only cleanup result, guard status, and limit-20 validation metrics | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| `archive_non_retrieval/README.md` | Local ignored quarantine note; not required for the handoff repo | Historical local cleanup evidence | [Script inventory](./10_script_inventory.md), [Developer runbook](./13_developer_runbook.md) |
| [`outputs/benchmarks/post_cleanup_cleaned500_matrix_report.md`](../../outputs/benchmarks/post_cleanup_cleaned500_matrix_report.md) | Post-cleanup retrieval-only codebase reproduced the corrected cleaned-500 matrix exactly | Canonical/current reproduction proof | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md), [Developer runbook](./13_developer_runbook.md) |
| [`outputs/benchmarks/post_cleanup_cleaned500_matrix_results.json`](../../outputs/benchmarks/post_cleanup_cleaned500_matrix_results.json) | Machine-readable post-cleanup matrix and exact baseline comparison | Canonical/current reproduction proof | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/remaining_dependency_surface_audit.md`](../../outputs/benchmarks/remaining_dependency_surface_audit.md) | Audit of remaining active top-level retrieval dependencies after cleanup | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/remaining_dependency_surface_audit.json`](../../outputs/benchmarks/remaining_dependency_surface_audit.json) | Machine-readable import/dependency audit for remaining top-level modules | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/top_level_dependency_migration_plan.md`](../../outputs/benchmarks/top_level_dependency_migration_plan.md) | Safe phased plan for migrating remaining top-level dependencies into retrieval-owned modules | Current cleanup evidence | [Roadmap](./11_known_issues_and_refactor_roadmap.md), [Developer runbook](./13_developer_runbook.md) |
| [`outputs/benchmarks/post_cleanup_stabilization_report.md`](../../outputs/benchmarks/post_cleanup_stabilization_report.md) | Final stabilization summary, guard results, path-config extraction, and limit-20 validation metrics | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md), [Developer runbook](./13_developer_runbook.md) |
| [`outputs/benchmarks/benchmark_env_batch_setup_report.md`](../../outputs/benchmarks/benchmark_env_batch_setup_report.md) | Windows batch bootstrap now restores Python 3.11.9, installs Chroma 0.6.3/PostHog<3, and smoke-tests Chroma compaction safety | Current environment evidence | [Developer runbook](./13_developer_runbook.md), [Command cheatsheet](./15_command_cheatsheet.md) |
| [`outputs/benchmarks/grammar_frame_extractor_snapshot_before.json`](../../outputs/benchmarks/grammar_frame_extractor_snapshot_before.json) | Pre-extraction grammar/action-frame behavior snapshot | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/grammar_frame_extractor_snapshot_after.json`](../../outputs/benchmarks/grammar_frame_extractor_snapshot_after.json) | Post-extraction grammar/action-frame behavior snapshot | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/grammar_frame_extractor_snapshot_comparison.md`](../../outputs/benchmarks/grammar_frame_extractor_snapshot_comparison.md) | Exact before/after comparison for grammar/action-frame extraction | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/grammar_action_frame_extraction_report.md`](../../outputs/benchmarks/grammar_action_frame_extraction_report.md) | Final report for grammar/action-frame extraction, smoke tests, guards, and limit-20 metrics | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/grammar_wrapper_cleaned500_validation_report.md`](../../outputs/benchmarks/grammar_wrapper_cleaned500_validation_report.md) | Full cleaned-500 wrapper deletion gate; current best mode matched post-cleanup baseline exactly for `user_only` and `all_turns` | Current cleanup evidence | [Script inventory](./10_script_inventory.md), [Roadmap](./11_known_issues_and_refactor_roadmap.md) |
| [`outputs/benchmarks/public_naming_cleanup_report.md`](../../outputs/benchmarks/public_naming_cleanup_report.md) | Public README/docs naming cleanup verification for Memory Retrieval Engine | Current cleanup evidence | [Developer runbook](./13_developer_runbook.md) |
| [`outputs/benchmarks/repo_readme_and_artifact_cleanup_report.md`](../../outputs/benchmarks/repo_readme_and_artifact_cleanup_report.md) | Root README creation, artifact staging result, link check, guards, compile, and limit-20 validation | Current cleanup evidence | [Developer runbook](./13_developer_runbook.md) |

The requested source name
`outputs/benchmarks/longmemeval_cleaned_chroma063_environment.md` is not
present in the workspace. Its current canonical equivalent is
`docs/longmemeval_cleaned_chroma063_environment.md`.

## Schema And Adapter Evidence

| Artifact path | What it proves | Status | Referenced by |
| --- | --- | --- | --- |
| [`outputs/benchmarks/schema_exploration/longmemeval_cleaned_schema_report.md`](../../outputs/benchmarks/schema_exploration/longmemeval_cleaned_schema_report.md) | Cleaned dataset fields, example count, session/turn statistics | Current supporting evidence | [Adapters](./05_adapters_and_schema.md) |
| [`outputs/benchmarks/schema_exploration/longmemeval_schema_compatibility_report.md`](../../outputs/benchmarks/schema_exploration/longmemeval_schema_compatibility_report.md) | Initial mapping proposal recommending extension of existing adapter | Historical/supporting | [Adapters](./05_adapters_and_schema.md) |

The requested direct paths
`outputs/benchmarks/longmemeval_cleaned_schema_report.md` and
`outputs/benchmarks/longmemeval_schema_compatibility_report.md` are not
present; the artifacts are under `outputs/benchmarks/schema_exploration/`.

## Temporal And Pointer Evidence

| Artifact path | What it proves | Status | Referenced by |
| --- | --- | --- | --- |
| [`outputs/benchmarks/temporal_multihop_v2_full_report.md`](../../outputs/benchmarks/temporal_multihop_v2_full_report.md) | Historical 147-example parser-v2 effect and rescued cases | Historical, still relevant design evidence | [Temporal history](./08_temporal_and_multihop_history.md) |
| [`outputs/benchmarks/temporal_pair_gate_diagnostic.md`](../../outputs/benchmarks/temporal_pair_gate_diagnostic.md) | `original_memory_id` pair-score activation bug and link-index fix rationale | Historical, relevant implementation evidence | [Temporal history](./08_temporal_and_multihop_history.md) |
| [`outputs/benchmarks/temporal_multihop_fixed_full_report.md`](../../outputs/benchmarks/temporal_multihop_fixed_full_report.md) | Fixed 147-run after graph lookup and link-index corrections | Historical | [Temporal history](./08_temporal_and_multihop_history.md) |
| [`outputs/benchmarks/temporal_event_target_extraction_report.md`](../../outputs/benchmarks/temporal_event_target_extraction_report.md) | Parser-v2 relcl/acl extraction diagnostic improvements | Historical | [Temporal history](./08_temporal_and_multihop_history.md) |
| [`outputs/benchmarks/pointer_integration_report.md`](../../outputs/benchmarks/pointer_integration_report.md) | Pointer field addition, validation, and compatibility claims at integration time | Historical/supporting; some storage descriptions superseded | [Pointer system](./09_pointer_system.md) |
| [`outputs/benchmarks/pointer_resolver_validation.md`](../../outputs/benchmarks/pointer_resolver_validation.md) | Pointer resolution/hash validation output | Supporting | [Pointer system](./09_pointer_system.md) |
| [`outputs/benchmarks/pointer_manifest_report.md`](../../outputs/benchmarks/pointer_manifest_report.md) | Pointer manifest build summary | Supporting | [Pointer system](./09_pointer_system.md) |

## Interpretation Notes

- Canonical cleaned metrics come only from the Chroma 0.6.3 final JSON/report,
  not from historical 147-example reports.
- Temporal and pointer historical reports explain why components exist and
  which defects were addressed; they do not override final cleaned metrics.
- Code inspection for this bible identified a clean-hybrid metadata-hint
  comparability risk not recorded in the final results artifact. See
  [Known issues and roadmap](./11_known_issues_and_refactor_roadmap.md).
