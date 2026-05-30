# Pointer System

## Phase 5 Pointer Provenance

The feature cache registry records pointer manifest provenance as
`pointer_manifest_v1_legacy`. Pointer resolution remains optional for current
raw retrieval validation; missing pointer manifest provenance is a warning
unless a future mode explicitly requires pointer resolution. The cleaned
pointer compatibility gap remains open because the current manifest builder is
documented as legacy/default-format oriented.

## Purpose

Pointer-based retrieval support was introduced to attach stable provenance to
external benchmark candidates. A pointer allows a candidate to refer back to
its originating source JSON location, supporting audit and future
source-of-truth verification without requiring provenance to be inferred from
ranked text.

## Implemented Components

| Component | Function |
| --- | --- |
| `pointer_manifest.py` | Builds a manifest from pointer IDs to JSON source paths, hashes, and previews |
| `pointer_resolver.py` | Resolves single or multiple pointers to source text and verifies hashes |
| `validate_pointer_manifest.py` | Validates resolution and hash consistency |
| `BuildBenchmarkIndex` / `run_external_benchmark.py` | Stores `pointer_id` among primitive Chroma metadata through the benchmark index build path |
| `clean_hybrid_retriever.py` | Passes `pointer_id` into candidate dictionaries |

## Candidate Shape Change

Pointer integration is additive: candidate dictionaries gained:

```python
{"pointer_id": "..."}
```

Retrieval fields such as session ID, original memory ID, source text, scores,
and ranking diagnostics remain part of the candidate shape.

Under the current stabilized Chroma ingestion path, `source_text` is the
Chroma document payload, while `pointer_id` is small metadata. The older
pointer integration report predates this metadata minimization and its
description of text in metadata should be read as historical.

## Compatibility Status

The pointer integration validation reported identical metrics before and after
adding pointer IDs for its tested external paths, plus 100/100 pointer
resolution/hash validation on a sample.

Pointer IDs are passive in the canonical scoring flow:

- dense retrieval operates on document embeddings;
- clean-hybrid scoring uses text and caches;
- temporal scoring uses temporal cache and event graph;
- pointer resolution is optional for audit/debug use.

## Incomplete Migration And Caveats

| Area | Current caveat |
| --- | --- |
| Cleaned LongMemEval-S pointer format | The cleaned adapter emits `lme_cleaned:{example_id}:{session_id}`, while `pointer_manifest.py` documents/builds the older `lme:{question_id}:doc:{doc_idx}` default format; cleaned manifest resolution requires review before relying on it |
| Deferred text retrieval | Not implemented; canonical indexing still embeds and stores source text as document text |
| LoCoMo composite units | Resolver supports `resolve_composite()`, but the report states composite session/window resolution is not fully wired into retrieval |
| Production migration | Pointer support is external-benchmark foundation work, not a completed production migration |

## Evidence

- [Pointer integration report](../../outputs/benchmarks/pointer_integration_report.md)
- [Pointer resolver validation](../../outputs/benchmarks/pointer_resolver_validation.md)
- [Pointer manifest report](../../outputs/benchmarks/pointer_manifest_report.md)
