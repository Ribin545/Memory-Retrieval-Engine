@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Canonical Memory Retrieval Engine benchmark environment bootstrap.
rem - Installs Python 3.11.9 if a compatible interpreter is missing.
rem - Rebuilds .venv_benchmark_chroma063 when the venv is absent or wrong.
rem - Installs app\benchmarks\requirements_chroma063.txt.
rem - Verifies chromadb==0.6.3 and posthog<3.
rem - Never touches the production Chroma DB.

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
cd /d "%ROOT%" || exit /b 1

set "PYTHON_VERSION_REQUIRED=3.11.9"
set "PYTHON_INSTALL_DIR=%LOCALAPPDATA%\Programs\Python\Python3119-memory-retrieval"
set "PYTHON_EXE=%PYTHON_INSTALL_DIR%\python.exe"
set "PYTHON_USERLOCAL_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
set "PYTHON_TMP_EXE=C:\tmp\Python3119\python.exe"
set "PYTHON_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
set "VENV_DIR=%ROOT%\.venv_benchmark_chroma063"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_FILE=%ROOT%\app\benchmarks\requirements_chroma063.txt"
set "BENCHMARK_CHROMA_DIR=%ROOT%\data\external\indexes\chroma_cleaned_500_py311_chroma063"
set "PRODUCTION_CHROMA_DIR=%ROOT%\data\protected_legacy_chroma_db"

set "RUN_SMOKE=0"
set "RUN_GUARDS=0"
set "CLEAR_CHROMA=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--smoke-test" set "RUN_SMOKE=1"& shift & goto parse_args
if /I "%~1"=="--guards" set "RUN_GUARDS=1"& shift & goto parse_args
if /I "%~1"=="--clear-chroma" set "CLEAR_CHROMA=1"& shift & goto parse_args
if /I "%~1"=="--help" goto help_ok
echo Unknown argument: %~1
goto help_bad

:help_ok
call :print_help
exit /b 0

:help_bad
call :print_help
exit /b 2

:print_help
echo.
echo Usage: setup_benchmark_env.bat [--smoke-test] [--guards] [--clear-chroma]
echo.
echo   --smoke-test    Run the benchmark-only Chroma compaction smoke test.
echo   --guards        Run benchmark integrity/schema/registry/boundary guards.
echo   --clear-chroma  Safely clear only the isolated benchmark Chroma path.
echo.
echo This script never deletes or opens data\protected_legacy_chroma_db.
exit /b 0

:args_done
echo [Memory Retrieval Engine] Benchmark environment setup
echo Root: %ROOT%
echo Required Python: %PYTHON_VERSION_REQUIRED%
echo Venv: %VENV_DIR%
echo.

if not exist "%REQ_FILE%" (
  echo ERROR: Requirements file not found: %REQ_FILE%
  exit /b 1
)

call :ensure_python || exit /b 1
call :ensure_venv || exit /b 1
call :install_requirements || exit /b 1
call :verify_environment || exit /b 1

if "%CLEAR_CHROMA%"=="1" call :clear_chroma || exit /b 1
if "%RUN_SMOKE%"=="1" call :run_smoke || exit /b 1
if "%RUN_GUARDS%"=="1" call :run_guards || exit /b 1

echo.
echo PASS: Canonical benchmark environment is ready.
echo Python: %VENV_PY%
echo Chroma persist path: %BENCHMARK_CHROMA_DIR%
echo Production Chroma untouched: %PRODUCTION_CHROMA_DIR%
exit /b 0

:ensure_python
echo [1/4] Checking Python %PYTHON_VERSION_REQUIRED%...
if exist "%PYTHON_EXE%" (
  for /f "usebackq delims=" %%v in (`"%PYTHON_EXE%" -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2^>nul`) do set "FOUND_VERSION=%%v"
  if "!FOUND_VERSION!"=="%PYTHON_VERSION_REQUIRED%" (
    echo Found pinned Python: %PYTHON_EXE%
    exit /b 0
  )
)

if exist "%PYTHON_USERLOCAL_EXE%" (
  for /f "usebackq delims=" %%v in (`"%PYTHON_USERLOCAL_EXE%" -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2^>nul`) do set "FOUND_VERSION=%%v"
  if "!FOUND_VERSION!"=="%PYTHON_VERSION_REQUIRED%" (
    set "PYTHON_EXE=%PYTHON_USERLOCAL_EXE%"
    echo Found pinned Python: !PYTHON_EXE!
    exit /b 0
  )
)

if exist "%PYTHON_TMP_EXE%" (
  for /f "usebackq delims=" %%v in (`"%PYTHON_TMP_EXE%" -c "import sys; print('.'.join(map(str, sys.version_info[:3])))" 2^>nul`) do set "FOUND_VERSION=%%v"
  if "!FOUND_VERSION!"=="%PYTHON_VERSION_REQUIRED%" (
    set "PYTHON_EXE=%PYTHON_TMP_EXE%"
    echo Found pinned Python: !PYTHON_EXE!
    exit /b 0
  )
)

set "FOUND_ON_PATH="
for /f "usebackq delims=" %%p in (`py -3.11 -c "import sys; print(sys.executable); print('.'.join(map(str, sys.version_info[:3])))" 2^>nul`) do (
  if not defined FOUND_ON_PATH (
    set "FOUND_ON_PATH=%%p"
  ) else (
    set "FOUND_PATH_VERSION=%%p"
  )
)
if "!FOUND_PATH_VERSION!"=="%PYTHON_VERSION_REQUIRED%" (
  set "PYTHON_EXE=!FOUND_ON_PATH!"
  echo Found pinned Python via py launcher: !PYTHON_EXE!
  exit /b 0
)

echo Python %PYTHON_VERSION_REQUIRED% not found. Downloading installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'" || exit /b 1

echo Installing Python %PYTHON_VERSION_REQUIRED% to %PYTHON_INSTALL_DIR%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%PYTHON_INSTALLER%' -ArgumentList '/quiet InstallAllUsers=0 TargetDir=""%PYTHON_INSTALL_DIR%"" Include_launcher=0 PrependPath=0 Include_test=0' -Wait -WindowStyle Hidden" || exit /b 1

if not exist "%PYTHON_EXE%" (
  echo ERROR: Python installer completed but python.exe was not found: %PYTHON_EXE%
  exit /b 1
)

for /f "usebackq delims=" %%v in (`"%PYTHON_EXE%" -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"`) do set "FOUND_VERSION=%%v"
if not "!FOUND_VERSION!"=="%PYTHON_VERSION_REQUIRED%" (
  echo ERROR: Installed Python version is !FOUND_VERSION!, expected %PYTHON_VERSION_REQUIRED%.
  exit /b 1
)
echo Installed pinned Python: %PYTHON_EXE%
exit /b 0

:ensure_venv
echo [2/4] Checking benchmark venv...
set "REBUILD_VENV=0"
if not exist "%VENV_PY%" set "REBUILD_VENV=1"
if exist "%VENV_PY%" if exist "%VENV_DIR%\pyvenv.cfg" (
  findstr /C:"version = %PYTHON_VERSION_REQUIRED%" "%VENV_DIR%\pyvenv.cfg" >nul 2>nul
  if errorlevel 1 (
    set "REBUILD_VENV=1"
  ) else (
    set "VENV_VERSION=%PYTHON_VERSION_REQUIRED%"
  )
)

if "%REBUILD_VENV%"=="1" (
  echo Rebuilding benchmark venv with Python %PYTHON_VERSION_REQUIRED%...
  if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" || exit /b 1
  "%PYTHON_EXE%" -m venv --copies "%VENV_DIR%" || exit /b 1
) else (
  echo Existing venv uses Python %PYTHON_VERSION_REQUIRED%.
)
exit /b 0

:install_requirements
echo [3/4] Installing pinned benchmark dependencies...
"%VENV_PY%" -m pip install --upgrade pip || exit /b 1
"%VENV_PY%" -m pip install -r "%REQ_FILE%" || exit /b 1
exit /b 0

:verify_environment
echo [4/4] Verifying canonical versions...
"%VENV_PY%" -c "import sys, chromadb, posthog; from packaging.version import Version; py='.'.join(map(str, sys.version_info[:3])); assert py=='%PYTHON_VERSION_REQUIRED%', py; assert chromadb.__version__=='0.6.3', chromadb.__version__; assert Version(posthog.__version__) < Version('3'), posthog.__version__; print('python=' + py); print('chromadb=' + chromadb.__version__); print('posthog=' + posthog.__version__)" || exit /b 1
exit /b 0

:clear_chroma
echo [optional] Clearing isolated benchmark Chroma directory...
echo Target: %BENCHMARK_CHROMA_DIR%
echo Production Chroma: %PRODUCTION_CHROMA_DIR%
"%VENV_PY%" "%ROOT%\app\benchmarks\clear_benchmark_chroma.py" || exit /b 1
exit /b 0

:run_smoke
echo [optional] Running Chroma smoke test...
"%VENV_PY%" "%ROOT%\app\benchmarks\chroma_smoke_test.py" --persist-dir "%BENCHMARK_CHROMA_DIR%" || exit /b 1
exit /b 0

:run_guards
echo [optional] Running benchmark guards...
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_benchmark_integrity.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_candidate_schema.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_index_registry.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_feature_cache_registry.py" || exit /b 1
"%VENV_PY%" "%ROOT%\app\benchmarks\validate_adapter_evaluation_boundary.py" || exit /b 1
exit /b 0
