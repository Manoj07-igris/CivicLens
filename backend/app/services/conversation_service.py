"""Conversation Service for CivicLens.

Manages conversational sessions and message persistence in SQLite.
Enforces atomicity, automatic titling, and cascade cleanup.
"""

import datetime
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import Settings, get_settings
from app.core.errors import ConversationNotFoundError, DocumentProcessingError
from app.db.database import Database, from_json, get_database, to_json, utc_now_iso
from app.models.agent import AgentResponse
from app.models.conversations import (
    ConversationImportRequest,
    ConversationMessage,
    ConversationMetadata,
)
from app.services.activity_service import get_activity_service

logger = logging.getLogger("civiclens.conversations")


def derive_auto_title(user_query: str, max_chars: int = 60) -> str:
  """Derive a clean, human-readable conversation title without external LLM calls."""
  clean = " ".join(user_query.strip().split())
  if not clean:
    return "New Conversation"
  # Take first sentence or first max_chars
  for sep in [".", "?", "!", "\n"]:
    if sep in clean:
      idx = clean.find(sep)
      if idx > 8:
        clean = clean[:idx].strip()
        break
  if len(clean) > max_chars:
    clean = clean[:max_chars].rstrip() + "..."
  return clean or "New Conversation"


class ConversationService:
  """Service managing stored chat sessions and messages in SQLite."""

  def __init__(self, settings: Optional[Settings] = None, db: Optional[Database] = None):
    self._settings = settings or get_settings()
    self._db = db or get_database()

  def create_conversation(
      self,
      title: Optional[str] = None,
      language_setting: str = "auto",
      document_ids: Optional[List[str]] = None,
      conv_id: Optional[str] = None,
      created_at: Optional[str] = None,
      owner_id: str = "local",
  ) -> ConversationMetadata:
    """Create a new conversational session."""
    cid = conv_id or str(uuid.uuid4())
    now_iso = created_at or utc_now_iso()
    doc_ids = document_ids or []
    safe_title = (title.strip() if title and title.strip() else "New Conversation")[:120]

    sql = """
      INSERT INTO conversations (
        id, owner_id, title, language_setting, document_ids, message_count, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, 0, ?, ?);
    """
    with self._db.transaction():
      self._db.execute(sql, (cid, owner_id, safe_title, language_setting, to_json(doc_ids), now_iso, now_iso))

    get_activity_service().record_activity("conversation.started", "conversation", cid, owner_id=owner_id)

    return ConversationMetadata(
        id=cid,
        title=safe_title,
        language_setting=language_setting,
        document_ids=doc_ids,
        message_count=0,
        created_at=now_iso,
        updated_at=now_iso,
    )

  def get_conversation(self, conversation_id: str, owner_id: Optional[str] = None) -> ConversationMetadata:
    """Retrieve metadata header for a conversation."""
    if owner_id is not None:
      row = self._db.fetchone(
          "SELECT id, title, language_setting, document_ids, message_count, created_at, updated_at FROM conversations WHERE id = ? AND owner_id = ?;",
          (conversation_id, owner_id),
      )
    else:
      row = self._db.fetchone(
          "SELECT id, title, language_setting, document_ids, message_count, created_at, updated_at FROM conversations WHERE id = ?;",
          (conversation_id,),
      )
    if not row:
      raise ConversationNotFoundError(f"Conversation '{conversation_id}' not found.")
    doc_ids = from_json(row["document_ids"]) or []
    return ConversationMetadata(
        id=row["id"],
        title=row["title"],
        language_setting=row["language_setting"],
        document_ids=doc_ids,
        message_count=row["message_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

  def list_conversations(
      self, limit: int = 20, offset: int = 0, owner_id: Optional[str] = None
  ) -> Tuple[List[ConversationMetadata], int]:
    """Return paginated list of conversations ordered by updated_at DESC."""
    if owner_id is not None:
      count_row = self._db.fetchone("SELECT COUNT(*) AS total FROM conversations WHERE owner_id = ?;", (owner_id,))
      total = count_row["total"] if count_row else 0

      sql = """
        SELECT id, title, language_setting, document_ids, message_count, created_at, updated_at
        FROM conversations
        WHERE owner_id = ?
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?;
      """
      rows = self._db.fetchall(sql, (owner_id, limit, offset))
    else:
      count_row = self._db.fetchone("SELECT COUNT(*) AS total FROM conversations;")
      total = count_row["total"] if count_row else 0

      sql = """
        SELECT id, title, language_setting, document_ids, message_count, created_at, updated_at
        FROM conversations
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?;
      """
      rows = self._db.fetchall(sql, (limit, offset))
    items = []
    for r in rows:
      doc_ids = from_json(r["document_ids"]) or []
      items.append(
          ConversationMetadata(
              id=r["id"],
              title=r["title"],
              language_setting=r["language_setting"],
              document_ids=doc_ids,
              message_count=r["message_count"],
              created_at=r["created_at"],
              updated_at=r["updated_at"],
          )
      )
    return items, total

  def get_messages(
      self, conversation_id: str, limit: int = 50, before_seq: Optional[int] = None, owner_id: Optional[str] = None
  ) -> Tuple[List[ConversationMessage], bool]:
    """Retrieve messages for a conversation in chronological order."""
    # Verify conversation exists and user owns it
    self.get_conversation(conversation_id, owner_id=owner_id)

    if before_seq is not None:
      sql = """
        SELECT id, conversation_id, seq, role, content, language_used, intent, grounded, model, meta, created_at
        FROM messages
        WHERE conversation_id = ? AND seq < ?
        ORDER BY seq DESC
        LIMIT ?;
      """
      rows = self._db.fetchall(sql, (conversation_id, before_seq, limit + 1))
    else:
      sql = """
        SELECT id, conversation_id, seq, role, content, language_used, intent, grounded, model, meta, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY seq DESC
        LIMIT ?;
      """
      rows = self._db.fetchall(sql, (conversation_id, limit + 1))

    has_more = len(rows) > limit
    returned_rows = rows[:limit]
    # Reverse to return in chronological order
    returned_rows.reverse()

    results: List[ConversationMessage] = []
    for r in returned_rows:
      meta = from_json(r["meta"]) or {}
      results.append(
          ConversationMessage(
              id=r["id"],
              conversation_id=r["conversation_id"],
              seq=r["seq"],
              role=r["role"],
              content=r["content"],
              language_used=r["language_used"],
              intent=r["intent"],
              grounded=bool(r["grounded"]) if r["grounded"] is not None else None,
              model=r["model"],
              meta=meta,
              created_at=r["created_at"],
          )
      )
    return results, has_more

  def update_conversation(
      self,
      conversation_id: str,
      title: Optional[str] = None,
      language_setting: Optional[str] = None,
      document_ids: Optional[List[str]] = None,
      owner_id: Optional[str] = None,
  ) -> ConversationMetadata:
    """Patch conversation metadata."""
    existing = self.get_conversation(conversation_id, owner_id=owner_id)
    now_iso = utc_now_iso()

    new_title = (title.strip()[:120]) if title is not None else existing.title
    new_lang = language_setting if language_setting is not None else existing.language_setting
    new_docs = document_ids if document_ids is not None else existing.document_ids

    sql = """
      UPDATE conversations
      SET title = ?, language_setting = ?, document_ids = ?, updated_at = ?
      WHERE id = ?;
    """
    with self._db.transaction():
      self._db.execute(sql, (new_title, new_lang, to_json(new_docs), now_iso, conversation_id))

    return self.get_conversation(conversation_id, owner_id=owner_id)

  def delete_conversation(self, conversation_id: str, owner_id: Optional[str] = None) -> bool:
    """Delete conversation and cascade messages."""
    self.get_conversation(conversation_id, owner_id=owner_id)
    with self._db.transaction():
      # Tool runs conversation_id set to NULL by foreign key or manually
      self._db.execute("UPDATE tool_runs SET conversation_id = NULL WHERE conversation_id = ?;", (conversation_id,))
      self._db.execute("DELETE FROM messages WHERE conversation_id = ?;", (conversation_id,))
      if owner_id is not None:
        cursor = self._db.execute("DELETE FROM conversations WHERE id = ? AND owner_id = ?;", (conversation_id, owner_id))
      else:
        cursor = self._db.execute("DELETE FROM conversations WHERE id = ?;", (conversation_id,))
      return cursor.rowcount > 0

  def delete_all_conversations(self, confirm: str, owner_id: Optional[str] = None) -> int:
    """Delete all conversations if confirmation phrase matches."""
    if confirm != self._settings.DELETE_ALL_CONFIRM_PHRASE:
      raise DocumentProcessingError(
          f"Confirmation phrase mismatch. Please enter '{self._settings.DELETE_ALL_CONFIRM_PHRASE}'."
      )
    with self._db.transaction():
      if owner_id is not None:
        rows = self._db.fetchall("SELECT id FROM conversations WHERE owner_id = ?;", (owner_id,))
        cids = [r["id"] for r in rows]
        for cid in cids:
          self._db.execute("UPDATE tool_runs SET conversation_id = NULL WHERE conversation_id = ?;", (cid,))
          self._db.execute("DELETE FROM messages WHERE conversation_id = ?;", (cid,))
        cursor = self._db.execute("DELETE FROM conversations WHERE owner_id = ?;", (owner_id,))
      else:
        self._db.execute("UPDATE tool_runs SET conversation_id = NULL;")
        self._db.execute("DELETE FROM messages;")
        cursor = self._db.execute("DELETE FROM conversations;")
      return cursor.rowcount

  def save_exchange(
      self,
      conversation_id: str,
      user_message: str,
      assistant_res: AgentResponse,
      owner_id: Optional[str] = None,
  ) -> Tuple[ConversationMessage, ConversationMessage]:
    """Atomically record citizen message + agent response and auto-title if needed."""
    meta = self.get_conversation(conversation_id, owner_id=owner_id)
    now_iso = utc_now_iso()

    with self._db.transaction():
      # Lock row and retrieve latest seq
      count_row = self._db.fetchone(
          "SELECT message_count, title FROM conversations WHERE id = ?;", (conversation_id,)
      )
      current_count = count_row["message_count"] if count_row else 0
      current_title = count_row["title"] if count_row else "New Conversation"

      user_seq = current_count + 1
      asst_seq = current_count + 2

      user_msg_id = str(uuid.uuid4())
      asst_msg_id = str(uuid.uuid4())

      # 1. Insert user message
      sql_msg = """
        INSERT INTO messages (
          id, conversation_id, seq, role, content, language_used, intent, grounded, model, meta, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
      """
      self._db.execute(
          sql_msg,
          (
              user_msg_id, conversation_id, user_seq, "user", user_message,
              assistant_res.language_used, assistant_res.intent, None, None,
              "{}", now_iso,
          ),
      )

      # 2. Insert assistant response
      # Build meta artifact package
      meta_payload: Dict[str, Any] = {
          "sources": [s.model_dump() for s in assistant_res.sources],
          "tool_activity": [t.model_dump() for t in assistant_res.tool_activity],
          "verifications": [v.model_dump() for v in assistant_res.verifications],
          "checklists": [c.model_dump() for c in assistant_res.checklists],
          "grievances": [g.model_dump() for g in assistant_res.grievances],
          "browser_sessions": [b.model_dump() for b in assistant_res.browser_sessions],
          "warnings": assistant_res.warnings,
      }
      if assistant_res.pending_approval:
        meta_payload["pending_approval"] = assistant_res.pending_approval.model_dump()

      self._db.execute(
          sql_msg,
          (
              asst_msg_id, conversation_id, asst_seq, "assistant", assistant_res.reply,
              assistant_res.language_used, assistant_res.intent,
              1 if assistant_res.grounded else 0,
              assistant_res.model, to_json(meta_payload), now_iso,
          ),
      )

      # 3. Auto-title if still default
      new_title = current_title
      if current_title in ("New Conversation", "", None) or current_count == 0:
        new_title = derive_auto_title(user_message)

      self._db.execute(
          "UPDATE conversations SET message_count = ?, title = ?, updated_at = ? WHERE id = ?;",
          (asst_seq, new_title, now_iso, conversation_id),
      )

    user_obj = ConversationMessage(
        id=user_msg_id,
        conversation_id=conversation_id,
        seq=user_seq,
        role="user",
        content=user_message,
        language_used=assistant_res.language_used,
        intent=assistant_res.intent,
        grounded=None,
        model=None,
        meta={},
        created_at=now_iso,
    )
    asst_obj = ConversationMessage(
        id=asst_msg_id,
        conversation_id=conversation_id,
        seq=asst_seq,
        role="assistant",
        content=assistant_res.reply,
        language_used=assistant_res.language_used,
        intent=assistant_res.intent,
        grounded=assistant_res.grounded,
        model=assistant_res.model,
        meta=meta_payload,
        created_at=now_iso,
    )
    return user_obj, asst_obj

  def import_from_localstorage(self, req: ConversationImportRequest, owner_id: str = "local") -> int:
    """Bulk import conversations from frontend localStorage (one-time migration)."""
    imported_count = 0
    now_iso = utc_now_iso()

    for item in req.conversations:
      cid = item.id or str(uuid.uuid4())
      # Check if already exists
      existing = self._db.fetchone("SELECT id FROM conversations WHERE id = ?;", (cid,))
      if existing:
        continue

      title = (item.title or "Imported Conversation")[:120]
      lang = item.language_setting or "auto"
      docs = item.document_ids or []
      c_time = item.created_at or now_iso
      u_time = item.updated_at or c_time

      with self._db.transaction():
        self._db.execute(
            """
            INSERT INTO conversations (id, owner_id, title, language_setting, document_ids, message_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (cid, owner_id, title, lang, to_json(docs), len(item.messages), c_time, u_time),
        )

        for idx, m in enumerate(item.messages):
          mid = str(uuid.uuid4())
          role = m.get("role", "user")
          content = m.get("content", "")
          m_time = m.get("created_at") or c_time
          meta_str = to_json(m.get("meta", {})) if isinstance(m.get("meta"), dict) else "{}"

          self._db.execute(
              """
              INSERT INTO messages (id, conversation_id, seq, role, content, language_used, intent, grounded, model, meta, created_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
              """,
              (
                  mid, cid, idx + 1, role, content,
                  m.get("language_used"), m.get("intent"),
                  1 if m.get("grounded") else 0,
                  m.get("model"), meta_str, m_time,
              ),
          )

        imported_count += 1

    return imported_count


_conversation_service: Optional[ConversationService] = None

def get_conversation_service() -> ConversationService:
  global _conversation_service
  if _conversation_service is None:
    _conversation_service = ConversationService()
  return _conversation_service

def set_conversation_service(service: Optional[ConversationService]) -> None:
  global _conversation_service
  _conversation_service = service
