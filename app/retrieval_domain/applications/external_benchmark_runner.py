"""Application service for the external benchmark CLI workflow."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any

from app.benchmarks.build_grammar_cache import build_grammar_cache_for_examples
from app.benchmarks.build_temporal_cache import build_temporal_cache_for_examples
from app.benchmarks.locomo_adapter import LocomoAdapter
from app.benchmarks.longmemeval_s_adapter import LongMemEvalAdapter
from app.retrieval_domain.features import (
    load_feature_cache_registry,
    run_feature_cache_preflight,
)
from app.retrieval_domain.infrastructure import path_config
from app.retrieval_domain.indexing.registry_io import write_registry

from .build_benchmark_index import DEFAULT_BENCHMARK_CHROMA_DIR, BuildBenchmarkIndex
from .generate_benchmark_report import BenchmarkReportContext, GenerateBenchmarkReport
from .retrieval_dispatcher import run_retrieval
from .run_benchmark_suite import RunBenchmarkSuite


ALL_MODES = [
    "vector_only",
    "bm25_only",
    "hybrid_dense_sparse",
    "grammar_emotion_reranker",
    "clean_hybrid",
    "clean_hybrid_grammar",
    "clean_hybrid_temporal",
    "clean_hybrid_temporal_multihop",
    "clean_hybrid_temporal_multihop_v2",
]
CLEAN_HYBRID_MODES = {
    "clean_hybrid",
    "clean_hybrid_grammar",
    "clean_hybrid_temporal",
    "clean_hybrid_temporal_multihop",
    "clean_hybrid_temporal_multihop_v2",
}
TEMPORAL_MODES = {
    "clean_hybrid_temporal",
    "clean_hybrid_temporal_multihop",
    "clean_hybrid_temporal_multihop_v2",
}
TEMPORAL_GRAPH_MODES = {
    "clean_hybrid_temporal_multihop",
    "clean_hybrid_temporal_multihop_v2",
}


@dataclass(frozen=True)
class LoadedBenchmark:
    adapter: Any
    examples: list[Any]
    unit_type: str


@dataclass(frozen=True)
class CacheBundle:
    grammar_cache: dict[str, Any] | None
    grammar_cache_path: str
    temporal_cache: dict[str, Any] | None
    temporal_cache_path: str
    temporal_graph_cache: dict[str, Any] | None
    temporal_graph_cache_path: str


class ExternalBenchmarkRunner:
    """Coordinate the existing external benchmark path through services."""

    def __init__(
        self,
        index_builder: BuildBenchmarkIndex | None = None,
        suite: RunBenchmarkSuite | None = None,
        report_writer: GenerateBenchmarkReport | None = None,
    ) -> None:
        self.index_builder = index_builder or BuildBenchmarkIndex()
        self.suite = suite or RunBenchmarkSuite()
        self.report_writer = report_writer or GenerateBenchmarkReport()

    @staticmethod
    def build_arg_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Run External Retrieval Benchmark")
        parser.add_argument("--benchmark", type=str, required=True, choices=["longmemeval_s", "locomo"])
        parser.add_argument("--data-path", type=str, required=True)
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--top-k", type=int, default=10)
        parser.add_argument("--mode", type=str, required=True, choices=ALL_MODES + ["all"])
        parser.add_argument("--unit-type", type=str, default=None, choices=["session", "turn", "window_3", "window_4", "window_5"])
        parser.add_argument("--schema", type=str, default="default", choices=["default", "cleaned"], help="Schema to use for LongMemEval-S dataset")
        parser.add_argument("--turns-mode", type=str, default="all_turns", choices=["all_turns", "user_only"], help="Turns mode for cleaned LongMemEval-S evaluation")
        parser.add_argument("--persist-dir", type=str, default=DEFAULT_BENCHMARK_CHROMA_DIR, help="Fresh benchmark-only Chroma persist directory")
        parser.add_argument("--batch-size", type=int, default=50, choices=[50, 100, 256], help="Chroma add batch size")
        parser.add_argument("--no-validate-batch-count", action="store_true", help="Skip count verification after each Chroma add batch")
        parser.add_argument("--resolved-only", action="store_true")
        parser.add_argument("--skip-model-reload", action="store_true")
        parser.add_argument("--use-existing-index", action="store_true", help="Reuse an existing isolated benchmark collection if present")
        parser.add_argument("--output-dir", type=str, default="outputs/benchmarks")
        parser.add_argument("--use-grammar-cache", action="store_true", help="Load grammar cache and attach to clean_hybrid retrieval")
        parser.add_argument("--build-grammar-cache", action="store_true", help="Build grammar cache before running benchmark")
        parser.add_argument("--grammar-cache-path", type=str, default=None, help="Override path to grammar cache JSON")
        parser.add_argument("--use-temporal-cache", action="store_true", help="Load temporal cache and attach to clean_hybrid_temporal retrieval")
        parser.add_argument("--build-temporal-cache", action="store_true", help="Build temporal cache before running benchmark")
        parser.add_argument("--temporal-cache-path", type=str, default=None, help="Override path to temporal cache JSON")
        parser.add_argument("--use-temporal-graph-cache", action="store_true", help="Load temporal event graph cache for multihop retrieval")
        parser.add_argument("--build-temporal-graph-cache", action="store_true", help="Build temporal event graph cache before running benchmark")
        parser.add_argument("--temporal-graph-cache-path", type=str, default=None, help="Override path to temporal event graph cache JSON")
        parser.add_argument("--partial-output", type=str, default=None, help="Path to JSONL file for partial per-example results")
        return parser

    def main(self, argv: list[str] | None = None) -> int:
        parser = self.build_arg_parser()
        args = parser.parse_args(argv)
        self.run(args)
        return 0

    def run(self, args: argparse.Namespace) -> tuple[str, str]:
        os.makedirs(args.output_dir, exist_ok=True)

        if args.skip_model_reload:
            os.environ["HF_HUB_OFFLINE"] = "1"

        client, temp_mem_path = self.index_builder.setup_isolated_env(
            args.benchmark,
            args.persist_dir,
        )
        loaded = self.load_dataset(args)
        caches = self.prepare_caches(args, loaded)
        modes_to_run = ALL_MODES if args.mode == "all" else [args.mode]

        feature_registry_path, feature_cache_identities, cache_status = self.preflight_feature_caches(
            args,
            loaded,
            caches,
        )

        mode_collections = self.index_builder.build_collections(
            client,
            temp_mem_path,
            loaded.examples,
            modes_to_run,
            args.benchmark,
            args.schema,
            args.turns_mode,
            batch_size=args.batch_size,
            validate_batch_count=not args.no_validate_batch_count,
            use_existing_index=args.use_existing_index,
        )

        all_results = self.suite.run_examples(
            examples=loaded.examples,
            modes=modes_to_run,
            mode_collections=mode_collections,
            adapter=loaded.adapter,
            retrieve_fn=run_retrieval,
            top_k=args.top_k,
            grammar_cache=caches.grammar_cache,
            temporal_cache=caches.temporal_cache,
            temporal_graph_cache=caches.temporal_graph_cache,
            partial_output=args.partial_output,
        )

        report_path, json_report_path = self.write_reports(
            args,
            loaded,
            caches,
            modes_to_run,
            all_results,
        )
        self.write_index_registry(
            args,
            caches,
            report_path,
            json_report_path,
            feature_registry_path,
            feature_cache_identities,
            cache_status,
        )
        return report_path, json_report_path

    @staticmethod
    def load_dataset(args: argparse.Namespace) -> LoadedBenchmark:
        print(f"[INFO] Initializing {args.benchmark} adapter...")
        if args.benchmark == "longmemeval_s":
            adapter = LongMemEvalAdapter()
            examples = adapter.load_dataset(
                args.data_path,
                args.limit,
                resolved_only=args.resolved_only,
                schema=args.schema,
                turns_mode=args.turns_mode,
            )
            unit_type = "session"
        else:
            adapter = LocomoAdapter()
            unit_type = args.unit_type or "turn"
            examples = adapter.load_dataset(args.data_path, args.limit, unit_type=unit_type)
        print(f"[INFO] Loaded {len(examples)} examples.")
        return LoadedBenchmark(adapter=adapter, examples=examples, unit_type=unit_type)

    def prepare_caches(self, args: argparse.Namespace, loaded: LoadedBenchmark) -> CacheBundle:
        grammar_path = args.grammar_cache_path or self.default_grammar_cache_path(
            args.benchmark,
            loaded.unit_type,
        )
        temporal_path = args.temporal_cache_path or self.default_temporal_cache_path(
            args.benchmark,
            loaded.unit_type,
        )
        temporal_graph_path = args.temporal_graph_cache_path or self.default_temporal_graph_cache_path(
            args.benchmark,
            loaded.unit_type,
        )

        grammar_cache = self._prepare_grammar_cache(args, loaded.examples, grammar_path)
        temporal_cache = self._prepare_temporal_cache(args, loaded.examples, temporal_path)
        temporal_graph_cache = self._prepare_temporal_graph_cache(
            args,
            temporal_cache,
            temporal_path,
            temporal_graph_path,
        )
        return CacheBundle(
            grammar_cache=grammar_cache,
            grammar_cache_path=grammar_path,
            temporal_cache=temporal_cache,
            temporal_cache_path=temporal_path,
            temporal_graph_cache=temporal_graph_cache,
            temporal_graph_cache_path=temporal_graph_path,
        )

    @staticmethod
    def default_grammar_cache_path(benchmark: str, unit_type: str) -> str:
        indexes_dir = os.path.join(path_config.DATA_DIR, "external", "indexes")
        if benchmark == "longmemeval_s":
            return os.path.join(indexes_dir, "longmemeval_s_grammar_cache_v2.json")
        return os.path.join(indexes_dir, f"locomo_grammar_cache_{unit_type}_v2.json")

    @staticmethod
    def default_temporal_cache_path(benchmark: str, unit_type: str) -> str:
        indexes_dir = os.path.join(path_config.DATA_DIR, "external", "indexes")
        if benchmark == "longmemeval_s":
            return os.path.join(indexes_dir, "longmemeval_s_temporal_cache.json")
        return os.path.join(indexes_dir, f"locomo_temporal_cache_{unit_type}.json")

    @staticmethod
    def default_temporal_graph_cache_path(benchmark: str, unit_type: str) -> str:
        indexes_dir = os.path.join(path_config.DATA_DIR, "external", "indexes")
        if benchmark == "longmemeval_s":
            return os.path.join(indexes_dir, "longmemeval_s_temporal_event_graph.json")
        return os.path.join(indexes_dir, f"locomo_temporal_event_graph_{unit_type}.json")

    @staticmethod
    def _write_cache(path: str, cache: dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)

    def _prepare_grammar_cache(
        self,
        args: argparse.Namespace,
        examples: list[Any],
        cache_path: str,
    ) -> dict[str, Any] | None:
        grammar_cache = None
        if args.build_grammar_cache:
            print(f"[INFO] Building grammar cache for {len(examples)} examples...")
            grammar_cache = build_grammar_cache_for_examples(examples)
            self._write_cache(cache_path, grammar_cache)
            print(f"[INFO] Grammar cache built and saved to {cache_path} ({len(grammar_cache)} entries)")

        if args.use_grammar_cache or args.mode in CLEAN_HYBRID_MODES or args.mode == "all":
            if grammar_cache is None and os.path.exists(cache_path):
                print(f"[INFO] Loading grammar cache from {cache_path}...")
                with open(cache_path, "r", encoding="utf-8") as f:
                    grammar_cache = json.load(f)
                print(f"[INFO] Loaded {len(grammar_cache)} cache entries.")
            elif grammar_cache is None:
                print(f"[WARN] Grammar cache not found at {cache_path}. clean_hybrid_grammar will run without cache.")
        return grammar_cache

    def _prepare_temporal_cache(
        self,
        args: argparse.Namespace,
        examples: list[Any],
        cache_path: str,
    ) -> dict[str, Any] | None:
        temporal_cache = None
        if args.build_temporal_cache:
            print(f"[INFO] Building temporal cache for {len(examples)} examples...")
            temporal_cache, _ = build_temporal_cache_for_examples(examples)
            self._write_cache(cache_path, temporal_cache)
            print(f"[INFO] Temporal cache built and saved to {cache_path} ({len(temporal_cache)} entries)")

        if args.use_temporal_cache or args.mode in TEMPORAL_MODES or args.mode == "all":
            if temporal_cache is None and os.path.exists(cache_path):
                print(f"[INFO] Loading temporal cache from {cache_path}...")
                with open(cache_path, "r", encoding="utf-8") as f:
                    temporal_cache = json.load(f)
                print(f"[INFO] Loaded {len(temporal_cache)} temporal cache entries.")
            elif temporal_cache is None:
                print(f"[WARN] Temporal cache not found at {cache_path}. clean_hybrid_temporal will run without cache.")
        return temporal_cache

    def _prepare_temporal_graph_cache(
        self,
        args: argparse.Namespace,
        temporal_cache: dict[str, Any] | None,
        temporal_cache_path: str,
        graph_cache_path: str,
    ) -> dict[str, Any] | None:
        temporal_graph_cache = None
        if args.build_temporal_graph_cache:
            from app.benchmarks.build_temporal_event_graph import build_temporal_event_graph

            print("[INFO] Building temporal event graph cache...")
            if temporal_cache is None and os.path.exists(temporal_cache_path):
                with open(temporal_cache_path, "r", encoding="utf-8") as f:
                    temporal_cache = json.load(f)
            if temporal_cache:
                temporal_graph_cache = build_temporal_event_graph(temporal_cache)
                self._write_cache(graph_cache_path, temporal_graph_cache)
                print(f"[INFO] Temporal event graph cache built and saved to {graph_cache_path}")
            else:
                print("[WARN] Cannot build temporal event graph: no temporal cache available.")

        if args.use_temporal_graph_cache or args.mode in TEMPORAL_GRAPH_MODES:
            if temporal_graph_cache is None and os.path.exists(graph_cache_path):
                print(f"[INFO] Loading temporal event graph cache from {graph_cache_path}...")
                with open(graph_cache_path, "r", encoding="utf-8") as f:
                    temporal_graph_cache = json.load(f)
                links = temporal_graph_cache.get("links", [])
                if links and "link_index" not in temporal_graph_cache:
                    print(f"[INFO] Pre-building link index from {len(links)} graph links...")
                    from app.benchmarks.temporal_multihop_scorer import _build_link_index

                    temporal_graph_cache["link_index"] = _build_link_index(links)
                    print("[INFO] Link index built.")
                print("[INFO] Loaded temporal event graph cache.")
            elif temporal_graph_cache is None:
                print(f"[WARN] Temporal event graph cache not found at {graph_cache_path}. Multihop will run without graph.")
        return temporal_graph_cache

    @staticmethod
    def preflight_feature_caches(
        args: argparse.Namespace,
        loaded: LoadedBenchmark,
        caches: CacheBundle,
    ) -> tuple[str, dict[str, dict[str, Any]], str]:
        pointer_manifest_path = os.path.join(
            path_config.DATA_DIR,
            "external",
            "indexes",
            "pointer_manifest.json",
        )
        feature_registry_path, feature_warnings = run_feature_cache_preflight(
            benchmark_name=args.benchmark,
            dataset_path=args.data_path,
            schema=args.schema,
            turns_mode=args.turns_mode,
            retrieval_mode=args.mode,
            grammar_cache_path=caches.grammar_cache_path if caches.grammar_cache is not None else None,
            temporal_cache_path=caches.temporal_cache_path if caches.temporal_cache is not None else None,
            temporal_graph_cache_path=caches.temporal_graph_cache_path if caches.temporal_graph_cache is not None else None,
            pointer_manifest_path=pointer_manifest_path if os.path.exists(pointer_manifest_path) else None,
            memory_unit_count=sum(len(example.memory_units) for example in loaded.examples),
            persist_path=args.persist_dir,
        )
        for warning in feature_warnings:
            print(f"[WARN] Feature cache provenance: {warning}")

        feature_registry = load_feature_cache_registry(feature_registry_path)
        feature_cache_identities = {
            entry["cache_type"]: {
                "cache_type": entry["cache_type"],
                "cache_path": entry.get("cache_path"),
                "cache_hash": entry.get("cache_hash"),
                "cache_version": entry.get("cache_version"),
            }
            for entry in feature_registry.get("entries", [])
        }
        cache_status = (
            "compatible"
            if feature_registry.get("compatibility", {}).get("compatible")
            else "incompatible"
        )
        return str(feature_registry_path), feature_cache_identities, cache_status

    def write_reports(
        self,
        args: argparse.Namespace,
        loaded: LoadedBenchmark,
        caches: CacheBundle,
        modes_to_run: list[str],
        all_results: dict[str, list[Any]],
    ) -> tuple[str, str]:
        report_context = BenchmarkReportContext(
            benchmark=args.benchmark,
            output_dir=args.output_dir,
            top_k=args.top_k,
            mode_arg=args.mode,
            examples_tested=len(loaded.examples),
            unit_type=args.unit_type if args.benchmark == "locomo" else None,
            resolved_only=args.resolved_only if args.benchmark == "longmemeval_s" else None,
            grammar_cache_path=caches.grammar_cache_path if caches.grammar_cache is not None else None,
            temporal_cache_path=caches.temporal_cache_path if caches.temporal_cache is not None else None,
            temporal_graph_cache_path=caches.temporal_graph_cache_path if caches.temporal_graph_cache is not None else None,
        )
        return self.report_writer.write(report_context, modes_to_run, all_results)

    def write_index_registry(
        self,
        args: argparse.Namespace,
        caches: CacheBundle,
        report_path: str,
        json_report_path: str,
        feature_registry_path: str,
        feature_cache_identities: dict[str, dict[str, Any]],
        cache_status: str,
    ) -> str:
        pointer_manifest_path = os.path.join(
            path_config.DATA_DIR,
            "external",
            "indexes",
            "pointer_manifest.json",
        )
        feature_registry = load_feature_cache_registry(feature_registry_path)
        registry_entries = self.index_builder.registry_entries(
            dataset_path=args.data_path,
            persist_path=args.persist_dir,
            grammar_cache_path=caches.grammar_cache_path if caches.grammar_cache is not None else None,
            temporal_cache_path=caches.temporal_cache_path if caches.temporal_cache is not None else None,
            temporal_graph_cache_path=caches.temporal_graph_cache_path if caches.temporal_graph_cache is not None else None,
            pointer_manifest_path=pointer_manifest_path if os.path.exists(pointer_manifest_path) else None,
            run_artifact_paths=[report_path, json_report_path],
            feature_registry_path=feature_registry_path,
            feature_cache_identities=feature_cache_identities,
            parser_version=feature_registry.get("parser_version"),
            cache_compatibility_status=cache_status,
        )
        registry_path = write_registry(args.benchmark, args.schema, args.turns_mode, registry_entries)
        print(f"[INFO] Index registry saved to {registry_path}")
        return registry_path


def main(argv: list[str] | None = None) -> int:
    return ExternalBenchmarkRunner().main(argv)
