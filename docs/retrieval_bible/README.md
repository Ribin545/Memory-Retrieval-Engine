# Memory Retrieval Engine Refactor Bible

## Purpose

This documentation pack consolidates the external retrieval benchmark work
into a source-grounded guide for a future refactor. It records the current
benchmark implementation, canonical cleaned LongMemEval-S run, storage
stabilization, temporal and pointer work, and remaining risks.

This pack is documentation only. It does not authorize a production retrieval
refactor, a scoring change, or access to the production Chroma database.

## Current Status

| Item | Current status |
| --- | --- |
| Canonical external dataset | Cleaned LongMemEval-S, 500 examples |
| Canonical raw-comparison track | `user_only` |
| Richer-context retrieval track | `all_turns` |
| Best measured mode in both tracks | `clean_hybrid_temporal_multihop_v2` |
| Canonical environment | Python `3.11.9`, `chromadb==0.6.3`, `posthog<3` |
| Benchmark storage | Isolated Chroma path, `collection.add()`, batch size `50` |
| Chroma compaction status | No compaction errors in successful canonical runs |
| Internal regression | Passed, 65 cases |

Integrity status: the pre-integrity-fix 99.0% `user_only` Recall@5 result is
superseded. Phase 1 removed the benchmark-only ground-truth metadata hint from
clean-hybrid-family retrieval, added a static integrity guard, and reran the
cleaned-500 matrix in the isolated Chroma 0.6.3 environment.

## Latest Cleaned Results

| Track | Best measured mode | Recall@1 | Recall@5 | Recall@10 | MRR |
| --- | --- | ---: | ---: | ---: | ---: |
| `user_only` | `clean_hybrid_temporal_multihop_v2` | 88.00% | 97.40% | 98.60% | 0.9204 |
| `all_turns` | `clean_hybrid_temporal_multihop_v2` | 82.00% | 95.60% | 98.00% | 0.8808 |

## External Raw Baseline Summary

The recorded external raw reference values are Recall@5 `96.6` and
Recall@10 `98.2`. The corrected Memory Retrieval Engine `user_only`
multihop-v2 row is higher at Recall@5 `97.40` and Recall@10 `98.60`, but by a
smaller margin than the superseded pre-integrity result.

`user_only` is the closest raw apples-to-apples track; `all_turns` is the
richer-context retrieval track. After correction, `all_turns` does not beat
the external raw reference.

## Reading Guide

| Document | Purpose |
| --- | --- |
| [01_current_system_state.md](./01_current_system_state.md) | Current implementation boundary, reliability fix, production caveat |
| [02_canonical_benchmark_environment.md](./02_canonical_benchmark_environment.md) | Pinned environment and isolated Chroma storage contract |
| [03_evaluation_tracks.md](./03_evaluation_tracks.md) | Legacy, cleaned, user-only, all-turns, and production regression paths |
| [04_retrieval_modes.md](./04_retrieval_modes.md) | Actual mode behavior and signals from current code |
| [05_adapters_and_schema.md](./05_adapters_and_schema.md) | Cleaned schema mapping and evaluation rules |
| [06_benchmark_results.md](./06_benchmark_results.md) | Canonical result tables |
| [07_mempalace_comparison.md](./07_mempalace_comparison.md) | Careful historical comparison framing |
| [08_temporal_and_multihop_history.md](./08_temporal_and_multihop_history.md) | Temporal/parser/graph journey |
| [09_pointer_system.md](./09_pointer_system.md) | Pointer foundation and migration status |
| [10_script_inventory.md](./10_script_inventory.md) | Relevant script classification |
| [11_known_issues_and_refactor_roadmap.md](./11_known_issues_and_refactor_roadmap.md) | Risks and phased roadmap |
| [12_domain_driven_design_architecture.md](./12_domain_driven_design_architecture.md) | DDD bounded contexts and future refactor architecture |
| [13_developer_runbook.md](./13_developer_runbook.md) | Practical developer/agent runbook for safe benchmark work |
| [14_agent_task_templates.md](./14_agent_task_templates.md) | Reusable prompts/templates for future agents |
| [15_command_cheatsheet.md](./15_command_cheatsheet.md) | Compact PowerShell command reference |
| [artifacts_index.md](./artifacts_index.md) | Evidence and raw artifact index |

## Canonical Sources

- [Corrected integrity-fix report](../../outputs/benchmarks/benchmark_integrity_fix_report.md)
- [Corrected integrity-fix results JSON](../../outputs/benchmarks/benchmark_integrity_fix_results.json)
- [Pre-integrity final report, superseded for hybrid comparison](../../outputs/benchmarks/longmemeval_cleaned_chroma063_final_report.md)
- [Pre-integrity final results JSON, superseded for hybrid comparison](../../outputs/benchmarks/longmemeval_cleaned_chroma063_final_results.json)
- [Canonical environment document](../longmemeval_cleaned_chroma063_environment.md)
- [Cleaned adapter validation](../../outputs/benchmarks/longmemeval_cleaned_adapter_validation.md)
- [Refactored runner reproduction report](../../outputs/benchmarks/refactored_cleaned500_matrix_report.md)
