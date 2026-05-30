from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import abc

@dataclass
class BenchmarkExample:
    benchmark_name: str
    example_id: str
    query: str
    memory_units: List[Dict[str, Any]]
    expected_session_ids: List[str] = field(default_factory=list)
    expected_evidence: List[str] = field(default_factory=list)
    expected_evidence_texts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BenchmarkResult:
    example_id: str
    retrieved_top_k: List[Dict[str, Any]]
    hit_at_1: bool
    hit_at_5: bool
    hit_at_10: bool
    mrr: float
    latency_ms: float
    error: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None

class BaseBenchmarkAdapter(abc.ABC):
    
    @abc.abstractmethod
    def load_dataset(self, data_path: str, limit: int = None) -> List[BenchmarkExample]:
        """
        Load the dataset from the given path and return a list of BenchmarkExample objects.
        Should print instructions and raise an exception if the dataset is missing.
        """
        pass
    
    def evaluate_retrieval(self, example: BenchmarkExample, retrieved_candidates: List[Dict[str, Any]]) -> BenchmarkResult:
        """
        Evaluate the retrieved candidates against the expected session IDs or evidence.
        """
        hit_at_1 = False
        hit_at_5 = False
        hit_at_10 = False
        mrr = 0.0
        
        # Determine if a candidate is a hit
        def is_hit(cand: Dict[str, Any]) -> bool:
            cand_session = cand.get("session_id", "") or cand.get("source_session_id", "")
            cand_text = cand.get("source_text", "") or ""
            cand_summary = cand.get("summary", "") or ""
            cand_text_lower = cand_text.lower()
            cand_summary_lower = cand_summary.lower()
            cand_dia_ids = cand.get("dia_ids") or cand.get("contained_dia_ids") or []
            if isinstance(cand_dia_ids, str):
                cand_dia_ids = [cand_dia_ids]
            
            # Match by session ID
            if example.expected_session_ids and cand_session in example.expected_session_ids:
                return True

            # Match by evidence dia id overlap
            if example.expected_evidence and set(cand_dia_ids).intersection(set(example.expected_evidence)):
                return True
                
            # Match by evidence substring
            evidence_texts = example.expected_evidence_texts or example.expected_evidence
            if evidence_texts:
                for ev in evidence_texts:
                    ev_lower = str(ev).lower()
                    if ev_lower in cand_text_lower or ev_lower in cand_summary_lower:
                        return True
            return False

        for rank, cand in enumerate(retrieved_candidates):
            if is_hit(cand):
                if mrr == 0.0:
                    mrr = 1.0 / (rank + 1)
                if rank == 0:
                    hit_at_1 = True
                if rank < 5:
                    hit_at_5 = True
                if rank < 10:
                    hit_at_10 = True

        return BenchmarkResult(
            example_id=example.example_id,
            retrieved_top_k=retrieved_candidates,
            hit_at_1=hit_at_1,
            hit_at_5=hit_at_5,
            hit_at_10=hit_at_10,
            mrr=mrr,
            latency_ms=0.0  # Will be set by the runner
        )
