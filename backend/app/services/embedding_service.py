"""Embedding service for CivicLens (Module 1 - Policy Intelligence & RAG).

Provides thread-safe lazy-loading of the intfloat/multilingual-e5-small embedding
model using FastEmbed (ONNX Runtime) on CPU. Enforces strict task-specific prefixes
('passage: ' and 'query: ') and L2-normalization for exact cosine similarity search.
"""

import asyncio
import logging
import threading
import time
from typing import List, Optional

import numpy as np

try:
  from fastembed import TextEmbedding
  from fastembed.common.model_description import ModelSource, PoolingType
except ImportError:
  TextEmbedding = None  # type: ignore
  ModelSource = None  # type: ignore
  PoolingType = None  # type: ignore

from app.core.config import Settings, get_settings

logger = logging.getLogger("civiclens.embeddings")

# E5 Prefix constants
# E5 models are trained using asymmetric contrastive learning:
# Passages (documents/chunks to be indexed) MUST be prefixed with 'passage: '
# Queries (questions searched against passages) MUST be prefixed with 'query: '
PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


def apply_passage_prefix(text: str) -> str:
  """Apply E5 passage prefix if not already present."""
  clean = text.strip()
  if clean.startswith(PASSAGE_PREFIX):
    return clean
  return f"{PASSAGE_PREFIX}{clean}"


def apply_query_prefix(text: str) -> str:
  """Apply E5 query prefix if not already present."""
  clean = text.strip()
  if clean.startswith(QUERY_PREFIX):
    return clean
  return f"{QUERY_PREFIX}{clean}"


def normalize_l2(vectors: np.ndarray) -> np.ndarray:
  """Normalize 2D vector array along axis 1 to unit L2 length.

  Ensures inner product search (faiss.IndexFlatIP) is mathematically
  identical to cosine similarity.
  """
  if vectors.size == 0:
    return vectors
  norms = np.linalg.norm(vectors, axis=1, keepdims=True)
  # Prevent division by zero
  norms[norms == 0.0] = 1.0
  return (vectors / norms).astype(np.float32)


class EmbeddingService:
  """Thread-safe, lazy-loading embedding engine for CPU execution."""

  def __init__(self, settings: Optional[Settings] = None):
    self._settings = settings or get_settings()
    self._model: Optional[TextEmbedding] = None
    self._lock = threading.Lock()
    self._model_name = self._settings.EMBEDDING_MODEL_NAME
    self._batch_size = self._settings.EMBEDDING_BATCH_SIZE
    self._is_available = True
    self._load_error: Optional[str] = None

  @property
  def model_name(self) -> str:
    return self._model_name

  def is_available(self) -> bool:
    """Return whether the embedding engine and packages are available."""
    return TextEmbedding is not None and self._is_available

  def _ensure_model_loaded_sync(self) -> TextEmbedding:
    """Load model synchronously under thread lock if not already loaded."""
    if self._model is not None:
      return self._model

    with self._lock:
      if self._model is not None:
        return self._model

      if TextEmbedding is None:
        self._is_available = False
        self._load_error = "FastEmbed library is not installed."
        raise RuntimeError(self._load_error)

      logger.info(
          "Lazy-loading embedding model '%s' on CPU (first use)...",
          self._model_name,
      )
      start_time = time.perf_counter()

      try:
        # Register custom model metadata if using multilingual-e5-small
        if "multilingual-e5-small" in self._model_name.lower():
          try:
            TextEmbedding.add_custom_model(
                model=self._model_name,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=self._model_name),
                dim=384,
                model_file="onnx/model.onnx",
            )
          except Exception as reg_err:
            logger.debug("Custom model registration notice: %s", reg_err)

        cache_dir_str = str(self._settings.embedding_cache_path)
        self._model = TextEmbedding(
            model_name=self._model_name,
            cache_dir=cache_dir_str,
        )

        load_duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "Embedding model '%s' loaded successfully in %.2f ms",
            self._model_name,
            load_duration_ms,
        )
        self._is_available = True
        return self._model

      except Exception as exc:
        self._is_available = False
        self._load_error = f"Failed to load embedding model: {exc}"
        logger.error(
            "Embedding model load failure for '%s': %s",
            self._model_name,
            exc,
        )
        raise RuntimeError(self._load_error) from exc

  def embed_passages_sync(self, texts: List[str]) -> np.ndarray:
    """Synchronously encode document chunks into L2-normalized vectors."""
    if not texts:
      return np.zeros((0, 384), dtype=np.float32)

    model = self._ensure_model_loaded_sync()
    prefixed = [apply_passage_prefix(t) for t in texts]

    # FastEmbed returns an iterator of numpy vectors
    raw_vectors = list(
        model.embed(prefixed, batch_size=self._batch_size)
    )
    arr = np.array(raw_vectors, dtype=np.float32)
    return normalize_l2(arr)

  def embed_query_sync(self, query: str) -> np.ndarray:
    """Synchronously encode a search question into an L2-normalized 1D vector."""
    clean = query.strip()
    if not clean:
      return np.zeros((384,), dtype=np.float32)

    model = self._ensure_model_loaded_sync()
    prefixed = apply_query_prefix(clean)

    raw_vectors = list(
        model.embed([prefixed], batch_size=1)
    )
    arr = np.array(raw_vectors[0], dtype=np.float32)
    # L2 normalize single vector
    norm = np.linalg.norm(arr)
    if norm > 0.0:
      arr = arr / norm
    return arr

  async def embed_passages(self, texts: List[str]) -> np.ndarray:
    """Asynchronously encode document chunks in threadpool."""
    return await asyncio.to_thread(self.embed_passages_sync, texts)

  async def embed_query(self, query: str) -> np.ndarray:
    """Asynchronously encode a search question in threadpool."""
    return await asyncio.to_thread(self.embed_query_sync, query)


_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
  """Dependency provider returning singleton EmbeddingService instance."""
  global _embedding_service_instance
  if _embedding_service_instance is None:
    _embedding_service_instance = EmbeddingService()
  return _embedding_service_instance


def set_embedding_service(service: Optional[EmbeddingService]) -> None:
  """Test helper to inject or reset EmbeddingService."""
  global _embedding_service_instance
  _embedding_service_instance = service
