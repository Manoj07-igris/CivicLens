"""RAG Service for CivicLens (Module 1 - Policy Intelligence).

Provides per-document FAISS vector indexing, hybrid retrieval (E5 vector + lexical token matching),
evidence-level evaluation, and grounded question answering with verified citations.
"""

import collections
import datetime
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from app.core.config import Settings, get_settings
from app.core.errors import DocumentNotFoundError, DocumentProcessingError
from app.core.pii_guard import ensure_no_pii
from app.core.prompts import get_rag_system_prompt, wrap_untrusted_content
from app.models.chat import ChatMessage, ToolActivityItem
from app.models.documents import (
    AskResponse,
    DocumentChunk,
    GroundedAnswer,
    IndexBuildResponse,
    PassageResult,
    VerifiedCitation,
)
from app.services.document_store import DocumentStore, get_document_store, validate_document_id
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.gemini_service import GeminiService, get_gemini_service
from app.services.language_service import resolve_reply_language

logger = logging.getLogger("civiclens.rag")


# In-memory LRU cache holding at most 3 FAISS indexes and chunk maps
class IndexCache:
  def __init__(self, capacity: int = 3):
    self.capacity = capacity
    self._cache: collections.OrderedDict = collections.OrderedDict()
    self._lock = threading.Lock()

  def get(self, doc_id: str) -> Optional[Tuple[faiss.IndexFlatIP, List[Dict[str, Any]]]]:
    with self._lock:
      if doc_id in self._cache:
        self._cache.move_to_end(doc_id)
        return self._cache[doc_id]
      return None

  def put(self, doc_id: str, index: faiss.IndexFlatIP, chunk_map: List[Dict[str, Any]]) -> None:
    with self._lock:
      if doc_id in self._cache:
        self._cache.move_to_end(doc_id)
      self._cache[doc_id] = (index, chunk_map)
      if len(self._cache) > self.capacity:
        self._cache.popitem(last=False)

  def invalidate(self, doc_id: str) -> None:
    with self._lock:
      self._cache.pop(doc_id, None)

  def clear(self) -> None:
    with self._lock:
      self._cache.clear()


_index_cache = IndexCache(capacity=3)


def get_index_cache() -> IndexCache:
  return _index_cache


def tokenize_text(text: str) -> List[str]:
  """Tokenize text preserving alphanumeric, Latin, and Tamil Unicode script characters."""
  if not text:
    return []
  # \w matches Unicode word characters (including Tamil script)
  tokens = re.findall(r"[\w\u0B80-\u0BFF]+", text.lower())
  return [t for t in tokens if len(t) > 1 or t.isdigit()]


def compute_lexical_score(query: str, chunk_text: str) -> float:
  """Lightweight lexical token-matching scorer for exact dates, numbers, and form codes."""
  q_tokens = tokenize_text(query)
  if not q_tokens:
    return 0.0

  chunk_lower = chunk_text.lower()
  matched_count = 0
  exact_number_boost = 0.0

  for token in q_tokens:
    if token in chunk_lower:
      matched_count += 1
      # Extra boost for dates, numbers, or currency tokens
      if any(c.isdigit() for c in token) or len(token) >= 5:
        exact_number_boost += 0.15

  base_ratio = matched_count / len(q_tokens)
  # Exact phrase matching boost
  clean_q = query.strip().lower()
  if len(clean_q) > 6 and clean_q in chunk_lower:
    base_ratio += 0.3

  return min(1.0, base_ratio + exact_number_boost)


class RAGService:
  """Orchestrates FAISS vector indexing, hybrid retrieval, and grounded Q&A."""

  def __init__(
      self,
      store: Optional[DocumentStore] = None,
      embeddings: Optional[EmbeddingService] = None,
      gemini: Optional[GeminiService] = None,
      settings: Optional[Settings] = None,
  ):
    self._store = store or get_document_store()
    self._embeddings = embeddings or get_embedding_service()
    self._gemini = gemini or get_gemini_service()
    self._settings = settings or get_settings()

  async def build_index(self, document_id: str, force: bool = False) -> IndexBuildResponse:
    """Build or rebuild a FAISS IndexFlatIP vector index for the document."""
    meta = self._store.get_metadata(document_id)
    if not meta:
      raise DocumentNotFoundError(f"Document '{document_id}' not found.")

    model_name = self._settings.EMBEDDING_MODEL_NAME
    idx_dir = self._store.get_index_dir(document_id)
    index_file = idx_dir / "index.faiss"
    map_file = idx_dir / "chunk_map.json"
    meta_file = idx_dir / "index_meta.json"

    # Idempotent check
    if not force and meta.get("index_status") == "indexed":
      if index_file.exists() and map_file.exists() and meta_file.exists():
        try:
          with open(meta_file, "r", encoding="utf-8") as f:
            idx_meta = json.load(f)
          if idx_meta.get("embedding_model") == model_name:
            return IndexBuildResponse(
                document_id=document_id,
                index_status="indexed",
                chunks_indexed=idx_meta.get("chunks_indexed", 0),
                chunks_skipped=idx_meta.get("chunks_skipped", 0),
                embedding_model=model_name,
                index_built_at=idx_meta.get("built_at"),
                message="Vector index is up-to-date.",
            )
        except Exception:
          logger.warning("Corrupt index metadata for %s; rebuilding index.", document_id)

    self._store.update_status(document_id, index_status="indexing")
    chunks = self._store.get_chunks(document_id)
    if not chunks:
      self._store.update_status(
          document_id,
          index_status="index_failed",
          error_message="Document contains no text chunks to index.",
      )
      raise DocumentProcessingError(
          "Document has no extracted chunks. Wait for processing or re-upload."
      )

    # Filter out empty or unreadable chunks
    usable_chunks: List[Dict[str, Any]] = []
    skipped_count = 0

    for c in chunks:
      text = c.get("text", "").strip()
      if len(text) < 15:
        skipped_count += 1
        continue
      usable_chunks.append(c)

    if not usable_chunks:
      self._store.update_status(
          document_id,
          index_status="index_failed",
          error_message="All chunks are empty or unreadable.",
      )
      raise DocumentProcessingError("No usable text chunks available for vector indexing.")

    try:
      texts_to_embed = [c["text"] for c in usable_chunks]
      start_t = time.perf_counter()

      # Compute L2-normalized passage embeddings
      vectors = await self._embeddings.embed_passages(texts_to_embed)
      dim = vectors.shape[1] if vectors.ndim == 2 else 384

      # Create FAISS IndexFlatIP (exact search on unit vectors)
      index = faiss.IndexFlatIP(dim)
      index.add(vectors)

      # Write index files atomically
      temp_idx = index_file.with_suffix(".faiss.tmp")
      faiss.write_index(index, str(temp_idx))
      temp_idx.replace(index_file)

      # Write chunk map
      temp_map = map_file.with_suffix(".json.tmp")
      with open(temp_map, "w", encoding="utf-8") as f:
        json.dump(usable_chunks, f, ensure_ascii=False, indent=2)
      temp_map.replace(map_file)

      now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
      idx_meta_data = {
          "document_id": document_id,
          "embedding_model": model_name,
          "chunks_indexed": len(usable_chunks),
          "chunks_skipped": skipped_count,
          "dim": dim,
          "built_at": now_iso,
      }
      with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(idx_meta_data, f, ensure_ascii=False, indent=2)

      # Cache in memory
      _index_cache.put(document_id, index, usable_chunks)

      self._store.update_status(
          document_id,
          index_status="indexed",
          index_built_at=now_iso,
          embedding_model=model_name,
          indexed_chunks_count=len(usable_chunks),
      )
      from app.services.activity_service import get_activity_service
      get_activity_service().record_activity("document.indexed", "document", document_id)

      duration_ms = (time.perf_counter() - start_t) * 1000.0
      logger.info(
          "Successfully built FAISS index for doc %s (%d chunks, %.1f ms)",
          document_id,
          len(usable_chunks),
          duration_ms,
      )

      return IndexBuildResponse(
          document_id=document_id,
          index_status="indexed",
          chunks_indexed=len(usable_chunks),
          chunks_skipped=skipped_count,
          embedding_model=model_name,
          index_built_at=now_iso,
          message=f"Successfully indexed {len(usable_chunks)} chunks into vector index.",
      )

    except Exception as exc:
      logger.exception("Failed to build vector index for doc %s: %s", document_id, exc)
      self._store.update_status(
          document_id,
          index_status="index_failed",
          error_message=f"Index build failed: {exc}",
      )
      raise DocumentProcessingError(f"Vector indexing failed: {exc}") from exc

  def _load_index_and_map(
      self, document_id: str
  ) -> Tuple[faiss.IndexFlatIP, List[Dict[str, Any]]]:
    """Load index and chunk map from LRU memory cache or disk."""
    cached = _index_cache.get(document_id)
    if cached is not None:
      return cached

    idx_dir = self._store.get_index_dir(document_id)
    index_file = idx_dir / "index.faiss"
    map_file = idx_dir / "chunk_map.json"

    if not index_file.exists() or not map_file.exists():
      raise FileNotFoundError(f"Vector index files missing for document '{document_id}'.")

    index = faiss.read_index(str(index_file))
    with open(map_file, "r", encoding="utf-8") as f:
      chunk_map = json.load(f)

    _index_cache.put(document_id, index, chunk_map)
    return index, chunk_map

  async def retrieve(
      self, document_id: str, query: str, top_k: int = 6
  ) -> Tuple[List[PassageResult], str]:
    """Retrieve top-scoring passages using hybrid vector + lexical token scoring.

    Returns (passages_list, evidence_level: 'strong' | 'weak' | 'none').
    """
    clean_query = query.strip()
    if not clean_query:
      return [], "none"

    meta = self._store.get_metadata(document_id)
    if not meta:
      raise DocumentNotFoundError(f"Document '{document_id}' not found.")

    doc_name = meta.get("filename", "document.pdf")

    # Ensure index exists; if not, build it lazily
    idx_dir = self._store.get_index_dir(document_id)
    if not (idx_dir / "index.faiss").exists() or meta.get("index_status") != "indexed":
      await self.build_index(document_id)

    index, chunk_map = self._load_index_and_map(document_id)
    total_chunks = len(chunk_map)
    if total_chunks == 0:
      return [], "none"

    # Encode query vector asynchronously
    q_vec = await self._embeddings.embed_query(clean_query)
    # Reshape for FAISS search: (1, dim)
    q_arr = np.expand_dims(q_vec, axis=0).astype(np.float32)

    # Search top candidates from vector index
    search_k = min(top_k * 3, total_chunks)
    vector_scores, vector_indices = index.search(q_arr, search_k)

    candidate_results: List[PassageResult] = []

    for rank, (v_score, idx) in enumerate(zip(vector_scores[0], vector_indices[0])):
      if idx < 0 or idx >= total_chunks:
        continue
      chunk_data = chunk_map[idx]
      chunk_text = chunk_data.get("text", "")

      # Lexical score calculation
      l_score = compute_lexical_score(clean_query, chunk_text)
      v_score_clamped = max(0.0, float(v_score))

      # Hybrid score combination: 70% semantic vector, 30% lexical exact token
      combined = 0.70 * v_score_clamped + 0.30 * l_score
      preview = chunk_text[:250].replace("\n", " ").strip()

      candidate_results.append(
          PassageResult(
              chunk_id=chunk_data.get("chunk_id", f"{document_id}_c{idx}"),
              document_id=document_id,
              document_name=doc_name,
              page_number=chunk_data.get("page_number", 1),
              chunk_index=chunk_data.get("chunk_index", 0),
              score=round(combined, 4),
              vector_score=round(v_score_clamped, 4),
              lexical_score=round(l_score, 4),
              excerpt=preview,
              text=chunk_text,
          )
      )

    # Sort descending by combined score
    candidate_results.sort(key=lambda p: p.score, reverse=True)

    # Filter by minimum score threshold
    min_score = self._settings.RETRIEVAL_MIN_SCORE
    filtered = [p for p in candidate_results if p.score >= min_score][:top_k]

    # Evaluate evidence level from retrieval signals strictly
    if not filtered or filtered[0].score < (min_score - 0.05):
      evidence_level = "none"
    elif filtered[0].score >= 0.75 or (len(filtered) >= 2 and filtered[1].score >= 0.70):
      evidence_level = "strong"
    else:
      evidence_level = "weak"

    return filtered, evidence_level

  async def retrieve_across(
      self,
      sources: List[Dict[str, Any]],
      query: str,
      top_k_per_source: int = 3,
      top_k_total: int = 8,
  ) -> Tuple[List[Dict[str, Any]], str, List[Dict[str, str]]]:
    """Retrieve top-scoring passages across multiple official sources and/or user documents.

    Uses the thread-safe IndexCache LRU (never loading more than capacity=3 indexes at once).
    Tags each passage with its collection ('official' | 'user') and source metadata.
    Returns (passages, evidence_level: 'strong' | 'weak' | 'none', skipped_sources).
    """
    clean_query = query.strip()
    if not clean_query or not sources:
      return [], "none", []

    # Encode query vector once for all sources
    q_vec = await self._embeddings.embed_query(clean_query)
    q_arr = np.expand_dims(q_vec, axis=0).astype(np.float32)

    all_passages: List[Dict[str, Any]] = []
    skipped_sources: List[Dict[str, str]] = []

    for src in sources:
      s_id = src.get("source_id") or src.get("document_id") or src.get("id")
      if not s_id:
        continue
      s_title = src.get("title") or src.get("filename") or "Document"
      collection = src.get("collection", "official")
      idx_dir = self._store.get_index_dir(s_id)

      # Check if index exists; build lazily if custom store provided
      if not (idx_dir / "index.faiss").exists():
        custom_store = src.get("store") or self._store
        try:
          chunks = custom_store.get_chunks(s_id)
          if not chunks:
            skipped_sources.append({
                "source_id": s_id,
                "title": s_title,
                "reason": "No extracted text chunks available",
            })
            continue

          # Temporarily build index with custom store
          orig_store = self._store
          self._store = custom_store
          try:
            await self.build_index(s_id)
          finally:
            self._store = orig_store
        except Exception as exc:
          logger.warning("Could not lazily index source %s: %s", s_id, exc)
          skipped_sources.append({
              "source_id": s_id,
              "title": s_title,
              "reason": f"Index build failed: {exc}",
          })
          continue

      try:
        index, chunk_map = self._load_index_and_map(s_id)
      except Exception as exc:
        logger.warning("Failed to load index for %s: %s", s_id, exc)
        skipped_sources.append({
            "source_id": s_id,
            "title": s_title,
            "reason": f"Index load failed: {exc}",
        })
        continue

      total_chunks = len(chunk_map)
      if total_chunks == 0:
        continue

      search_k = min(top_k_per_source * 3, total_chunks)
      vector_scores, vector_indices = index.search(q_arr, search_k)

      src_passages: List[Dict[str, Any]] = []
      for v_score, idx in zip(vector_scores[0], vector_indices[0]):
        if idx < 0 or idx >= total_chunks:
          continue
        chunk_data = chunk_map[idx]
        chunk_text = chunk_data.get("text", "")
        l_score = compute_lexical_score(clean_query, chunk_text)
        v_score_clamped = max(0.0, float(v_score))
        combined = 0.70 * v_score_clamped + 0.30 * l_score

        src_passages.append({
            "collection": collection,
            "source_id": s_id,
            "source_title": s_title,
            "issuing_authority": src.get("issuing_authority"),
            "effective_date": src.get("effective_date"),
            "status": src.get("status", "unknown"),
            "series_id": src.get("series_id"),
            "source_url": src.get("source_url"),
            "chunk_id": chunk_data.get("chunk_id", f"{s_id}_c{idx}"),
            "page_number": chunk_data.get("page_number", 1),
            "text": chunk_text,
            "excerpt": chunk_text[:250].replace("\n", " ").strip(),
            "score": round(combined, 4),
        })

      # Sort per-source candidates and take top_k_per_source
      src_passages.sort(key=lambda p: p["score"], reverse=True)
      all_passages.extend(src_passages[:top_k_per_source])

    # Global sort descending by score
    all_passages.sort(key=lambda p: p["score"], reverse=True)

    # Filter by minimum score threshold and cap at top_k_total
    min_score = self._settings.RETRIEVAL_MIN_SCORE
    filtered = [p for p in all_passages if p["score"] >= min_score][:top_k_total]

    if not filtered or filtered[0]["score"] < (min_score - 0.05):
      evidence_level = "none"
    elif filtered[0]["score"] >= 0.75 or (len(filtered) >= 2 and filtered[1]["score"] >= 0.70):
      evidence_level = "strong"
    else:
      evidence_level = "weak"

    return filtered, evidence_level, skipped_sources

  async def answer_question(
      self,
      document_id: str,
      question: str,
      language: str = "auto",
      history: Optional[List[ChatMessage]] = None,
  ) -> AskResponse:
    """Answer a citizen question using grounded RAG, Gemini structured output, and backend verification."""
    clean_question = question.strip()
    if not clean_question:
      raise DocumentProcessingError("Question cannot be blank.")
    ensure_no_pii(clean_question, field_name="question")

    meta = self._store.get_metadata(document_id)
    if not meta:
      raise DocumentNotFoundError(f"Document '{document_id}' not found.")

    doc_status = meta.get("status")
    if doc_status not in ("ready", "ready_with_warnings"):
      raise DocumentProcessingError(
          f"Document cannot be queried while status is '{doc_status}'. Please wait until processing completes."
      )

    doc_name = meta.get("filename", "document.pdf")
    doc_lang = meta.get("language", "en")
    target_lang = resolve_reply_language(clean_question, language)

    # 1. Retrieve passages
    start_t = time.perf_counter()
    passages, evidence_level = await self.retrieve(
        document_id, clean_question, top_k=self._settings.RETRIEVAL_TOP_K
    )

    tool_activity: List[ToolActivityItem] = [
        ToolActivityItem(
            tool_name="retrieve_evidence",
            summary=f"Retrieved {len(passages)} passages with {evidence_level} evidence",
            status="completed",
        )
    ]

    # 2. Evidence None Guardrail: Do NOT call Gemini
    if evidence_level == "none" or not passages:
      latency_ms = (time.perf_counter() - start_t) * 1000.0
      missing_msg = (
          "This document does not specify details regarding this question."
          if target_lang == "en"
          else "இந்த ஆவணத்தில் நீங்கள் கேட்ட கேள்விக்கான தகவல்கள் இடம்பெறவில்லை."
      )
      suggestion_msg = (
          "Please check your question phrasing, view the original document pages, or consult official government portals."
          if target_lang == "en"
          else "தயவுசெய்து உங்கள் வினாவைச் சரிபார்க்கவும், அசல் ஆவணத்தைப் பார்வையிடவும் அல்லது அதிகாரப்பூர்வ அரசு தளங்களை அணுகவும்."
      )
      return AskResponse(
          answer=f"{missing_msg}\n\n{suggestion_msg}",
          found=False,
          language_used=target_lang,
          evidence_level="none",
          citations=[],
          missing_information=missing_msg,
          follow_up_suggestion=suggestion_msg,
          retrieved_count=len(passages),
          unverified_citations=False,
          partial_context=False,
          model="none",
          latency_ms=round(latency_ms, 2),
          token_usage=None,
          tool_activity=tool_activity,
      )

    # 3. Context budget packing
    max_chars = self._settings.RAG_MAX_CONTEXT_CHARS
    packed_passages: List[PassageResult] = []
    current_chars = 0
    partial_context = False

    for p in passages:
      wrapped_item = wrap_untrusted_content(
          p.text, label=f"untrusted_passage chunk_id='{p.chunk_id}' page='{p.page_number}'"
      )
      if current_chars + len(wrapped_item) > max_chars:
        partial_context = True
        break
      packed_passages.append(p)
      current_chars += len(wrapped_item)

    if not packed_passages:
      packed_passages = [passages[0]]

    # 4. Assemble system prompt
    low_qual_notice = None
    if meta.get("warnings"):
      low_qual_notice = (
          "Note: Some pages of this document had image-only or low-quality text. "
          "If the answer is incomplete, mention that certain pages could not be fully read."
      )

    system_prompt = get_rag_system_prompt(
        reply_language=target_lang,
        low_quality_notice=low_qual_notice,
    )

    # Build user prompt with wrapped untrusted passages
    passages_block = "\n\n".join(
        wrap_untrusted_content(
            p.text,
            label=f"untrusted_passage chunk_id='{p.chunk_id}' page='{p.page_number}'",
        )
        for p in packed_passages
    )

    # History representation (purely for conversational reference)
    history_str = ""
    if history:
      recent_history = history[-3:]
      history_lines = [f"{m.role.capitalize()}: {m.content}" for m in recent_history]
      history_str = "[Prior Conversational Context]:\n" + "\n".join(history_lines) + "\n\n"

    user_prompt = (
        f"{history_str}Citizen Question:\n{clean_question}\n\n"
        f"Available Official Document Passages:\n{passages_block}\n\n"
        f"Please provide your structured response according to the directives."
    )

    # 5. Call Gemini structured generation
    grounded: GroundedAnswer = await self._gemini.generate_structured(
        prompt_or_messages=user_prompt,
        response_model=GroundedAnswer,
        system_instruction=system_prompt,
        temperature=0.1,
    )

    tool_activity.append(
        ToolActivityItem(
            tool_name="generate_grounded_answer",
            summary="Synthesized grounded answer with Gemini",
            status="completed",
        )
    )

    # 6. Critical Backend Verification
    valid_chunks_by_id = {p.chunk_id: p for p in passages}
    verified_citations: List[VerifiedCitation] = []
    dropped_citation_count = 0

    if grounded.citations:
      for item in grounded.citations:
        c_id = item.chunk_id.strip()
        if c_id not in valid_chunks_by_id:
          dropped_citation_count += 1
          continue

        passage_match = valid_chunks_by_id[c_id]
        chunk_clean = passage_match.text

        # Verify quote appears verbatim
        verified_quote = None
        if item.quote and item.quote.strip():
          clean_quote = item.quote.strip()
          # Normalize spaces for robust substring check
          norm_quote = re.sub(r"\s+", " ", clean_quote.lower())
          norm_chunk = re.sub(r"\s+", " ", chunk_clean.lower())
          if norm_quote in norm_chunk:
            verified_quote = clean_quote

        verified_citations.append(
            VerifiedCitation(
                chunk_id=c_id,
                document_id=document_id,
                document_name=doc_name,
                # Page number strictly from backend metadata
                page_number=passage_match.page_number,
                excerpt=passage_match.excerpt,
                verified_quote=verified_quote,
                score=passage_match.score,
            )
        )

    if dropped_citation_count > 0:
      logger.warning(
          "Dropped %d invalid/hallucinated citations for doc %s",
          dropped_citation_count,
          document_id,
      )

    unverified_citations = False
    if grounded.found and not verified_citations:
      unverified_citations = True

    latency_ms = (time.perf_counter() - start_t) * 1000.0

    return AskResponse(
        answer=grounded.answer,
        found=grounded.found,
        language_used=target_lang,
        evidence_level=evidence_level,
        citations=verified_citations,
        missing_information=grounded.missing_information,
        follow_up_suggestion=grounded.follow_up_suggestion,
        retrieved_count=len(passages),
        unverified_citations=unverified_citations,
        partial_context=partial_context,
        model=self._gemini.active_model,
        latency_ms=round(latency_ms, 2),
        token_usage=None,
        tool_activity=tool_activity,
    )


_rag_service_instance: Optional[RAGService] = None


def get_rag_service() -> RAGService:
  """Dependency provider returning singleton RAGService instance."""
  global _rag_service_instance
  if _rag_service_instance is None:
    _rag_service_instance = RAGService()
  return _rag_service_instance


def set_rag_service(service: Optional[RAGService]) -> None:
  """Test helper to inject or reset RAGService."""
  global _rag_service_instance
  _rag_service_instance = service


# Clean function aliases for direct tool registration in Phase 9
async def index_document(document_id: str, force: bool = False) -> IndexBuildResponse:
  return await get_rag_service().build_index(document_id, force=force)


async def retrieve(
    document_id: str, query: str, top_k: int = 6
) -> Tuple[List[PassageResult], str]:
  return await get_rag_service().retrieve(document_id, query, top_k=top_k)


async def answer_question(
    document_id: str,
    question: str,
    language: str = "auto",
    history: Optional[List[ChatMessage]] = None,
) -> AskResponse:
  return await get_rag_service().answer_question(
      document_id, question, language=language, history=history
  )
