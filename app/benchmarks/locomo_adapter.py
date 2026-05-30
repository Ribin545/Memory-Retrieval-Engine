import os
import sys
import json
import uuid
from typing import List, Dict, Any
from app.benchmarks.external_benchmark_adapter import BaseBenchmarkAdapter, BenchmarkExample

class LocomoAdapter(BaseBenchmarkAdapter):
    def _build_memory_units(self, sample_id: str, conversation_dict: Dict[str, Any], unit_type: str) -> List[Dict[str, Any]]:
        memory_units = []

        for key, turns in conversation_dict.items():
            if not (key.startswith("session_") and not key.endswith("_date_time") and isinstance(turns, list)):
                continue

            session_id = key
            normalized_turns = []
            for idx, t in enumerate(turns):
                speaker = t.get("speaker", "user")
                text = t.get("text", "")
                dia_id = t.get("dia_id", "")
                normalized_turns.append({
                    "speaker": speaker,
                    "text": text,
                    "dia_id": dia_id,
                    "turn_index": idx,
                })

            def build_unit(unit_turns: List[Dict[str, Any]], suffix: str, memory_unit_type: str):
                text_parts = []
                dia_ids = []
                pointer_ids = []
                for turn in unit_turns:
                    dia_id = turn.get("dia_id", "")
                    text_parts.append(f"[{dia_id}] {turn.get('speaker', 'user')}: {turn.get('text', '')}")
                    if dia_id:
                        dia_ids.append(dia_id)
                    turn_idx = turn.get("turn_index", 0)
                    pointer_id = f"locomo:{sample_id}:session:{session_id}:turn:{turn_idx}"
                    pointer_ids.append(pointer_id)
                full_text = "\n".join(text_parts)
                primary_pointer_id = pointer_ids[0] if pointer_ids else ""
                memory_units.append({
                    "memory_id": f"{sample_id}_{session_id}{suffix}",
                    "pointer_id": primary_pointer_id,
                    "pointer_ids": pointer_ids,
                    "benchmark_name": "locomo",
                    "user_id": sample_id,
                    "session_id": session_id,
                    "source_session_id": session_id,
                    "source_text": full_text,
                    "summary": full_text[:500] + "..." if len(full_text) > 500 else full_text,
                    "memory_type": "event",
                    "memory_source_kind": "summary",
                    "topic_tags": ["locomo"],
                    "timestamp": "2026-05-24T00:00:00.000Z",
                    "importance": 0.5,
                    "contained_dia_ids": dia_ids,
                    "dia_ids": dia_ids,
                    "evidence_ids": [],
                    "memory_unit_type": memory_unit_type,
                })

            if unit_type == "session":
                build_unit(normalized_turns, "", "session")
            elif unit_type == "turn":
                for turn in normalized_turns:
                    build_unit([turn], f"_turn_{turn['turn_index']}", "turn")
            elif unit_type.startswith("window_"):
                try:
                    window_size = int(unit_type.split("_", 1)[1])
                except Exception:
                    window_size = 3
                if len(normalized_turns) <= window_size:
                    build_unit(normalized_turns, f"_win_{window_size}_0_{max(len(normalized_turns) - 1, 0)}", unit_type)
                else:
                    for start in range(0, len(normalized_turns) - window_size + 1):
                        window_turns = normalized_turns[start:start + window_size]
                        end = start + window_size - 1
                        build_unit(window_turns, f"_win_{window_size}_{start}_{end}", unit_type)
            else:
                build_unit(normalized_turns, "", "session")

        return memory_units

    def load_dataset(self, data_path: str, limit: int = None, unit_type: str = "session") -> List[BenchmarkExample]:
        if not os.path.isdir(data_path):
            print(f"[ERROR] Expected LoCoMo data directory at: {data_path}")
            print("Please download the dataset (e.g. locomo10.json) into this folder.")
            sys.exit(1)
            
        json_files = [f for f in os.listdir(data_path) if f.endswith('.json')]
        if not json_files:
            print(f"[ERROR] No JSON files found in {data_path}")
            print("Please provide the LoCoMo dataset in JSON format.")
            sys.exit(1)
            
        file_to_load = os.path.join(data_path, json_files[0])
        print(f"[INFO] Loading LoCoMo dataset from {file_to_load}")
        
        try:
            with open(file_to_load, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load JSON: {e}")
            sys.exit(1)
            
        examples = []
        
        # LoCoMo 10 contains a list of personas
        for conv_i, persona in enumerate(data):
            if limit and len(examples) >= limit:
                break
                
            qa_list = persona.get("qa", [])
            conversation_dict = persona.get("conversation", {})
            sample_id = persona.get("sample_id", f"user_{conv_i}")
            
            memory_units = self._build_memory_units(sample_id, conversation_dict, unit_type)
                
            # Create a BenchmarkExample for each QA pair
            for qa in qa_list:
                if limit and len(examples) >= limit:
                    break
                    
                question = qa.get("question", "")
                answer = qa.get("answer", "")
                evidence = qa.get("evidence", []) # e.g. ["D1:3", "D2:5"]
                
                # To map evidence to our session-level memory units,
                # any memory unit that contains ONE of the evidence dia_ids is considered a target session.
                expected_session_ids = []
                for ev in evidence:
                    for mu in memory_units:
                        if ev in mu.get("contained_dia_ids", []):
                            if mu["session_id"] not in expected_session_ids:
                                expected_session_ids.append(mu["session_id"])
                
                # Fallback if no mapping found
                metadata = {"qa_category": qa.get("category", "unknown"), "unit_type": unit_type}
                if not expected_session_ids:
                    expected_session_ids = []
                    metadata["evidence_unresolved"] = True

                expected_evidence_texts = []
                answer = qa.get("answer", "")
                if answer:
                    expected_evidence_texts.append(answer)
                    
                examples.append(BenchmarkExample(
                    benchmark_name="locomo",
                    example_id=f"conv-{conv_i}_{uuid.uuid4().hex[:8]}",
                    query=question,
                    memory_units=memory_units,
                    expected_session_ids=expected_session_ids,
                    expected_evidence=evidence,
                    expected_evidence_texts=expected_evidence_texts,
                    metadata=metadata
                ))
                
        return examples
