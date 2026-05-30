import json
import os
from collections import Counter
from tqdm import tqdm

def explore_schema(file_path):
    print(f"Loading {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list):
        # If it's a dict, try to find a list inside
        for key, value in data.items():
            if isinstance(value, list):
                data = value
                break

    total_examples = len(data)
    print(f"Total examples: {total_examples}")

    # Top-level fields and types
    if total_examples == 0:
        return "No data found"

    first_example = data[0]
    fields = {k: type(v).__name__ for k, v in first_example.items()}

    # Deeper analysis
    questions = []
    answers = []
    sessions_counts = []
    turns_counts = []
    total_turns = 0

    for ex in tqdm(data, desc="Analyzing examples"):
        questions.append(ex.get('question', 'N/A'))
        answers.append(ex.get('answer', 'N/A'))

        sessions = ex.get('haystack_sessions', [])
        if isinstance(sessions, list):
            sessions_counts.append(len(sessions))
            for session in sessions:
                if isinstance(session, list):
                    turns_counts.append(len(session))
                    total_turns += len(session)
                elif isinstance(session, dict):
                    turns_counts.append(1)
                    total_turns += 1
                elif isinstance(session, str):
                    turns_counts.append(1)
                    total_turns += 1

    avg_sessions = sum(sessions_counts) / total_examples if total_examples > 0 else 0
    avg_turns = total_turns / len(turns_counts) if turns_counts else 0

    summary = {
        "total_examples": total_examples,
        "top_level_structure": "list",
        "fields": fields,
        "avg_sessions_per_example": avg_sessions,
        "avg_turns_per_session": avg_turns,
        "first_3_examples": data[:3]
    }

    # Write raw summary
    os.makedirs("outputs/benchmarks/schema_exploration", exist_ok=True)
    with open("outputs/benchmarks/schema_exploration/longmemeval_schema_raw_summary.json", "w", encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    # Write report
    report_path = "outputs/benchmarks/schema_exploration/longmemeval_cleaned_schema_report.md"
    with open(report_path, "w", encoding='utf-8') as f:
        f.write("# LongMemEval-S Cleaned Schema Report\n\n")
        f.write(f"**Local Dataset Path:** {file_path}\n\n")
        f.write(f"**Total Examples:** {total_examples}\n\n")
        f.write("## Fields and Types\n")
        for k, v in fields.items():
            f.write(f"- `{k}`: {v}\n")

        f.write("\n## Statistics\n")
        f.write(f"- Average sessions per example: {avg_sessions:.2f}\n")
        f.write(f"- Average turns per session: {avg_turns:.2f}\n\n")

        f.write("## Sample Records (First 3)\n")
        for i, ex in enumerate(data[:3]):
            f.write(f"### Example {i+1}\n")
            f.write(f"- **Question:** {ex.get('question', 'N/A')}\n")
            f.write(f"- **Answer:** {ex.get('answer', 'N/A')}\n")
            f.write(f"- **Sessions Count:** {len(ex.get('haystack_sessions', []))}\n\n")

    print(f"Reports written to {report_path} and outputs/benchmarks/schema_exploration/longmemeval_schema_raw_summary.json")

if __name__ == "__main__":
    explore_schema("data/external/longmemeval_cleaned/longmemeval_s_cleaned.json")
