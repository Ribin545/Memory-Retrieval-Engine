#!/usr/bin/env python3
"""Safely clear the isolated benchmark Chroma persist directory.

This utility is intentionally narrow: it only clears the frozen cleaned
LongMemEval-S benchmark Chroma path and refuses to operate on the production
legacy Chroma DB.
"""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_CHROMA_DIR = (
    ROOT / "data" / "external" / "indexes" / "chroma_cleaned_500_py311_chroma063"
).resolve()
ALLOWED_ROOT = (ROOT / "data" / "external" / "indexes").resolve()
PRODUCTION_CHROMA_DIR = (ROOT / "data" / "protected_legacy_chroma_db").resolve()


def clear_benchmark_chroma() -> Path:
    if not str(BENCHMARK_CHROMA_DIR).startswith(str(ALLOWED_ROOT)):
        raise RuntimeError(f"Refusing cleanup outside benchmark indexes: {BENCHMARK_CHROMA_DIR}")
    if BENCHMARK_CHROMA_DIR == PRODUCTION_CHROMA_DIR:
        raise RuntimeError("Refusing to delete production Chroma DB")

    if BENCHMARK_CHROMA_DIR.exists():
        shutil.rmtree(BENCHMARK_CHROMA_DIR)
    BENCHMARK_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return BENCHMARK_CHROMA_DIR


def main() -> int:
    cleared = clear_benchmark_chroma()
    print(f"Cleared isolated benchmark Chroma directory: {cleared}")
    print(f"Production Chroma directory untouched: {PRODUCTION_CHROMA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
