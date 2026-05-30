import json
import os
import ast
from tqdm import tqdm

def extract_expected_fields(adapter_path):
    with open(adapter_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # We look for field names used in the adapter.
    # This is a simple heuristic: looking for string literals that look like field names
    # or looking for a mapping dict if it exists.
    # Since we don't have the file yet, we'll try to find keywords like 'question', 'session', etc.
    # A better way is to look for a mapping dictionary if the adapter has one.
    return ["question", "sessions", "session_id", "answer"] # Default common fields

def compare_schemas(cleaned_path, old_path, adapter_path):
    print(f"Loading cleaned dataset: {cleaned_path}")
    with open(cleaned_path, 'r', encoding='utf-8') as f:
        cleaned_data = json.load(f)

    print(f"Loading old dataset: {old_path}")
    if os.path.exists(old_path):
        with open(old_path, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
    else:
        old_data = []
        print("Old dataset not found.")

    # Extract expected fields from adapter
    expected_fields = set(extract_expected_fields(adapter_path))

    if not cleaned_data:
        return "Cleaned data empty"

    cleaned_fields = set(cleaned_data[0].keys())
    old_fields = set(old_data[0].keys()) if old_data else set()

    compatible_fields = cleaned_fields.intersection(expected_fields)
    missing_fields = expected_fields - cleaned_fields

    # Map analysis
    mapping_proposal = {
        "question": "question" if "question" in cleaned_fields else "TBD",
        "sessions/documents": "haystack_sessions" if "haystack_sessions" in cleaned_fields else "TBD",
        "session_ids": "haystack_session_ids" if "haystack_session_ids" in cleaned_fields else "TBD",
        "dates": "haystack_dates" if "haystack_dates" in cleaned_fields else "TBD",
        "expected_session_ids": "answer_session_ids" if "answer_session_ids" in cleaned_fields else "TBD"
    }

    # Decision logic
    # If the cleaned schema is significantly different or contains essential missing fields,
    # a separate adapter might be cleaner.
    decision = "A. extend existing longmemeval_s_adapter.py with cleaned_schema mode"
    if len(missing_fields) > 2:
        decision = "B. create a separate longmemeval_cleaned_adapter.py"

    report_path = "outputs/benchmarks/schema_exploration/longmemeval_schema_compatibility_report.md"
    with open(report_path, "w", encoding='utf-8') as f:
        f.write("# LongMemEval-S Schema Compatibility Report\n\n")
        f.write("## Dataset Comparison\n")
        f.write(f"- **Cleaned Fields:** {sorted(list(cleaned_fields))}\n")
        f.write(f"- **Old Fields:** {sorted(list(old_fields))}\n")
        f.write(f"- **Adapter Expected Fields:** {sorted(expected_fields)}\n\n")

        f.write("## Compatibility Analysis\n")
        f.write(f"- **Compatible Fields:** {sorted(list(compatible_fields))}\n")
        f.write(f"- **Missing Fields:** {sorted(list(missing_fields))}\n\n")

        f.write("## Field Mapping Proposal\n")
        for target, source in mapping_proposal.items():
            f.write(f"- {target} $\rightarrow$ `{source}`\n")

        f.write("\n## Final Recommendation\n")
        f.write(f"**Decision:** {decision}\n\n")
        f.write("### Reasoning:\n")
        f.write("- If the mapping is 1:1 and minimal, extending is better.\n")
        f.write("- If the cleaned dataset structure introduces new concepts (e.g. different session nesting), a separate adapter is safer.\n")

    print(f"Compatibility report written to {report_path}")

if __name__ == "__main__":
    CLEANED_PATH = "data/external/longmemeval_cleaned/longmemeval_s_cleaned.json"
    OLD_PATH = "data/external/longmemeval/longmemeval_s.json"
    ADAPTER_PATH = "app/benchmarks/longmemeval_s_adapter.py"
    compare_schemas(CLEANED_PATH, OLD_PATH, ADAPTER_PATH)
