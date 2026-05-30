"""Fail-fast Chroma persistence smoke test for the external benchmark store."""
import argparse
import os
import platform
import sys

import chromadb


DEFAULT_PERSIST_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "data",
        "external",
        "indexes",
        "chroma_cleaned_500_py311_chroma063",
    )
)
COLLECTION_NAME = "external_benchmark_chroma_smoke"
PRODUCTION_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "protected_legacy_chroma_db")
)
LEGACY_BENCHMARK_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "external", "indexes", "longmemeval_s_db")
)
METADATA_FIELDS = (
    "example_id",
    "memory_id",
    "original_memory_id",
    "session_id",
    "source_session_id",
    "pointer_id",
    "timestamp",
    "memory_unit_type",
    "turns_mode",
)


def _embedding(value: int) -> list[float]:
    return [float(value % 7), float((value + 1) % 11), float((value + 2) % 13)]


def _metadata(doc_id: str) -> dict:
    return {
        "example_id": "smoke_example",
        "memory_id": doc_id,
        "original_memory_id": doc_id,
        "session_id": "smoke_session",
        "source_session_id": "smoke_session",
        "pointer_id": f"smoke:{doc_id}",
        "timestamp": "2026-05-26",
        "memory_unit_type": "session",
        "turns_mode": "user_only",
    }


def _add_documents(collection, start: int, count: int) -> None:
    ids = [f"smoke_{value:04d}" for value in range(start, start + count)]
    collection.add(
        ids=ids,
        embeddings=[_embedding(value) for value in range(start, start + count)],
        documents=[f"tiny smoke document {value}" for value in range(start, start + count)],
        metadatas=[_metadata(doc_id) for doc_id in ids],
    )


def _exercise_collection(client, iteration: int) -> None:
    collection = client.create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    _add_documents(collection, 0, 10)
    if collection.count() != 10:
        raise RuntimeError(f"Iteration {iteration}: expected count 10 after initial add.")
    collection.query(query_embeddings=[_embedding(1)], n_results=3)

    for offset in range(10, 1010, 100):
        _add_documents(collection, offset, 100)
        expected = offset + 100
        if collection.count() != expected:
            raise RuntimeError(f"Iteration {iteration}: expected count {expected} after batch add.")
    collection.query(query_embeddings=[_embedding(1000)], n_results=5)
    if collection.count() != 1010:
        raise RuntimeError(f"Iteration {iteration}: expected final count 1010.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a benchmark-only Chroma persistence smoke test.")
    parser.add_argument("--persist-dir", default=DEFAULT_PERSIST_DIR)
    args = parser.parse_args()

    persist_dir = os.path.abspath(args.persist_dir)
    if persist_dir in (PRODUCTION_DIR, LEGACY_BENCHMARK_DIR):
        raise ValueError(f"Refusing to open prohibited Chroma persist directory: {persist_dir}")
    os.makedirs(persist_dir, exist_ok=True)
    client = chromadb.PersistentClient(path=persist_dir)
    existing = {
        item if isinstance(item, str) else item.name
        for item in client.list_collections()
    }
    if COLLECTION_NAME in existing:
        client.delete_collection(name=COLLECTION_NAME)

    print(f"Python: {sys.version.split()[0]} ({platform.system()})")
    print(f"chromadb: {chromadb.__version__}")
    print(f"client: {type(client).__name__}")
    print(f"persist_dir: {persist_dir}")
    print(f"metadata_fields: {', '.join(METADATA_FIELDS)}")

    for iteration in (1, 2):
        _exercise_collection(client, iteration)
        print(f"iteration {iteration}: added, counted, and queried 1010 documents")
        client.delete_collection(name=COLLECTION_NAME)
        if iteration == 1:
            print("iteration 1: collection deleted; recreating")

    print("PASS: Chroma persistence smoke test completed without compaction errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
