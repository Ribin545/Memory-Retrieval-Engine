# Evaluation Tracks

## A. Legacy 147 LongMemEval-S Path

The original/default adapter path loads document strings from the older
LongMemEval-S form and generates `doc_N` session IDs. Because this source does
not provide the cleaned path's explicit answer-session ground truth, the
adapter derives expected sessions with `fuzzy_match_evidence(query, answer,
doc_text)`.

This path remains useful for historical ablations, temporal/parser debugging,
and understanding the evolution of retrieval modes. It is not the canonical
path for comparison with the cleaned external raw-style evaluation.

## B. Cleaned 500 LongMemEval-S Path

The canonical external evaluation passes `--schema cleaned` and loads 500
examples containing explicit `answer_session_ids`. The adapter maps them to
`expected_session_ids` and evaluates candidates using strict equality against
candidate `session_id`, `source_session_id`, or `original_memory_id`.

The cleaned evaluation does not use fuzzy evidence matching.

## C. `user_only` Track

`user_only` joins only turns whose role is `user`, formatting each as
`user: {content}`. It is the closest available external raw
apples-to-apples path and is the designated track for raw reference
comparison.

## D. `all_turns` Track

`all_turns` joins both user and assistant turns with role labels. It retains
assistant suggestions and conversational context, which is relevant to a
assistant-memory retrieval product, but adds text that can make retrieval
noisier than `user_only`.

This is the richer-context retrieval track, not a replacement for the raw
comparison track.

## E. Internal 65-Case Regression

The internal regression suite validates production retrieval behavior
separately from external benchmark accuracy. It exercises production imports,
not `app/benchmarks/clean_hybrid_retriever.py`.

The suite passed 65 cases during canonical-environment validation. However,
query-only access changed production Chroma SQLite bytes; any future
production regression should operate on a snapshot or copy.

## Boundaries

| Path | Dataset / target | Purpose | Canonical comparison status |
| --- | --- | --- | --- |
| Legacy default LongMemEval-S | 147 older examples | Historical/parser ablations | Historical only |
| Cleaned `user_only` | 500 explicit-ID examples | Raw external comparison | Canonical track, with scoring-risk qualification |
| Cleaned `all_turns` | 500 explicit-ID examples | Richer assistant context | Canonical richer-context track, with scoring-risk qualification |
| Internal regression | 65 production cases | Production behavior validation | Separate from external metrics |

The qualification refers to the current clean-hybrid-family
ground-truth-derived `query_session_id` metadata hint documented in
[01_current_system_state.md](./01_current_system_state.md).
