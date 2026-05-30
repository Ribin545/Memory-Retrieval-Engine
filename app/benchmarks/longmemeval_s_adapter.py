"""Compatibility wrapper for LongMemEval-S benchmark adapter imports.

Legacy fuzzy evidence setup is implemented only in the Dataset Context legacy
adapter and remains limited to the old default LongMemEval-S path.
"""

from __future__ import annotations

from app.retrieval_domain.dataset import (
    LongMemEvalAdapterFacade,
    fuzzy_match_evidence,
)


class LongMemEvalAdapter(LongMemEvalAdapterFacade):
    """Backward-compatible adapter name used by the benchmark runner."""


__all__ = ["LongMemEvalAdapter", "fuzzy_match_evidence"]
