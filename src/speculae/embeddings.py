"""
Optional semantic embedding layer for Speculae.

Two backends:
  - 'local'  : sentence-transformers (runs fully offline after first download)
  - 'openai' : OpenAI text-embedding API (BYOAK)

The module degrades gracefully if dependencies are missing — core
functionality (journaling, pattern detection, FTS5 search) never depends
on this module.
"""

from __future__ import annotations

import os

import numpy as np

from .config import EmbeddingsConfig


class EmbeddingsNotAvailable(Exception):
    """Raised when the configured backend cannot be loaded."""


# ── Backend loaders ───────────────────────────────────────────────────────────

class LocalEmbedder:
    """Sentence-transformers backend."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingsNotAvailable(
                "sentence-transformers not installed. "
                "Run: pip install speculae[semantic]"
            ) from exc

        self._model = SentenceTransformer(model_name)
        self.dim = self._model.get_sentence_embedding_dimension()

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()


class OpenAIEmbedder:
    """OpenAI embeddings backend (BYOAK)."""

    def __init__(self, model: str = "text-embedding-3-small", api_key: str = "") -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EmbeddingsNotAvailable(
                "openai not installed. Run: pip install speculae[llm]"
            ) from exc

        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise EmbeddingsNotAvailable(
                "No OpenAI API key. Set OPENAI_API_KEY or configure speculae."
            )
        self._client = OpenAI(api_key=key)
        self._model = model
        self.dim = 1536  # text-embedding-3-small

    def encode(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]


# ── Factory ──────────────────────────────────────────────────────────────────

_cached_embedder: LocalEmbedder | OpenAIEmbedder | None = None


def get_embedder(cfg: EmbeddingsConfig) -> LocalEmbedder | OpenAIEmbedder:
    global _cached_embedder
    if _cached_embedder is not None:
        return _cached_embedder

    if cfg.backend == "openai":
        _cached_embedder = OpenAIEmbedder(model=cfg.openai_model)
    else:
        _cached_embedder = LocalEmbedder(model_name=cfg.model)

    return _cached_embedder


# ── Cosine similarity search ──────────────────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def semantic_search(
    query: str,
    entries_with_embeddings: list[tuple],   # list of (Entry, embedding: list[float])
    top_k: int = 10,
    cfg: EmbeddingsConfig | None = None,
) -> list[tuple]:                            # list of (Entry, score)
    """Rank entries by cosine similarity to the query.

    Returns up to top_k (Entry, score) pairs, highest-similarity first.

    Scalability note
    ----------------
    Embeddings are stored as JSON blobs in the SQLite ``entries`` table and
    loaded into memory here for NumPy cosine similarity. This is fast and
    dependency-free for personal journals (hundreds to low thousands of
    entries), but will become a bottleneck beyond roughly 5 000-10 000 entries
    because:

    1. All embeddings are fetched from disk on every search call.
    2. The similarity loop is O(n) in Python with no batch optimisation.

    Future path: if larger datasets become a target use case, migrate to a
    dedicated vector index (e.g. FAISS, hnswlib, or sqlite-vss) and store
    embeddings outside of the main SQLite file.
    """
    if not entries_with_embeddings:
        return []

    embedder = get_embedder(cfg)
    query_vec = embedder.encode([query])[0]

    scored = []
    for entry, emb in entries_with_embeddings:
        if emb is None:
            continue
        score = cosine_similarity(query_vec, emb)
        scored.append((entry, score))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:top_k]
