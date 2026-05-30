# Canonical Benchmark Results

## Source And Conditions

These tables are rendered from
[outputs/benchmarks/benchmark_integrity_fix_results.json](../../outputs/benchmarks/benchmark_integrity_fix_results.json).

The earlier
[longmemeval_cleaned_chroma063_final_results.json](../../outputs/benchmarks/longmemeval_cleaned_chroma063_final_results.json)
artifact is retained as a historical pre-integrity result. Its 99.0%
`user_only` Recall@5 clean-hybrid-family result is superseded because
clean-hybrid scoring received a ground-truth-derived metadata hint.

Common run conditions:

| Item | Value |
| --- | --- |
| Dataset | Cleaned LongMemEval-S |
| Examples | `500` |
| Python | `3.11.9` |
| Chroma | `0.6.3` |
| Persist path | `data/external/indexes/chroma_cleaned_500_py311_chroma063/` |
| Batch size | `50` |
| Chroma compaction errors | None in successful canonical runs |

Latency is displayed to one decimal millisecond, matching the Markdown
presentation of the canonical final report. The JSON source retains full
precision.

## Cleaned LongMemEval-S: `user_only`

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Avg latency | Indexed docs | Collection name |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `vector_only` | 82.20% | 96.40% | 98.80% | 0.8842 | 61.0 ms | 23,867 | `longmemeval_s_cleaned_user_only_vector_only_stable_v1` |
| `clean_hybrid` | 87.80% | 97.40% | 98.60% | 0.9198 | 30.8 ms | 23,867 | `longmemeval_s_cleaned_user_only_clean_hybrid_stable_v1` |
| `clean_hybrid_temporal` | 87.80% | 97.40% | 98.60% | 0.9196 | 31.2 ms | 23,867 | `longmemeval_s_cleaned_user_only_clean_hybrid_temporal_stable_v1` |
| `clean_hybrid_temporal_multihop_v2` | 88.00% | 97.40% | 98.60% | 0.9204 | 30.8 ms | 23,867 | `longmemeval_s_cleaned_user_only_ch_temporal_mh_v2_stable_v1` |

## Cleaned LongMemEval-S: `all_turns`

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Avg latency | Indexed docs | Collection name |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `vector_only` | 74.60% | 92.40% | 96.80% | 0.8252 | 29.9 ms | 23,867 | `longmemeval_s_cleaned_all_turns_vector_only_stable_v1` |
| `clean_hybrid` | 82.40% | 95.60% | 98.00% | 0.8824 | 36.3 ms | 23,867 | `longmemeval_s_cleaned_all_turns_clean_hybrid_stable_v1` |
| `clean_hybrid_temporal` | 81.80% | 95.60% | 98.00% | 0.8790 | 37.4 ms | 23,867 | `longmemeval_s_cleaned_all_turns_clean_hybrid_temporal_stable_v1` |
| `clean_hybrid_temporal_multihop_v2` | 82.00% | 95.60% | 98.00% | 0.8808 | 37.9 ms | 23,867 | `longmemeval_s_cleaned_all_turns_ch_temporal_mh_v2_stable_v1` |

## Interpretation Boundary

These are the corrected canonical values after removing the
ground-truth-derived `query_session_id` / `query_evidence_ids` path from
clean-hybrid-family benchmark retrieval. Therefore:

- `vector_only` remains a clean dense baseline under the current runner.
- The clean-hybrid-family rows no longer receive expected session IDs, answer
  session IDs, expected evidence, or answer text as retrieval hints.
- Ground truth is used only by the evaluator after retrieval returns ranked
  candidates.

No retrieval scoring weights or evaluator metrics were changed for the
integrity correction.

## Phase 6 Limit-20 Validation

Phase 6 changed ownership of the cleaned strict hit policy, not metric
definitions or retrieval scoring. Small isolated validations passed against
the existing benchmark Chroma path:

| Turns mode | Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Avg latency | Report |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `user_only` | `clean_hybrid_temporal_multihop_v2` | 95.00% | 100.00% | 100.00% | 0.9750 | 23.0 ms | [JSON](../../outputs/benchmarks/ddd_phase6_validation/user_only/longmemeval_s_clean_hybrid_temporal_multihop_v2_retrieval_report.json) |
| `all_turns` | `clean_hybrid_temporal_multihop_v2` | 65.00% | 95.00% | 95.00% | 0.7667 | 45.9 ms | [JSON](../../outputs/benchmarks/ddd_phase6_validation/all_turns/longmemeval_s_clean_hybrid_temporal_multihop_v2_retrieval_report.json) |

These are smoke-scale validation metrics only. The corrected cleaned-500
matrix above remains the canonical comparison source.
