from __future__ import annotations

import hashlib
import math

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.config import Settings


class HashingEmbeddings(Embeddings):
    """Deterministic character n-gram embeddings for offline reproducibility.

    This lightweight fallback is not a replacement for a production embedding
    model. It keeps the public demo and test suite usable without an API key.
    """

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        normalized = "".join(text.lower().split())
        grams: list[str] = []
        for size in (1, 2, 3):
            grams.extend(normalized[index : index + size] for index in range(len(normalized) - size + 1))
        vector = [0.0] * self.dimensions
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            sign = 1.0 if value & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def create_embeddings(settings: Settings, provider: str | None = None) -> Embeddings:
    selected = (provider or settings.embedding_provider).lower()
    if selected == "hash":
        return HashingEmbeddings()
    if selected == "qwen":
        if not settings.qwen_api_key:
            raise ValueError("DASHSCOPE_API_KEY is required for Qwen embeddings")
        return OpenAIEmbeddings(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_base_url,
            model=settings.embedding_model,
        )
    raise ValueError(f"unsupported embedding provider: {selected}")
