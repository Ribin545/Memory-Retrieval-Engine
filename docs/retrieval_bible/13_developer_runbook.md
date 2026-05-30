# Developer Runbook

## A. What This System Is

This is the external benchmark system for Memory Retrieval Engine.
It validates retrieval behavior against external datasets without touching the
production Chroma database.

The canonical benchmark is cleaned LongMemEval-S with 500 examples.

Canonical tracks:

- `user_only`: closest raw-compatible comparison.
- `all_turns`: richer retrieval context track, joining user and assistant
  turns with role labels.

Current corrected trusted best rows:

| Track | Mode | Recall@1 | Recall@5 | Recall@10 | MRR |
| --- | --- | ---: | ---: | ---: | ---: |
| `user_only` | `clean_hybrid_temporal_multihop_v2` | 88.00% | 97.40% | 98.60% | 0.9204 |
| `all_turns` | `clean_hybrid_temporal_multihop_v2` | 82.00% | 95.60% | 98.00% | 0.8808 |

The refactored DDD runner reproduced the corrected cleaned-500 matrix exactly.
See
[`outputs/benchmarks/refactored_cleaned500_matrix_report.md`](../../outputs/benchmarks/refactored_cleaned500_matrix_report.md).

## B. Directory Map

| Path | Purpose |
| --- | --- |
| `app/benchmarks/` | Canonical benchmark CLI, scoring modules, validators, cache builders, pointer utilities |
| `app/benchmarks/archive/` | Historical/non-canonical diagnostic runners preserved for reproducibility |
| `app/archive_non_retrieval/` | Quarantined non-retrieval Python/runtime/history code; preserved, not active |
| `archive_non_retrieval/frontend/` | Quarantined frontend/demo UI code; preserved, not active |
| `app/retrieval_domain/applications/` | DDD application services: runner workflow, index build, evaluation loop, reporting, retrieval dispatch |
| `app/retrieval_domain/dataset/` | Dataset Context: raw JSON repository, LongMemEval cleaned/legacy adapters, facade |
| `app/retrieval_domain/evaluation/` | Evaluation Context: hit policies and metric aggregation |
| `app/retrieval_domain/retrieval/` | Retrieval contracts and candidate mapper |
| `app/retrieval_domain/indexing/` | Index registry models, metadata contract, collection-name policy |
| `app/retrieval_domain/infrastructure/` | Benchmark-only Chroma repository and retrieval-owned path config |
| `app/retrieval_domain/features/` | Feature-cache provenance, parser/cache version labels, compatibility validation |
| `docs/retrieval_bible/` | System docs, architecture, runbooks, inventory |
| `outputs/benchmarks/` | Reports, raw result JSON, phase reports |
| `outputs/benchmarks/registry/` | Index and feature-cache registry JSON |
| `marked_for_delete/` | Ignored local deletion-staging folder; should stay clear before publishing |

Remaining active top-level compatibility modules:

| Path | Why it remains |
| --- | --- |
| `app/dynamic_action_frame_extractor.py` | Compatibility wrapper for the retrieval-owned grammar/action-frame extractor |
| `app/memory_retriever.py` | Dense retrieval helper path still reachable from canonical benchmark code |
| `app/hybrid_memory_retriever.py` | Sparse/hybrid helper path still reachable from canonical benchmark code |
| `app/vector_store.py` | Legacy vector query adapter still reachable and must be isolated carefully |
| `app/paths.py` | Compatibility wrapper around `app/retrieval_domain/infrastructure/path_config.py` |

## C. Canonical Environment Setup

Canonical environment:

- Python `3.11.9`
- `chromadb==0.6.3`
- `posthog<3`
- requirements file: `app/benchmarks/requirements_chroma063.txt`
- isolated Chroma path:
  `data/external/indexes/chroma_cleaned_500_py311_chroma063/`
- batch size `50`
- Chroma ingestion API: `collection.add()`, not `upsert()`

Never point benchmark commands at `data/protected_legacy_chroma_db/`.

PowerShell setup:

```powershell
cmd /c start.bat
```

`start.bat` is the preferred first-run bootstrap. It calls
`setup_benchmark_env.bat`, downloads the cleaned 500-example LongMemEval-S
dataset if missing, removes stale temporary cache files, builds missing feature
caches, runs guards, and performs small validation without requiring secrets.

Lower-level environment setup:

```powershell
.\setup_benchmark_env.bat
```

The batch script is the preferred setup path. It checks for Python `3.11.9`,
downloads and installs it if missing, rebuilds `.venv_benchmark_chroma063` only
when needed, installs `app/benchmarks/requirements_chroma063.txt`, and verifies
`chromadb==0.6.3` plus `posthog<3`.

Useful flags:

```powershell
.\setup_benchmark_env.bat --smoke-test
.\setup_benchmark_env.bat --guards
.\setup_benchmark_env.bat --clear-chroma
```

`--clear-chroma` calls the narrow benchmark-only cleanup script and refuses the
production Chroma DB path.

Manual equivalent:

```powershell
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py --version
& $py -m venv .venv_benchmark_chroma063
& .\.venv_benchmark_chroma063\Scripts\python.exe -m pip install --upgrade pip
& .\.venv_benchmark_chroma063\Scripts\python.exe -m pip install -r app\benchmarks\requirements_chroma063.txt
& .\.venv_benchmark_chroma063\Scripts\python.exe -c "import sys, chromadb, posthog; print(sys.version.split()[0]); print(chromadb.__version__); print(posthog.__version__)"
```

If the venv launcher points at a blocked user-local interpreter, use the
verified fallback invocation:

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
& "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe" -S -c "import sys, chromadb; print(sys.version.split()[0]); print(chromadb.__version__)"
```

## D. Safe Preflight Checklist

Run before benchmark or refactor work:

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\validate_benchmark_integrity.py
& $py -S app\benchmarks\validate_candidate_schema.py
& $py -S app\benchmarks\validate_index_registry.py
& $py -S app\benchmarks\validate_feature_cache_registry.py
& $py -S app\benchmarks\validate_adapter_evaluation_boundary.py
```

What they protect:

| Guard | Protects |
| --- | --- |
| `validate_benchmark_integrity.py` | Ground truth cannot enter retrieval scoring/request construction |
| `validate_candidate_schema.py` | Candidate output shape is stable and ground-truth-free |
| `validate_index_registry.py` | Registry paths, Chroma version, metadata contract, counts, artifacts |
| `validate_feature_cache_registry.py` | Required feature caches and parser/cache compatibility |
| `validate_adapter_evaluation_boundary.py` | Dataset/Evaluation/Retrieval import and ownership boundaries |

## E. Small Validation Commands

`user_only`:

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\run_external_benchmark.py --benchmark longmemeval_s --data-path data\external\longmemeval_cleaned --limit 20 --top-k 10 --mode clean_hybrid_temporal_multihop_v2 --skip-model-reload --use-existing-index --schema cleaned --turns-mode user_only --output-dir outputs\benchmarks\validation\user_only
```

`all_turns`:

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\run_external_benchmark.py --benchmark longmemeval_s --data-path data\external\longmemeval_cleaned --limit 20 --top-k 10 --mode clean_hybrid_temporal_multihop_v2 --skip-model-reload --use-existing-index --schema cleaned --turns-mode all_turns --output-dir outputs\benchmarks\validation\all_turns
```

Expected small-run pattern:

- `user_only`: R@1 about `95%`, R@5 `100%`, R@10 `100%`, MRR `0.9750`.
- `all_turns`: R@1 about `65%`, R@5 `95%`, R@10 `95%`, MRR `0.7667`.

## F. Full Corrected Cleaned-500 Matrix

Only run this after Python 3.11.9 is restored and all guards pass.

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
$modes = @("vector_only", "clean_hybrid", "clean_hybrid_temporal", "clean_hybrid_temporal_multihop_v2")
$turnsModes = @("user_only", "all_turns")
foreach ($turns in $turnsModes) {
  foreach ($mode in $modes) {
    Write-Output "PHASE cleaned500 turns=$turns mode=$mode"
    & $py -S app\benchmarks\run_external_benchmark.py --benchmark longmemeval_s --data-path data\external\longmemeval_cleaned --schema cleaned --turns-mode $turns --limit 500 --top-k 10 --mode $mode --skip-model-reload --batch-size 50 --persist-dir data\external\indexes\chroma_cleaned_500_py311_chroma063 --output-dir "outputs\benchmarks\cleaned500_runs\$turns\$mode"
    if ($LASTEXITCODE -ne 0) { throw "Benchmark failed: turns=$turns mode=$mode" }
  }
}
```

If reusing existing indexes causes any zero-candidate or count mismatch, stop,
clear only the isolated benchmark Chroma path, and rebuild fresh.

## G. Clear Benchmark Chroma Safely

Use only:

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\clear_benchmark_chroma.py
```

Never manually delete or point scripts at `data/protected_legacy_chroma_db/`.

## H. Where To Edit Common Tasks

| Task | Edit here |
| --- | --- |
| Add/change dataset schema | `app/retrieval_domain/dataset/` |
| Change evaluation hit policy | `app/retrieval_domain/evaluation/` |
| Change candidate output shape | `app/retrieval_domain/retrieval/candidate_mapper.py`, `app/retrieval_domain/retrieval_models.py` |
| Change Chroma storage behavior | `app/retrieval_domain/infrastructure/chroma_index_repository.py`, `app/retrieval_domain/indexing/` |
| Change retrieval-owned path constants | `app/retrieval_domain/infrastructure/path_config.py` |
| Change grammar/action-frame extraction | `app/retrieval_domain/features/grammar_frame_extractor.py`; keep `app/dynamic_action_frame_extractor.py` as compatibility wrapper |
| Change temporal parser | `app/benchmarks/temporal_query_parser_v2.py`, `app/retrieval_domain/features/temporal_versions.py` |
| Change reports | `app/retrieval_domain/applications/generate_benchmark_report.py` |
| Change CLI wrapper concerns | `app/benchmarks/run_external_benchmark.py` |
| Change benchmark workflow | `app/retrieval_domain/applications/external_benchmark_runner.py` |

## I. Files Not To Edit Casually

- `data/protected_legacy_chroma_db/`
- `app/benchmarks/archive/*`
- `app/archive_non_retrieval/*`
- `archive_non_retrieval/frontend/*`
- benchmark result artifacts unless intentionally regenerating them
- `outputs/benchmarks/benchmark_integrity_fix_results.json`
- `outputs/benchmarks/refactored_cleaned500_matrix_results.json`
- production retrieval modules, unless explicitly doing a production refactor

## J. Ground-Truth Leakage Rules

Allowed in retrieval:

- query text
- normalized memory/index candidates
- `example_id` only for benchmark haystack filtering
- retrieval mode config
- feature caches
- timestamps
- pointer/source metadata

Allowed only after retrieval, inside evaluation:

- `expected_session_ids`

Forbidden in retrieval:

- `answer_session_ids`
- `expected_session_ids`
- `expected_evidence`
- answer text
- `query_session_id` derived from ground truth
- `query_evidence_ids`
- `_query_evidence_ids`
- `correct_session_id`

## K. Script Status Guide

See [10_script_inventory.md](./10_script_inventory.md).

Summary:

- Canonical: public CLI, clean-hybrid retriever, temporal parser/scorer,
  Chroma smoke/clear tools, validators, requirements.
- Supporting: cache builders, pointer tools, schema exploration, DDD services.
- Archived: historical diagnostics in `app/benchmarks/archive/`.
- Quarantined/non-retrieval: frontend/demo, emotional response/planning,
  LLM judge, response policy, reengagement, scratch/debug, and older product
  runtime modules under `app/archive_non_retrieval/` and
  `archive_non_retrieval/frontend/`.
- Experimental/future: `locomo_adapter.py` remains available, but LoCoMo is
  not canonical yet.

The active codebase is retrieval-only. Do not reintroduce quarantined modules
into active imports unless a future task explicitly expands the product scope
outside retrieval.

Post-cleanup stabilization proved the full cleaned-500 matrix still reproduces
exactly. See
[`outputs/benchmarks/post_cleanup_cleaned500_matrix_report.md`](../../outputs/benchmarks/post_cleanup_cleaned500_matrix_report.md)
and
[`outputs/benchmarks/post_cleanup_stabilization_report.md`](../../outputs/benchmarks/post_cleanup_stabilization_report.md).

## L. Common Failure Modes And Fixes

| Failure | Likely cause | Fix |
| --- | --- | --- |
| Chroma compaction error | Version/storage fragility | Use Python 3.11.9, Chroma 0.6.3, fresh isolated benchmark path |
| Chroma disk-full/count mismatch | Stale/deleted collections or disk pressure | Stop; run `clear_benchmark_chroma.py`; rebuild isolated benchmark indexes |
| Collection name length error | Chroma 0.6.3 limit | Use `CollectionNamePolicy`; preserve `ch_temporal_mh_v2` alias |
| Feature cache provenance warning | Existing cache lacks embedded dataset/schema/turns metadata | Warning is expected unless compatibility is false |
| Missing Python 3.11.9 venv | Broken launcher or removed interpreter | Restore Python 3.11.9 and use `python -S` with benchmark `PYTHONPATH` if needed |
| Accidental production DB risk | Wrong persist path | Stop; verify path is under `data/external/indexes/` |
| Metric mismatch after refactor | Behavior changed or stale index | Stop; inspect candidate/ranking diffs; do not tune weights |
| Guard failure: forbidden field | Ground truth leaked into retrieval or metadata | Remove forbidden field from retrieval path; keep it in evaluation only |

## M. Add A New Retrieval Mode Safely

1. Define the mode name and status.
2. Add dispatch in `app/retrieval_domain/applications/retrieval_dispatcher.py`.
3. Keep scoring in a clearly owned retrieval/scoring module.
4. Ensure candidate mapper returns the canonical candidate shape.
5. Update registry/mode docs and script inventory.
6. Run all guards.
7. Run limit-20 `user_only` and `all_turns`.
8. Do not make external comparison claims until full cleaned-500 rerun passes.

## N. Add A New Benchmark Dataset Safely

1. Do schema exploration first.
2. Create a Dataset Context adapter.
3. Define explicit GroundTruth and HitPolicy ownership.
4. Avoid fuzzy matching unless clearly legacy/non-canonical.
5. Add index/registry support.
6. Run a limit validation.
7. Only mark canonical after environment, storage, metrics, and reports are
   frozen.

## O. Update Docs After Changes

Update the docs that changed:

- [README.md](./README.md)
- [10_script_inventory.md](./10_script_inventory.md)
- [11_known_issues_and_refactor_roadmap.md](./11_known_issues_and_refactor_roadmap.md)
- [12_domain_driven_design_architecture.md](./12_domain_driven_design_architecture.md)
- [artifacts_index.md](./artifacts_index.md)
- relevant mode/schema docs such as [04_retrieval_modes.md](./04_retrieval_modes.md)
  and [05_adapters_and_schema.md](./05_adapters_and_schema.md)
