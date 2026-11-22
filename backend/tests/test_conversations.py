"""Tests for Chat Conversation persistence, auto-titling, and localStorage import (Phase 15)."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.database import Database
from app.db.migrations.runner import MigrationRunner
from app.models.agent import AgentResponse, AgentToolActivityItem
from app.models.conversations import (
    ConversationImportItem,
    ConversationImportRequest,
)
from app.services.conversation_service import ConversationService
from app.main import app

client = TestClient(app)


@pytest.fixture
def conv_service(tmp_path: Path):
  """Provision an isolated ConversationService instance."""
  db_path = tmp_path / "conv_test.db"
  settings = Settings(
      DATABASE_PATH=str(db_path),
      DELETE_ALL_CONFIRM_PHRASE="DELETE ALL CONVERSATIONS",
  )
  db = Database(settings)
  runner = MigrationRunner(db)
  runner.run_migrations()
  service = ConversationService(settings, db=db)
  return service


def test_conversation_crud(conv_service: ConversationService):
  """Verify basic create, get, list, update, and delete for conversations."""
  # Create
  conv = conv_service.create_conversation(
      title="Pudhumai Penn Questions",
      language_setting="ta",
      document_ids=["doc_1", "doc_2"],
  )
  assert conv.id is not None
  assert conv.title == "Pudhumai Penn Questions"
  assert conv.language_setting == "ta"
  assert conv.document_ids == ["doc_1", "doc_2"]
  assert conv.message_count == 0

  # Get
  fetched = conv_service.get_conversation(conv.id)
  assert fetched.id == conv.id
  assert fetched.title == conv.title

  # List
  items, total = conv_service.list_conversations(limit=10)
  assert total >= 1
  assert any(c.id == conv.id for c in items)

  # Update
  updated = conv_service.update_conversation(
      conv.id,
      title="Updated Scheme Guidance",
      language_setting="auto",
  )
  assert updated.title == "Updated Scheme Guidance"
  assert updated.language_setting == "auto"

  # Delete
  deleted = conv_service.delete_conversation(conv.id)
  assert deleted is True


def test_save_exchange_and_auto_titling(conv_service: ConversationService):
  """Verify save_exchange records atomic user/assistant message pair and derives lazy title."""
  # Create conversation with default title
  conv = conv_service.create_conversation(title=None)
  assert conv.title == "New Conversation"

  # Mock agent response
  res = AgentResponse(
      reply="The Pudhumai Penn scheme provides Rs. 1,000 monthly financial assistance to eligible girl students.",
      language_used="en",
      intent="document_explanation",
      grounded=True,
      sources=[],
      verifications=[],
      checklists=[],
      grievances=[],
      browser_sessions=[],
      tool_activity=[
          AgentToolActivityItem(
              tool_name="retrieve_chunks",
              ui_label_key="tools.retrieve_chunks",
              status="success",
              summary="Found scheme circular excerpts.",
              duration_ms=45.2,
          )
      ],
      steps_used=1,
      model="gemini-2.5-flash",
      latency_ms=120.5,
  )

  user_msg, asst_msg = conv_service.save_exchange(
      conversation_id=conv.id,
      user_message="What is the monthly stipend for Pudhumai Penn scheme?",
      assistant_res=res,
  )

  assert user_msg.seq == 1
  assert user_msg.role == "user"
  assert asst_msg.seq == 2
  assert asst_msg.role == "assistant"
  assert asst_msg.grounded is True

  # Check auto-title was updated from default "New Conversation"
  updated_conv = conv_service.get_conversation(conv.id)
  assert updated_conv.message_count == 2
  assert updated_conv.title != "New Conversation"
  assert "Pudhumai Penn" in updated_conv.title


def test_message_pagination_before_seq(conv_service: ConversationService):
  """Verify message pagination with limit and before_seq."""
  conv = conv_service.create_conversation(title="Pagination Test")
  res = AgentResponse(
      reply="Acknowledged",
      language_used="en",
      intent="general_civic_information",
      grounded=False,
      sources=[],
      verifications=[],
      checklists=[],
      grievances=[],
      browser_sessions=[],
      tool_activity=[],
      steps_used=1,
      model="gemini-2.5-flash",
      latency_ms=10.0,
  )

  # Save 3 exchanges (6 messages total)
  for i in range(1, 4):
    conv_service.save_exchange(conv.id, f"Question {i}", res)

  # Fetch all (should return 6 messages)
  all_msgs, has_more = conv_service.get_messages(conv.id, limit=10)
  assert len(all_msgs) == 6
  assert has_more is False

  # Fetch latest 2 messages (seq 5 and 6)
  latest_2, has_more_2 = conv_service.get_messages(conv.id, limit=2)
  assert len(latest_2) == 2
  assert has_more_2 is True
  assert latest_2[0].seq == 5
  assert latest_2[1].seq == 6

  # Fetch 2 messages before seq 5 (seq 3 and 4)
  prev_2, has_more_prev = conv_service.get_messages(conv.id, limit=2, before_seq=5)
  assert len(prev_2) == 2
  assert prev_2[0].seq == 3
  assert prev_2[1].seq == 4


def test_import_from_localstorage(conv_service: ConversationService):
  """Verify bulk import of conversations formatted from browser localStorage."""
  local_items = [
      ConversationImportItem(
          id=str(uuid.uuid4()),
          title="Imported Chat 1",
          language_setting="en",
          document_ids=["doc_a"],
          created_at="2026-11-20T10:00:00Z",
          updated_at="2026-11-20T10:05:00Z",
          messages=[
              {"role": "user", "content": "Hello", "created_at": "2026-11-20T10:00:00Z"},
              {"role": "assistant", "content": "How can I help you?", "meta": {"intent": "general"}, "created_at": "2026-11-20T10:01:00Z"},
          ],
      ),
      ConversationImportItem(
          id=str(uuid.uuid4()),
          title="Imported Chat 2",
          language_setting="ta",
          document_ids=[],
          messages=[
              {"role": "user", "content": "வணக்கம்"},
              {"role": "assistant", "content": "வணக்கம்! நான் சிவிக்லென்ஸ்."},
          ],
      ),
  ]

  imported_count = conv_service.import_from_localstorage(
      ConversationImportRequest(conversations=local_items)
  )
  assert imported_count == 2

  # Verify conversations now exist in DB
  conv1 = conv_service.get_conversation(local_items[0].id)
  assert conv1.title == "Imported Chat 1"
  assert conv1.message_count == 2

  # Test idempotency (re-importing should skip existing)
  imp2 = conv_service.import_from_localstorage(
      ConversationImportRequest(conversations=local_items)
  )
  assert imp2 == 0


def test_delete_all_conversations(conv_service: ConversationService):
  """Verify bulk deletion requires exact confirmation phrase."""
  conv_service.create_conversation(title="Test 1")
  conv_service.create_conversation(title="Test 2")

  # Wrong phrase fails
  with pytest.raises(Exception):
    conv_service.delete_all_conversations("WRONG PHRASE")

  # Correct phrase succeeds
  deleted_count = conv_service.delete_all_conversations("DELETE ALL CONVERSATIONS")
  assert deleted_count >= 2

  items, total = conv_service.list_conversations()
  assert total == 0


def test_conversations_api_endpoints():
  """Verify FastAPI router endpoints for /api/v1/conversations."""
  # 1. Create conversation
  res = client.post(
      "/api/v1/conversations",
      json={"title": "API Test Chat", "language_setting": "en", "document_ids": []},
  )
  assert res.status_code == 201
  data = res.json()
  conv_id = data["id"]
  assert data["title"] == "API Test Chat"

  # 2. Get conversation
  get_res = client.get(f"/api/v1/conversations/{conv_id}")
  assert get_res.status_code == 200
  assert get_res.json()["conversation"]["id"] == conv_id

  # 3. Patch conversation
  patch_res = client.patch(
      f"/api/v1/conversations/{conv_id}",
      json={"title": "Patched API Chat"},
  )
  assert patch_res.status_code == 200
  assert patch_res.json()["title"] == "Patched API Chat"

  # 4. List conversations
  list_res = client.get("/api/v1/conversations?limit=10")
  assert list_res.status_code == 200
  assert list_res.json()["total"] >= 1

  # 5. Delete conversation
  del_res = client.delete(f"/api/v1/conversations/{conv_id}")
  assert del_res.status_code == 200
