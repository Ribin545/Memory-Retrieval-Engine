"""Version labels for current feature extraction and temporal components."""

TEMPORAL_PARSER_V1 = "temporal_parser_v1"
TEMPORAL_PARSER_V2_RELCL_ACL = "temporal_parser_v2_relcl_acl"
TEMPORAL_MULTIHOP_SCORER_V2 = "temporal_multihop_scorer_v2"
GRAMMAR_CACHE_V1 = "grammar_cache_v1"
TEMPORAL_CACHE_V1 = "temporal_cache_v1"
TEMPORAL_EVENT_GRAPH_V1 = "temporal_event_graph_v1"
POINTER_MANIFEST_V1_LEGACY = "pointer_manifest_v1_legacy"


PARSER_BY_MODE = {
    "clean_hybrid_temporal": TEMPORAL_PARSER_V1,
    "clean_hybrid_temporal_multihop": TEMPORAL_PARSER_V1,
    "clean_hybrid_temporal_multihop_v2": TEMPORAL_PARSER_V2_RELCL_ACL,
}


REQUIRED_CACHE_TYPES_BY_MODE = {
    "clean_hybrid": ("grammar",),
    "clean_hybrid_grammar": ("grammar",),
    "clean_hybrid_temporal": ("grammar", "temporal"),
    "clean_hybrid_temporal_multihop": ("grammar", "temporal", "temporal_graph"),
    "clean_hybrid_temporal_multihop_v2": ("grammar", "temporal", "temporal_graph"),
}
