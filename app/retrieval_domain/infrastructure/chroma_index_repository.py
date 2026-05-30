"""Chroma infrastructure repository for benchmark-only indexes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Sequence

from tqdm import tqdm

from app.retrieval_domain.indexing.metadata_contracts import MetadataContract
from app.retrieval_domain.infrastructure import path_config


@dataclass(frozen=True)
class ChromaAddDiagnostics:
    collection_name: str
    indexed_document_count: int
    expected_document_count: int
    batch_size: int
    write_error: str | None = None
    count_error: str | None = None
    query_error: str | None = None
    compaction_error: bool = False


class ChromaIndexRepository:
    """Storage-only adapter for isolated benchmark Chroma collections."""

    def __init__(
        self,
        indexes_dir: str,
        production_dir: str | None = None,
        metadata_contract: MetadataContract | None = None,
    ) -> None:
        self.indexes_dir = os.path.abspath(indexes_dir)
        self.production_dir = os.path.abspath(production_dir or path_config.PROTECTED_LEGACY_CHROMA_DIR)
        self.metadata_contract = metadata_contract or MetadataContract()

    def validate_benchmark_persist_dir(self, benchmark_name: str, persist_dir: str) -> str:
        persist_dir = os.path.abspath(persist_dir)
        legacy_failed_dir = os.path.abspath(os.path.join(self.indexes_dir, f"{benchmark_name}_db"))
        if os.path.commonpath([persist_dir, self.indexes_dir]) != self.indexes_dir:
            raise ValueError(
                f"Benchmark Chroma path must remain under {self.indexes_dir}: {persist_dir}"
            )
        if persist_dir in (self.production_dir, legacy_failed_dir):
            raise ValueError(f"Refusing to open prohibited Chroma persist directory: {persist_dir}")
        return persist_dir

    def create_client(self, benchmark_name: str, persist_dir: str):
        import chromadb

        isolated_db_path = self.validate_benchmark_persist_dir(benchmark_name, persist_dir)
        os.makedirs(isolated_db_path, exist_ok=True)
        print(f"[INFO] Initializing isolated ChromaDB at {isolated_db_path}")
        return chromadb.PersistentClient(path=isolated_db_path)

    @staticmethod
    def list_collection_names(client: Any) -> set[str]:
        return {item if isinstance(item, str) else item.name for item in client.list_collections()}

    def get_or_recreate_collection(
        self,
        client: Any,
        collection_name: str,
        use_existing_index: bool = False,
    ) -> tuple[Any, bool]:
        collection_names = self.list_collection_names(client)
        if use_existing_index and collection_name in collection_names:
            print(f"[INFO] Reusing existing benchmark collection '{collection_name}'.")
            return client.get_collection(name=collection_name), True
        if use_existing_index:
            print(
                f"[WARN] Existing benchmark collection '{collection_name}' not found; "
                "building a fresh isolated collection."
            )
        if collection_name in collection_names:
            print(
                f"[INFO] Deleting existing benchmark collection '{collection_name}' "
                "before fresh add ingestion."
            )
            client.delete_collection(name=collection_name)
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return collection, False

    def add_documents(
        self,
        collection: Any,
        ids: Sequence[str],
        embeddings: Sequence[Any],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
        batch_size: int = 50,
        validate_batch_count: bool = True,
        desc: str = "Chroma add",
    ) -> ChromaAddDiagnostics:
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate memory IDs detected before fresh Chroma add ingestion.")
        if not (len(ids) == len(embeddings) == len(documents) == len(metadatas)):
            raise ValueError("Chroma add inputs must have matching lengths.")
        for metadata in metadatas:
            self.metadata_contract.validate(metadata)

        total = len(ids)
        try:
            batches = range(0, total, batch_size)
            for i in tqdm(
                batches,
                total=(total + batch_size - 1) // batch_size,
                desc=desc,
            ):
                batch_slice = slice(i, i + batch_size)
                collection.add(
                    ids=list(ids[batch_slice]),
                    embeddings=list(embeddings[batch_slice]),
                    documents=list(documents[batch_slice]),
                    metadatas=list(metadatas[batch_slice]),
                )
                if validate_batch_count:
                    try:
                        count_after_batch = collection.count()
                    except Exception as exc:
                        raise RuntimeError(f"Chroma count failed after batch add: {exc}") from exc
                    expected = min(i + batch_size, total)
                    if count_after_batch != expected:
                        raise RuntimeError(
                            "Chroma count mismatch after batch add: "
                            f"expected {expected}, got {count_after_batch}."
                        )
        except Exception as exc:
            message = str(exc)
            return ChromaAddDiagnostics(
                collection_name=collection.name,
                indexed_document_count=0,
                expected_document_count=total,
                batch_size=batch_size,
                write_error=message,
                compaction_error="compaction" in message.lower(),
            )

        try:
            actual_count = collection.count()
        except Exception as exc:
            raise RuntimeError(f"Chroma count failed after ingestion: {exc}") from exc
        if actual_count != total:
            raise RuntimeError(f"Ingestion count mismatch! Expected {total}, got {actual_count}")

        return ChromaAddDiagnostics(
            collection_name=collection.name,
            indexed_document_count=actual_count,
            expected_document_count=total,
            batch_size=batch_size,
        )
