"""
Embeddings (FR-015, Phase 3 knowledge layer).

This is a deterministic, dependency-free "hashing trick" bag-of-words
embedding: no API key, no network call, no ML model download required to
run the FYP locally. It's good enough to demonstrate retrieval over a
small document set (architecture docs, runbooks, previous incidents).

Swap `embed_text()` for a real embedding call (e.g. Gemini's
text-embedding-004, or any provider) when you're ready - every caller in
this module only depends on this function's signature
(str -> list[float] of fixed EMBEDDING_DIM), so nothing else needs to
change.
"""
from __future__ import annotations

import hashlib
import math
import re

EMBEDDING_DIM = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [_light_stem(t) for t in tokens]


def _light_stem(token: str) -> str:
    """Naive suffix stripping so 'deployment'/'deployments' etc. hash to the
    same bucket. A real embedding model wouldn't need this - it's only
    here because the hashing-trick placeholder has no notion of morphology
    on its own."""
    for suffix in ("ies", "ing", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def embed_text(text: str) -> list[float]:
    """Hash each token into one of EMBEDDING_DIM buckets, accumulate term
    frequency, then L2-normalize. Cosine similarity between two such
    vectors approximates shared-vocabulary overlap - a reasonable stand-in
    for semantic similarity on a small, topically narrow document set."""
    vector = [0.0] * EMBEDDING_DIM
    tokens = _tokenize(text)
    if not tokens:
        return vector

    for token in tokens:
        bucket = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % EMBEDDING_DIM
        vector[bucket] += 1.0

    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))  # already L2-normalized, so dot product == cosine
