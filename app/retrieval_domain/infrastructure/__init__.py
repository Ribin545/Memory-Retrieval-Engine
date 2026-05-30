"""Infrastructure adapters for retrieval-domain services."""

__all__ = ["ChromaAddDiagnostics", "ChromaIndexRepository"]


def __getattr__(name: str):
    if name in __all__:
        from .chroma_index_repository import ChromaAddDiagnostics, ChromaIndexRepository

        return {
            "ChromaAddDiagnostics": ChromaAddDiagnostics,
            "ChromaIndexRepository": ChromaIndexRepository,
        }[name]
    raise AttributeError(name)
