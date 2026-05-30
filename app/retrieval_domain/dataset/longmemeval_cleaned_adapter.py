"""Cleaned LongMemEval-S Dataset Context adapter."""

from __future__ import annotations

from typing import Any

from app.benchmarks.external_benchmark_adapter import BenchmarkExample


class LongMemEvalCleanedAdapter:
    """Map cleaned 500-question LongMemEval-S records into examples."""

    schema = "cleaned"

    def examples_from_records(
        self,
        records: list[dict[str, Any]],
        *,
        limit: int | None = None,
        resolved_only: bool = False,
        turns_mode: str = "all_turns",
    ) -> list[BenchmarkExample]:
        examples: list[BenchmarkExample] = []
        for i, item in enumerate(records):
            if limit and len(examples) >= limit:
                break

            query = item.get("question")
            if not query:
                continue

            example = self._map_record(i, item, query, turns_mode)
            if resolved_only and example.metadata.get("evidence_unresolved"):
                continue
            examples.append(example)
        return examples

    def _map_record(
        self,
        index: int,
        item: dict[str, Any],
        query: str,
        turns_mode: str,
    ) -> BenchmarkExample:
        example_id = item.get("question_id", f"lme_cleaned_{index}")
        answer = item.get("answer", "")
        expected_session_ids = item.get("answer_session_ids", [])

        haystack_sessions = item.get("haystack_sessions", [])
        haystack_session_ids = item.get("haystack_session_ids", [])
        haystack_dates = item.get("haystack_dates", [])

        memory_units = []
        for session_idx, (session, session_id, session_date) in enumerate(
            zip(haystack_sessions, haystack_session_ids, haystack_dates)
        ):
            source_text = self._join_session_turns(session, turns_mode)
            memory_units.append(
                {
                    "memory_id": f"lme_cleaned_{index}_{session_idx}_{session_id}",
                    "pointer_id": f"lme_cleaned:{example_id}:{session_id}",
                    "user_id": f"user_longmem_{index}",
                    "session_id": session_id,
                    "source_session_id": session_id,
                    "original_memory_id": session_id,
                    "source_text": source_text,
                    "summary": source_text[:500] + "..." if len(source_text) > 500 else source_text,
                    "memory_type": "conversation_session",
                    "memory_source_kind": "raw_session",
                    "topic_tags": ["longmemeval"],
                    "timestamp": session_date,
                    "importance": 0.5,
                }
            )

        metadata = {
            "question_type": item.get("question_type", "unknown"),
            "schema": self.schema,
        }
        if item.get("question_date") is not None:
            metadata["question_date"] = item.get("question_date")
        if answer:
            metadata["answer"] = answer
        if not expected_session_ids:
            metadata["evidence_unresolved"] = True

        return BenchmarkExample(
            benchmark_name="longmemeval",
            example_id=example_id,
            query=query,
            memory_units=memory_units,
            expected_session_ids=expected_session_ids,
            expected_evidence=[answer] if answer else [],
            metadata=metadata,
        )

    @staticmethod
    def _join_session_turns(session: Any, turns_mode: str) -> str:
        if not isinstance(session, list):
            return str(session)

        if turns_mode == "user_only":
            turns = [
                f"{turn.get('role', 'user')}: {turn.get('content', '')}"
                for turn in session
                if turn.get("role") == "user"
            ]
        else:
            turns = [
                f"{turn.get('role', 'user')}: {turn.get('content', '')}"
                for turn in session
            ]
        return "\n\n".join(turns)
