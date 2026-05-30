# Retrieval Modes

## Phase 5 Feature Provenance

Feature caches are now described by
`outputs/benchmarks/registry/feature_cache_registry.json` before retrieval.
The registry records grammar, temporal, temporal event graph, and pointer
manifest cache identities, including hashes and version labels. For
`clean_hybrid_temporal_multihop_v2`, preflight requires:

- grammar cache provenance;
- temporal cache provenance;
- temporal event graph provenance;
- parser version `temporal_parser_v2_relcl_acl`.

This provenance layer does not change scoring, ranking, parser extraction, or
evaluation. Unknown dataset/schema/turns provenance in existing cache files is
reported as a warning.

## Shared Canonical Input Shape

For cleaned LongMemEval-S, each memory unit represents one haystack session.
The adapter supplies `source_text`, session identifiers, an original session
identifier, pointer ID, and timestamp. The canonical Chroma ingestion stores
the text as the document and only primitive identifying metadata.

All canonical modes query a stable collection partitioned by `example_id`.

## Signal Definitions In Current Code

| Signal | Current implementation |
| --- | --- |
| `dense_raw` | `1.0 - cosine_distance` from direct Chroma query |
| `sparse_raw` | Maximum of `_exact_phrase_score()` and `_all_terms_score()` over document text/summary |
| `grammar_score` | Query grammar-frame match against grammar-cache frames, when passed |
| `metadata_score` | Benchmark metadata signal; ground-truth session/evidence hints were removed in Phase 1 |
| `emotion_score` | Implemented but query emotion terms are explicitly empty; weight is `0.00` |
| `temporal_score` | Query temporal-frame overlap against temporal cache events |
| `temporal_pair_score` | Event-target pair and graph-link score for gated multihop queries |

Signals that participate are min-max normalized over the retrieved candidate
pool before fixed-weight fusion.

## `vector_only`

| Item | Detail |
| --- | --- |
| Purpose | Dense semantic retrieval baseline |
| Input memory unit | Cleaned session text document plus identifying primitive metadata |
| Signals used | Chroma embedding similarity only |
| Scoring flow | Embed query, query Chroma with `example_id` filter, rank by Chroma distance-derived similarity |
| Relevant code | `retrieval_dispatcher.py::run_retrieval`, `reconstruct_vector_candidates` |
| Required caches | None |
| Known limitations | No lexical, temporal, graph, or contextual reranking |
| Use | Baseline for cleaned comparisons |
| Status | **Canonical** |

Unlike the clean-hybrid family, the current `vector_only` branch does not
receive the expected-session metadata score.

## `clean_hybrid`

| Item | Detail |
| --- | --- |
| Purpose | Rerank dense candidates with isolated benchmark fusion |
| Input memory unit | Same cleaned session documents; top dense candidate pool is `max(top_k, 15)` |
| Signals used in the current runner | Dense, sparse, metadata; emotion is disabled and grammar cache is not passed for this exact mode |
| Fixed weight table | Dense `0.35`, sparse `0.40`, grammar `0.15`, metadata `0.10`, emotion `0.00` |
| Relevant code | `clean_hybrid_retriever.py::clean_hybrid_retrieve`, `retrieval_dispatcher.py::run_retrieval` |
| Required caches | None for the canonical `clean_hybrid` dispatch |
| Known limitations | Metadata signal is intentionally narrow after the integrity fix; exact behavior should remain frozen unless a new benchmark run is planned |
| Use | Corrected hybrid baseline in the cleaned-500 matrix |
| Status | **Canonical corrected benchmark mode** |

Although a grammar weight exists, the current runner sets candidate
`grammar_score` to zero for `clean_hybrid` because it passes no grammar cache
for that exact mode.

## `clean_hybrid_temporal`

| Item | Detail |
| --- | --- |
| Purpose | Add single-candidate temporal relevance to clean-hybrid reranking |
| Input memory unit | Cleaned session documents plus identifiers used to look up cache entries |
| Signals used | Dense, sparse, grammar, metadata, temporal when non-zero; emotion disabled |
| Fixed weight table | Dense `0.30`, sparse `0.35`, grammar `0.10`, temporal `0.15`, metadata `0.10`, emotion `0.00` |
| Relevant code | `clean_hybrid_retriever.py`, `temporal_query_parser.py`, `build_grammar_cache.py`, `build_temporal_cache.py` |
| Required caches | Grammar cache and temporal cache |
| Known limitations | Temporal benefit depends on cache coverage and query signal |
| Use | Recorded temporal ablation and canonical cleaned result |
| Status | **Canonical corrected benchmark mode** |

## `clean_hybrid_temporal_multihop_v2`

| Item | Detail |
| --- | --- |
| Purpose | Rerank multi-event temporal queries using event pairs and graph relations |
| Input memory unit | Cleaned session documents plus `original_memory_id` for graph/cache lookup |
| Signals used | Dense, sparse, grammar, temporal, metadata; gated `temporal_pair_score`; emotion disabled |
| Fixed weight table | Dense `0.25`, sparse `0.30`, grammar `0.10`, temporal `0.15`, temporal-pair `0.10`, metadata `0.10`, emotion `0.00` |
| Relevant code | `clean_hybrid_retriever.py`, `temporal_query_parser_v2.py`, `temporal_multihop_scorer.py`, `retrieval_dispatcher.py` |
| Required caches | Grammar cache, temporal cache, temporal event graph cache |
| Gate | Pair contribution is included only when a candidate pair score exceeds `0.5` for a parsed multi-event query |
| Known limitations | Graph is large; noun-phrase-only event comparisons remain weak |
| Use | Best measured canonical cleaned mode and temporal multihop research path |
| Status | **Canonical corrected benchmark mode** |

Implementation details that matter:

- The v2 parser adds relative/adnominal clause (`relcl` / `acl`) event target
  extraction and quality-based target ordering.
- The graph scorer looks up graph events using `original_memory_id`, fixing a
  prior mismatch with runner-generated stable IDs.
- The runner pre-builds the graph `link_index` once rather than per query.
- The collection storage alias `ch_temporal_mh_v2` changes only the Chroma
  identifier, not the retrieval mode.

## Modes Outside The Canonical Final Matrix

The runner also exposes historical or exploratory modes such as `bm25_only`,
`hybrid_dense_sparse`, `grammar_emotion_reranker`,
`clean_hybrid_grammar`, and `clean_hybrid_temporal_multihop`. They are not
part of the canonical cleaned-500 comparison table and should not be promoted
to canonical status without a new evaluation decision.
