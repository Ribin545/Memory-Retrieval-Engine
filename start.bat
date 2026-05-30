@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Memory Retrieval Engine bootstrap.
rem This script prepares the canonical cleaned LongMemEval-S benchmark path.
rem It installs the pinned Python/Chroma environment, downloads the cleaned
rem 500-question dataset if missing, builds required feature caches if missing,
rem and runs validation without touching production Chroma.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%" || exit /b 1

set "VENV_DIR=%ROOT%\.venv_benchmark_chroma063"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "DATA_DIR=%ROOT%\data\external\longmemeval_cleaned"
set "DATA_FILE=%DATA_DIR%\longmemeval_s_cleaned.json"
set "INDEX_DIR=%ROOT%\data\external\indexes"
set "CHROMA_DIR=%INDEX_DIR%\chroma_cleaned_500_py311_chroma063"
set "PRODUCTION_CHROMA_DIR=%ROOT%\data\protected_legacy_chroma_db"
set "GRAMMAR_CACHE=%INDEX_DIR%\longmemeval_s_grammar_cache_v2.json"
set "TEMPORAL_CACHE=%INDEX_DIR%\longmemeval_s_temporal_cache.json"
set "TEMPORAL_GRAPH=%INDEX_DIR%\longmemeval_s_temporal_event_graph.json"
set "MODE=clean_hybrid_temporal_multihop_v2"
set "RUN_VALIDATION=1"
set "RUN_FULL_ALL_TURNS=0"
set "RUN_FULL_USER_ONLY=0"
set "RUN_FULL_MATRIX=0"
set "FORCE_DOWNLOAD=0"
set "FORCE_DOWNLOAD_ARG="
set "REBUILD_CACHES=0"
set "REBUILD_INDEX=0"
set "CLEAR_CHROMA=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--help" goto help
if /I "%~1"=="--skip-validation" set "RUN_VALIDATION=0"& shift & goto parse_args
if /I "%~1"=="--full-all-turns" set "RUN_FULL_ALL_TURNS=1"& shift & goto parse_args
if /I "%~1"=="--full-user-only" set "RUN_FULL_USER_ONLY=1"& shift & goto parse_args
if /I "%~1"=="--full-matrix" set "RUN_FULL_MATRIX=1"& shift & goto parse_args
if /I "%~1"=="--force-download" set "FORCE_DOWNLOAD=1"& set "FORCE_DOWNLOAD_ARG=--force"& shift & goto parse_args
if /I "%~1"=="--rebuild-caches" set "REBUILD_CACHES=1"& shift & goto parse_args
if /I "%~1"=="--rebuild-index" set "REBUILD_INDEX=1"& shift & goto parse_args
if /I "%~1"=="--clear-chroma" set "CLEAR_CHROMA=1"& shift & goto parse_args
echo Unknown argument: %~1
goto help_error

:help
echo.
echo Usage: start.bat [options]
echo.
echo Default:
echo   Setup environment, download dataset if missing, build missing caches,
echo   run guards, and run limit-20 user_only/all_turns validation.
echo.
echo Options:
echo   --skip-validation    Prepare files/env only; do not run guards or validation.
echo   --full-all-turns     Run full cleaned-500 all_turns current-best mode.
echo   --full-user-only     Run full cleaned-500 user_only current-best mode.
echo   --full-matrix        Run all 8 cleaned-500 canonical cells.
echo   --force-download     Re-download cleaned LongMemEval-S dataset.
echo   --rebuild-caches     Rebuild grammar, temporal, and temporal graph caches.
echo   --rebuild-index      Rebuild current-best user_only/all_turns Chroma collections.
echo   --clear-chroma       Clear only the isolated benchmark Chroma directory first.
echo.
echo This script never opens or deletes %PRODUCTION_CHROMA_DIR%.
exit /b 0

:help_error
call :help
exit /b 2

:args_done
echo [Memory Retrieval Engine] Bootstrap
echo Root: %ROOT%
echo Dataset: %DATA_FILE%
echo Benchmark Chroma: %CHROMA_DIR%
echo Production Chroma untouched: %PRODUCTION_CHROMA_DIR%
echo.

call :run_setup || exit /b 1
call :ensure_dataset || exit /b 1
call :prefetch_embedding_model || exit /b 1
call :ensure_caches || exit /b 1

if "%REBUILD_INDEX%"=="1" call :bootstrap_full_index || exit /b 1
if not exist "%CHROMA_DIR%\chroma.sqlite3" call :bootstrap_full_index || exit /b 1

if "%RUN_VALIDATION%"=="1" call :run_guards_and_small_validation || exit /b 1
if "%RUN_FULL_ALL_TURNS%"=="1" call :run_full_one all_turns || exit /b 1
if "%RUN_FULL_USER_ONLY%"=="1" call :run_full_one user_only || exit /b 1
if "%RUN_FULL_MATRIX%"=="1" call :run_full_matrix || exit /b 1

echo.
echo PASS: Memory Retrieval Engine bootstrap complete.
echo No secrets were required. Production Chroma was not opened.
exit /b 0

:run_setup
echo [1/6] Setting up pinned benchmark environment...
if "%CLEAR_CHROMA%"=="1" (
  call "%ROOT%\setup_benchmark_env.bat" --clear-chroma || exit /b 1
) else (
  call "%ROOT%\setup_benchmark_env.bat" || exit /b 1
)
if not exist "%VENV_PY%" (
  echo ERROR: benchmark Python not found after setup: %VENV_PY%
  exit /b 1
)
exit /b 0

:ensure_dataset
echo [2/6] Ensuring cleaned LongMemEval-S dataset...
if "%FORCE_DOWNLOAD%"=="1" goto download_dataset
if exist "%DATA_FILE%" (
  echo Dataset already present: %DATA_FILE%
  "%VENV_PY%" -c "import json; p=r'%DATA_FILE%'; data=json.load(open(p, encoding='utf-8')); assert len(data)==500, len(data); print('examples=500')" || exit /b 1
  exit /b 0
)

:download_dataset
echo Downloading cleaned LongMemEval-S dataset...
"%VENV_PY%" "%ROOT%\app\benchmarks\schema_exploration\longmemeval\download_cleaned_longmemeval.py" %FORCE_DOWNLOAD_ARG% || exit /b 1
"%VENV_PY%" -c "import json; p=r'%DATA_FILE%'; data=json.load(open(p, encoding='utf-8')); assert len(data)==500, len(data); print('examples=500')" || exit /b 1
exit /b 0

:prefetch_embedding_model
echo [3/6] Ensuring embedding model is cached...
"%VENV_PY%" -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2'); print('all-MiniLM-L6-v2 ready')" || exit /b 1
exit /b 0

:ensure_caches
echo [4/6] Ensuring feature caches...
if not exist "%INDEX_DIR%" mkdir "%INDEX_DIR%" || exit /b 1
if exist "%TEMPORAL_GRAPH%.tmp" (
  echo Removing stale temporal graph tmp file: %TEMPORAL_GRAPH%.tmp
  del /f /q "%TEMPORAL_GRAPH%.tmp" || exit /b 1
)
if "%REBUILD_CACHES%"=="1" (
  if exist "%GRAMMAR_CACHE%" del /f /q "%GRAMMAR_CACHE%" || exit /b 1
  if exist "%TEMPORAL_CACHE%" del /f /q "%TEMPORAL_CACHE%" || exit /b 1
  if exist "%TEMPORAL_GRAPH%" del /f /q "%TEMPORAL_GRAPH%" || exit /b 1
)
if not exist "%GRAMMAR_CACHE%" (
  echo Building grammar cache...
  "%VENV_PY%" "%ROOT%\app\benchmarks\build_grammar_cache.py" --benchmark longmemeval_s --data-path "%DATA_DIR%" --output-dir "%INDEX_DIR%" --schema cleaned --turns-mode all_turns || exit /b 1
) else (
  echo Grammar cache already present.
)
if not exist "%TEMPORAL_CACHE%" (
  echo Building temporal cache...
  "%VENV_PY%" "%ROOT%\app\benchmarks\build_temporal_cache.py" --benchmark longmemeval_s --data-path "%DATA_DIR%" --output-dir "%INDEX_DIR%" --schema cleaned --turns-mode all_turns || exit /b 1
) else (
  echo Temporal cache already present.
)
if not exist "%TEMPORAL_GRAPH%" (
  echo Building temporal event graph. This can take a while.
  "%VENV_PY%" "%ROOT%\app\benchmarks\build_temporal_event_graph.py" --benchmark longmemeval_s --temporal-cache-path "%TEMPORAL_CACHE%" --output-dir "%INDEX_DIR%" || exit /b 1
) else (
  echo Temporal event graph already present.
)
exit /b 0

:bootstrap_full_index
echo [5/6] Bootstrapping full current-best Chroma collections...
call :run_full_one user_only bootstrap_index || exit /b 1
call :run_full_one all_turns bootstrap_index || exit /b 1
exit /b 0

:run_guards_and_small_validation
echo [6/6] Running guards and small validation...
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_benchmark_integrity.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_candidate_schema.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_index_registry.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_feature_cache_registry.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_adapter_evaluation_boundary.py" || exit /b 1
call :run_small_one user_only || exit /b 1
call :run_small_one all_turns || exit /b 1
exit /b 0

:run_small_one
set "TURNS=%~1"
echo Running limit-20 validation: %TURNS%
"%VENV_PY%" "%ROOT%\app\benchmarks\run_external_benchmark.py" --benchmark longmemeval_s --data-path "%DATA_DIR%" --limit 20 --top-k 10 --mode %MODE% --use-existing-index --schema cleaned --turns-mode %TURNS% --output-dir "%ROOT%\outputs\benchmarks\start_validation\%TURNS%" || exit /b 1
exit /b 0

:run_full_one
set "TURNS=%~1"
set "RUN_NAME=%~2"
if "%RUN_NAME%"=="" set "RUN_NAME=full500"
set "USE_EXISTING=--use-existing-index"
if "%RUN_NAME%"=="bootstrap_index" set "USE_EXISTING="
echo Running full cleaned-500: %TURNS% (%RUN_NAME%)
"%VENV_PY%" "%ROOT%\app\benchmarks\run_external_benchmark.py" --benchmark longmemeval_s --data-path "%DATA_DIR%" --limit 500 --top-k 10 --mode %MODE% %USE_EXISTING% --schema cleaned --turns-mode %TURNS% --batch-size 50 --persist-dir "%CHROMA_DIR%" --output-dir "%ROOT%\outputs\benchmarks\start_%RUN_NAME%\%TURNS%\%MODE%" || exit /b 1
exit /b 0

:run_full_matrix
for %%T in (user_only all_turns) do (
  for %%M in (vector_only clean_hybrid clean_hybrid_temporal clean_hybrid_temporal_multihop_v2) do (
    echo Running full matrix cell: %%T %%M
    "%VENV_PY%" "%ROOT%\app\benchmarks\run_external_benchmark.py" --benchmark longmemeval_s --data-path "%DATA_DIR%" --limit 500 --top-k 10 --mode %%M --use-existing-index --schema cleaned --turns-mode %%T --batch-size 50 --persist-dir "%CHROMA_DIR%" --output-dir "%ROOT%\outputs\benchmarks\start_full_matrix\%%T\%%M" || exit /b 1
  )
)
exit /b 0
