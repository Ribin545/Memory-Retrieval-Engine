# Command Cheatsheet

All commands are Windows PowerShell.

## Environment

Preferred bootstrap:

```powershell
cmd /c start.bat
```

This restores the pinned benchmark environment, downloads the cleaned
LongMemEval-S 500-example dataset if missing, ensures required feature caches,
runs guards, and performs small validation. It does not require API keys.

Lower-level environment setup:

```powershell
.\setup_benchmark_env.bat
```

Optional smoke/guard modes:

```powershell
.\setup_benchmark_env.bat --smoke-test
.\setup_benchmark_env.bat --guards
.\setup_benchmark_env.bat --clear-chroma
```

The script installs Python `3.11.9` if missing, rebuilds only the benchmark
venv when needed, installs `chromadb==0.6.3` and `posthog<3`, and never targets
`data\protected_legacy_chroma_db`.

Manual equivalent:

```powershell
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py --version
& $py -m venv .venv_benchmark_chroma063
& .\.venv_benchmark_chroma063\Scripts\python.exe -m pip install -r app\benchmarks\requirements_chroma063.txt
```

Fallback invocation when the venv launcher is blocked:

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S -c "import sys, chromadb; print(sys.version.split()[0]); print(chromadb.__version__)"
```

## Guards

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\validate_benchmark_integrity.py
& $py -S app\benchmarks\validate_candidate_schema.py
& $py -S app\benchmarks\validate_index_registry.py
& $py -S app\benchmarks\validate_feature_cache_registry.py
& $py -S app\benchmarks\validate_adapter_evaluation_boundary.py
```

## Limit-20 Validation

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\run_external_benchmark.py --benchmark longmemeval_s --data-path data\external\longmemeval_cleaned --limit 20 --top-k 10 --mode clean_hybrid_temporal_multihop_v2 --skip-model-reload --use-existing-index --schema cleaned --turns-mode user_only --output-dir outputs\benchmarks\validation\user_only
& $py -S app\benchmarks\run_external_benchmark.py --benchmark longmemeval_s --data-path data\external\longmemeval_cleaned --limit 20 --top-k 10 --mode clean_hybrid_temporal_multihop_v2 --skip-model-reload --use-existing-index --schema cleaned --turns-mode all_turns --output-dir outputs\benchmarks\validation\all_turns
```

## Full 8-Cell Cleaned-500 Matrix

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
$modes = @("vector_only", "clean_hybrid", "clean_hybrid_temporal", "clean_hybrid_temporal_multihop_v2")
$turnsModes = @("user_only", "all_turns")
foreach ($turns in $turnsModes) {
  foreach ($mode in $modes) {
    & $py -S app\benchmarks\run_external_benchmark.py --benchmark longmemeval_s --data-path data\external\longmemeval_cleaned --schema cleaned --turns-mode $turns --limit 500 --top-k 10 --mode $mode --skip-model-reload --batch-size 50 --persist-dir data\external\indexes\chroma_cleaned_500_py311_chroma063 --output-dir "outputs\benchmarks\cleaned500_runs\$turns\$mode"
    if ($LASTEXITCODE -ne 0) { throw "Benchmark failed: $turns $mode" }
  }
}
```

## Clear Benchmark Chroma

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\clear_benchmark_chroma.py
```

## Chroma Smoke Test

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\chroma_smoke_test.py --persist-dir data\external\indexes\chroma_cleaned_500_py311_chroma063
```

## Compile Checks

```powershell
python -m py_compile app\benchmarks\run_external_benchmark.py app\retrieval_domain\applications\external_benchmark_runner.py app\retrieval_domain\applications\retrieval_dispatcher.py
```

## Registry Validation

```powershell
$env:PYTHONPATH = (Resolve-Path ".venv_benchmark_chroma063\Lib\site-packages").Path
$py = "C:\Users\tltp2128\AppData\Local\Programs\Python\Python311\python.exe"
& $py -S app\benchmarks\validate_index_registry.py
& $py -S app\benchmarks\validate_feature_cache_registry.py
```

## Output Locations

| Output | Location |
| --- | --- |
| Run reports | `outputs/benchmarks/<run_name>/` |
| Index registries | `outputs/benchmarks/registry/` |
| Refactored full-matrix proof | `outputs/benchmarks/refactored_cleaned500_matrix_report.md` |
| Local deletion-staging folder, ignored and normally clear | `marked_for_delete/` |
| Current runbook | `docs/retrieval_bible/13_developer_runbook.md` |
