"""Legacy/default LongMemEval-S Dataset Context adapter."""

from __future__ import annotations

import uuid
from typing import Any

from app.benchmarks.external_benchmark_adapter import BenchmarkExample
from app.retrieval_domain.evaluation import LegacyFuzzyEvidenceSetupPolicy


def fuzzy_match_evidence(query: str, answer: str, doc_text: str) -> bool:
    """Legacy fuzzy evidence setup for the old default LongMemEval-S path only."""

    return LegacyFuzzyEvidenceSetupPolicy().fuzzy_match_evidence(
        query=query,
        answer=answer,
        doc_text=doc_text,
    )


class LongMemEvalLegacyAdapter:
    """Map the old/default 147-example LongMemEval-S schema.

    The fuzzy evidence setup here is legacy and non-canonical. It must never be
    used for the cleaned schema and must never feed retrieval scoring.
    """

    schema = "default"

    def examples_from_records(
        self,
        records: list[dict[str, Any]],
        *,
        limit: int | None = None,
        resolved_only: bool = False,
        turns_mode: str = "all_turns",
    ) -> list[BenchmarkExample]:
        del turns_mode
        examples: list[BenchmarkExample] = []
        for i, item in enumerate(records):
            if limit and len(examples) >= limit:
                break

            question = item.get("question") or item.get("query")
            if not question:
                continue

            example = self._map_record(i, item, question)
            if resolved_only and example.metadata.get("evidence_unresolved"):
                continue
            examples.append(example)
        return examples

    def _map_record(
        self,
        index: int,
        item: dict[str, Any],
        question: str,
    ) -> BenchmarkExample:
        documents = item.get("documents", [])
        answer = item.get("answer", "")

        memory_units = []
        expected_session_ids = []
        for doc_idx, doc_text in enumerate(documents):
            session_id = f"doc_{doc_idx}"
            question_id = item.get("question_id") or item.get("id") or f"idx_{index}"
            pointer_id = f"lme:{question_id}:doc:{doc_idx}"

            memory_units.append(
                {
                    "memory_id": f"longmem_{index}_{session_id}",
                    "pointer_id": pointer_id,
                    "user_id": f"user_longmem_{index}",
                    "session_id": session_id,
                    "source_text": doc_text,
                    "summary": doc_text[:500] + "..." if len(doc_text) > 500 else doc_text,
                    "memory_type": "event",
                    "memory_source_kind": "summary",
                    "topic_tags": ["longmemeval"],
                    "timestamp": "2026-05-24T00:00:00.000Z",
                    "importance": 0.5,
                }
            )

            if fuzzy_match_evidence(question, answer, doc_text):
                expected_session_ids.append(session_id)

        metadata = {"question_type": item.get("question_type", "unknown"), "schema": self.schema}
        if not expected_session_ids:
            metadata["evidence_unresolved"] = True

        return BenchmarkExample(
            benchmark_name="longmemeval",
            example_id=item.get("question_id", f"lme_{uuid.uuid4().hex[:8]}"),
            query=question,
            memory_units=memory_units,
            expected_session_ids=expected_session_ids,
            expected_evidence=[answer] if answer else [],
            metadata=metadata,
        )
