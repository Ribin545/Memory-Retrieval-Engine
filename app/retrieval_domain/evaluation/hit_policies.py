"""Hit policies owned by the Evaluation bounded context."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Protocol


class HitPolicy(Protocol):
    """Determines whether a ranked candidate satisfies evaluation ground truth."""

    def is_hit(self, candidate: Any, expected_session_ids: Iterable[str]) -> bool:
        """Return True when the candidate matches the expected ground truth."""


def _candidate_value(candidate: Any, key: str) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(key)
    return getattr(candidate, key, None)


@dataclass(frozen=True)
class StrictSessionIdHitPolicy:
    """Strict cleaned LongMemEval-S hit policy.

    Evaluation owns this comparison. Retrieval candidates are already ranked
    before this policy sees them, and this policy must not mutate their scores
    or order.
    """

    candidate_id_fields: tuple[str, ...] = (
        "session_id",
        "source_session_id",
        "original_memory_id",
    )

    def is_hit(self, candidate: Any, expected_session_ids: Iterable[str]) -> bool:
        expected_ids = {str(value) for value in expected_session_ids if value is not None}
        if not expected_ids:
            return False

        for field_name in self.candidate_id_fields:
            value = _candidate_value(candidate, field_name)
            if value is not None and str(value) in expected_ids:
                return True
        return False


@dataclass(frozen=True)
class LegacyFuzzyEvidenceSetupPolicy:
    """Legacy evidence setup for the old 147 LongMemEval-S path only.

    This derives expected session IDs from answer text in the default schema.
    It is intentionally not used by the cleaned schema and must never feed
    retrieval scoring.
    """

    weak_stopwords: frozenset[str] = frozenset(
        {
            "including",
            "acceptable",
            "between",
            "which",
            "their",
            "would",
            "provide",
            "these",
            "those",
            "about",
            "could",
            "there",
            "that",
            "from",
            "this",
        }
    )
    negations: tuple[str, ...] = (
        "not provide",
        "no information",
        "does not state",
        "not mentioned",
        "cannot be determined",
    )

    def fuzzy_match_evidence(self, query: str, answer: str, doc_text: str) -> bool:
        clean_answer = str(answer).lower()
        text_lower = doc_text.lower()

        if any(neg in clean_answer for neg in self.negations):
            return False

        numbers = set(re.findall(r"\b\d+\b", clean_answer))
        a_words = {
            word
            for word in re.findall(r"\b\w+\b", clean_answer)
            if len(word) > 4 and word not in self.weak_stopwords
        }
        q_words = {
            word
            for word in re.findall(r"\b\w+\b", query.lower())
            if len(word) > 4 and word not in self.weak_stopwords
        }

        answer_score = 0
        query_score = 0

        for num in numbers:
            if re.search(rf"\b{re.escape(num)}\b", text_lower):
                answer_score += 2
        for word in a_words:
            if re.search(rf"\b{re.escape(word)}\b", text_lower):
                answer_score += 1

        for word in q_words:
            if re.search(rf"\b{re.escape(word)}\b", text_lower):
                query_score += 0.5

        if answer_score == 0:
            return False

        return (answer_score + query_score) >= 2.5
