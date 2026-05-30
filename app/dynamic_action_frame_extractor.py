"""Compatibility wrapper for retrieval-owned grammar/action-frame extraction.

The implementation moved to
`app.retrieval_domain.features.grammar_frame_extractor` during the retrieval
cleanup. This module preserves the historical import path for archived and
external callers, including underscore-prefixed helpers such as
`_ensure_nlp_loaded`.
"""

from app.retrieval_domain.features import grammar_frame_extractor as _impl

for _name in dir(_impl):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_impl, _name)

__all__ = [name for name in globals() if not name.startswith("__")]
