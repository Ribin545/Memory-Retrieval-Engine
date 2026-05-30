# Temporal And Multihop History

## Phase 5 Provenance Labels

Phase 5 formalized the current temporal/parser/cache labels without changing
behavior:

- `temporal_query_parser.py` -> `temporal_parser_v1`
- `temporal_query_parser_v2.py` -> `temporal_parser_v2_relcl_acl`
- `temporal_multihop_scorer.py` -> `temporal_multihop_scorer_v2`
- temporal cache builder -> `temporal_cache_v1`
- temporal event graph builder -> `temporal_event_graph_v1`

`clean_hybrid_temporal_multihop_v2` now fails preflight if temporal cache or
temporal event graph provenance is missing or if the parser label is not
`temporal_parser_v2_relcl_acl`. The parser and scorer implementations were not
changed.

## Evolution

### Basic Temporal Layer

`build_temporal_cache.py` builds per-memory temporal events and date entities.
`clean_hybrid_temporal` extracts temporal query features and adds
`temporal_score` to the fusion path when non-zero.

### Temporal Event Graph

`build_temporal_event_graph.py` builds event cards and cross-memory links from
the temporal cache. Links represent same entity, same object or verb, shared
topic, date ordering, and same session relationships.

### Pointer Foundation

Pointer IDs were added as passive provenance metadata so retrieved candidates
can be resolved back to source material. Pointer integration did not supply
the temporal score; it established traceable candidate identity for future
retrieval and audit work.

## Multihop Corrections

| Issue | Observed effect | Resolution recorded in code/history |
| --- | --- | --- |
| `original_memory_id` mismatch | Event graph keyed raw IDs while retrieval candidates used generated IDs, leaving pair scores at zero | Graph lookup now uses candidate `original_memory_id` |
| Pair-score activation failure | No pair contribution in the faulty full run | With correct graph lookup, multihop scoring activates on detected multi-event queries |
| Link-index rebuild cost | Building an index across approximately 16.5M links per query caused severe latency | Runner pre-builds `link_index` once when graph is loaded |
| Weak embedded-event parsing | Queries framed as "the day I X ... the day I Y" emphasized structural terms such as `pass/day` | Parser v2 adds `relcl`/`acl` extraction and quality-based target ranking |

## Parser V2

`temporal_query_parser_v2.py` extends the multi-event parser with:

- relative-clause and adnominal-clause verb extraction;
- support for coordinated verbs in those clauses;
- enhanced object lookup including dative/indirect-object handling;
- target quality ordering that demotes light verbs and generic temporal nouns.

`clean_hybrid_temporal_multihop_v2` uses that parser output and applies a
gated temporal-pair contribution when the top pair evidence is strong enough.

## Rescued Examples In The Historical 147 Run

The v2 parser full report records two rank-one rescues over the earlier
multihop parser:

| Example | Improvement |
| --- | --- |
| `gpt4_8e165409` | Parsed `repot/spider_plant` and `give/neighbor`; expected session moved to rank 1 |
| `gpt4_74aed68e` | Parsed `replace/spark_plugs` and `participate/tuesdays_racking_event`; expected session moved to rank 1 |

On that historical 147-example comparison, v2 reached Recall@1 `80.27%`
versus `78.91%` for the temporal baseline and v1 multihop.

## Remaining Limitation

Noun-phrase-only comparisons remain difficult. Queries such as comparisons
between two trips or named events may provide nouns but no embedded event verb
for the parser to align to event cards. This is an open parser/modeling issue,
not evidence that scoring weights should be changed without a controlled
evaluation.

## Evidence

- [Temporal multihop v2 full report](../../outputs/benchmarks/temporal_multihop_v2_full_report.md)
- [Temporal pair gate diagnostic](../../outputs/benchmarks/temporal_pair_gate_diagnostic.md)
- [Temporal multihop fixed full report](../../outputs/benchmarks/temporal_multihop_fixed_full_report.md)
- [Temporal event target extraction report](../../outputs/benchmarks/temporal_event_target_extraction_report.md)
