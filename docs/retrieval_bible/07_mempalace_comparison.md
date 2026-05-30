# External Raw Baseline Comparison

## Reference Values Used

The benchmark work used these external raw reference values:

| Reference | Recall@5 | Recall@10 |
| --- | ---: | ---: |
| External raw | 96.6 | 98.2 |

This comparison is limited to raw retrieval figures. It does not compare
against an LLM-assisted/reranked external mode.

## Memory Retrieval Engine Measured Best Rows

| Track | Mode | Recall@1 | Recall@5 | Recall@10 | MRR |
| --- | --- | ---: | ---: | ---: | ---: |
| `user_only` | `clean_hybrid_temporal_multihop_v2` | 88.00% | 97.40% | 98.60% | 0.9204 |
| `all_turns` | `clean_hybrid_temporal_multihop_v2` | 82.00% | 95.60% | 98.00% | 0.8808 |

## Track Interpretation

`user_only` includes only user utterances and is the closest available
apples-to-apples path for comparison with external raw evaluation.

`all_turns` preserves user and assistant text, including suggestion context.
It is the richer-context retrieval path and should be read as a
product-oriented retrieval test rather than a strict raw-comparison
replacement.

## Numeric Comparison

On the corrected `user_only` result, Memory Retrieval Engine's measured best
mode is higher than the cited external raw figures by a smaller margin than the
superseded pre-integrity run:

| Metric | External raw | Memory Retrieval Engine measured `user_only` best | Difference |
| --- | ---: | ---: | ---: |
| Recall@5 | 96.60% | 97.40% | +0.80 points |
| Recall@10 | 98.20% | 98.60% | +0.40 points |

For `all_turns`, Memory Retrieval Engine's corrected multihop-v2 row does not
beat the external raw reference:

| Metric | External raw | Memory Retrieval Engine corrected `all_turns` multihop-v2 | Difference |
| --- | ---: | ---: | ---: |
| Recall@5 | 96.60% | 95.60% | -1.00 points |
| Recall@10 | 98.20% | 98.00% | -0.20 points |

## Required Qualification

The pre-integrity 99.0% `user_only` Recall@5 result is superseded. The current
defensible wording is:

> The corrected `user_only` clean-hybrid-temporal-multihop-v2 result exceeds
> the external raw Recall@5 and Recall@10 references by a smaller margin;
> the corrected `all_turns` result does not exceed the external raw reference.

Do not compare this system to any LLM-rerank or 100% mode unless an
LLM reranking/reader stage is implemented and separately evaluated here.
