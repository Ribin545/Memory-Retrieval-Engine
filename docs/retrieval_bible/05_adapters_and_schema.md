# Adapters And Schema

## Relevant Adapter

The cleaned and legacy LongMemEval-S paths are both implemented in
[app/benchmarks/longmemeval_s_adapter.py](../../app/benchmarks/longmemeval_s_adapter.py).
The adapter selects the cleaned branch only when invoked with
`schema="cleaned"`.

As of Phase 8, that file is only a compatibility wrapper. The Dataset Context
implementation lives under `app/retrieval_domain/dataset/`:

| File | Responsibility |
| --- | --- |
| `ports.py` | Dataset repository/adapter protocols |
| `json_dataset_repository.py` | Raw JSON discovery, loading, and hashing |
| `longmemeval_cleaned_adapter.py` | Cleaned 500-example schema mapping |
| `longmemeval_legacy_adapter.py` | Old/default 147-example schema mapping and legacy fuzzy evidence setup |
| `longmemeval_adapter_facade.py` | Backward-compatible `LongMemEvalAdapter`-style API and cleaned evaluation compatibility |

## Cleaned Dataset Shape

The inspected cleaned dataset contains 500 examples with these top-level
fields:

```text
question_id
question_type
question
question_date
answer
answer_session_ids
haystack_dates
haystack_session_ids
haystack_sessions
```

The schema exploration report records an average of 47.73 sessions per
example and 10.34 turns per session.

## Current Field Mapping

| Cleaned field | Benchmark representation | Current implementation detail |
| --- | --- | --- |
| `question_id` | `example_id` | Used directly, with fallback only if absent |
| `question` | `query` | Required; missing queries are skipped |
| `answer` | `expected_evidence` | Stored as one-item list when non-empty |
| `answer_session_ids` | `expected_session_ids` | Ground truth for strict cleaned evaluation |
| `haystack_sessions` | `memory_units` | One memory unit per session; text joined from turns |
| `haystack_session_ids` | `session_id`, `source_session_id`, `original_memory_id` | Same source ID copied into all three fields |
| `haystack_dates` | memory-unit `timestamp` | Zipped one-to-one with sessions and session IDs |
| `question_date` | example metadata | Preserved as `metadata["question_date"]`; not yet used as retrieval query timestamp |
| `question_type` | example `metadata["question_type"]` | Preserved with `metadata["schema"]="cleaned"` |

## Turn Assembly

For session lists:

| Turns mode | Assembly behavior |
| --- | --- |
| `user_only` | Retains only turns where `role == "user"` and formats `role: content` |
| `all_turns` | Retains all turns and formats `role: content` |

Turn strings are joined with two newline characters.

## Strict Cleaned Evaluation

For an example loaded under the cleaned schema, a candidate is considered a
hit if any of these candidate fields exactly equals one of the explicit
`expected_session_ids`:

```text
session_id
source_session_id
original_memory_id
```

Recall@1, Recall@5, Recall@10, and MRR are then computed from the first
matching rank. No fuzzy answer-text evidence mapping is used for this branch.

As of Phase 6, the cleaned strict hit policy is owned by the Evaluation
Context:

- `app/retrieval_domain/evaluation/hit_policies.py` defines
  `StrictSessionIdHitPolicy`.
- `app/retrieval_domain/evaluation/metric_aggregation.py` computes the same
  Recall@K and MRR formulas used by the previous inline adapter logic.
- `app/retrieval_domain/evaluation/evaluation_service.py` coordinates the hit
  policy and metrics after retrieval returns ranked candidates.

`LongMemEvalAdapter.evaluate_retrieval()` remains as a compatibility wrapper
for existing callers, but the cleaned hit comparison is no longer implemented
inline in the adapter.

In Phase 8, that wrapper role moved to
`LongMemEvalAdapterFacade.evaluate_retrieval()`. The benchmark import path
`app/benchmarks/longmemeval_s_adapter.py::LongMemEvalAdapter` still works.

## Legacy Default Schema Preservation

The legacy adapter retains the default branch for the older dataset shape
based on `documents`. That branch generates `doc_N` session identifiers and
invokes `fuzzy_match_evidence()` to derive expected sessions from query,
answer, and document text.

The fuzzy branch is preserved for historical runs as
`LegacyFuzzyEvidenceSetupPolicy` and must not be conflated with the canonical
cleaned-500 evaluation. It is not used when `schema="cleaned"` and must never
feed retrieval scoring.

## Boundary Validation

Phase 6 added
[`app/benchmarks/validate_adapter_evaluation_boundary.py`](../../app/benchmarks/validate_adapter_evaluation_boundary.py)
to enforce that:

- dataset adapters do not import retrieval scoring or Chroma infrastructure;
- cleaned LongMemEval-S does not call legacy fuzzy evidence matching;
- only the legacy LongMemEval adapter owns fuzzy evidence setup;
- the JSON dataset repository only loads raw files and hashes;
- hit policies do not import retrievers or Chroma;
- retrieval modules do not import evaluation-owned hit policies or
  `GroundTruth`;
- evaluation modules do not mutate candidate `score` or `final_score`.

## Evidence

- [Cleaned adapter validation report](../../outputs/benchmarks/longmemeval_cleaned_adapter_validation.md)
- [Cleaned schema report](../../outputs/benchmarks/schema_exploration/longmemeval_cleaned_schema_report.md)
- [Schema compatibility report](../../outputs/benchmarks/schema_exploration/longmemeval_schema_compatibility_report.md)

Note: the two schema reports exist beneath `outputs/benchmarks/schema_exploration/`,
not directly beneath `outputs/benchmarks/`.
