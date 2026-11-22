"""Conversations and Chat History API router."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import ConversationNotFoundError, DocumentProcessingError
from app.models.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationImportRequest,
    ConversationListResponse,
    ConversationMetadata,
    ConversationUpdateRequest,
)
from app.services.conversation_service import ConversationService, get_conversation_service

logger = logging.getLogger("civiclens.api.conversations")

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
  """List stored conversational sessions ordered by most recently updated."""
  items, total = service.list_conversations(limit=limit, offset=offset, owner_id=current_user.id)
  return ConversationListResponse(
      items=items,
      total=total,
      limit=limit,
      offset=offset,
  )


@router.post("", response_model=ConversationMetadata, status_code=status.HTTP_201_CREATED)
def create_conversation(
    req: ConversationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
  """Create a new conversational session."""
  return service.create_conversation(
      title=req.title,
      language_setting=req.language_setting,
      document_ids=req.document_ids,
      owner_id=current_user.id,
  )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_detail(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before_seq: Optional[int] = Query(default=None, ge=1),
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
  """Retrieve metadata and chronological messages for a conversation."""
  try:
    meta = service.get_conversation(conversation_id, owner_id=current_user.id)
    messages, has_more = service.get_messages(
        conversation_id=conversation_id,
        limit=limit,
        before_seq=before_seq,
        owner_id=current_user.id,
    )
    return ConversationDetailResponse(
        conversation=meta,
        messages=messages,
        has_more=has_more,
    )
  except ConversationNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/{conversation_id}", response_model=ConversationMetadata)
def update_conversation(
    conversation_id: str,
    req: ConversationUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
  """Update conversation title, language preference, or attached document IDs."""
  try:
    return service.update_conversation(
        conversation_id=conversation_id,
        title=req.title,
        language_setting=req.language_setting,
        document_ids=req.document_ids,
        owner_id=current_user.id,
    )
  except ConversationNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(
    conversation_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
  """Delete a single conversation and its associated messages."""
  try:
    service.delete_conversation(conversation_id, owner_id=current_user.id)
    return {"status": "deleted", "conversation_id": conversation_id}
  except ConversationNotFoundError as exc:
    raise HTTPException(status_code=404, detail=str(exc))


@router.delete("", status_code=status.HTTP_200_OK)
def delete_all_conversations(
    confirm: str = Query(..., description="Must match DELETE_ALL_CONFIRM_PHRASE"),
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
  """Delete all stored conversations for current user if confirmed."""
  try:
    count = service.delete_all_conversations(confirm=confirm, owner_id=current_user.id)
    return {"status": "deleted_all", "deleted_conversations_count": count}
  except DocumentProcessingError as exc:
    raise HTTPException(status_code=400, detail=str(exc))


@router.post("/import", status_code=status.HTTP_200_OK)
def import_conversations(
    req: ConversationImportRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
):
  """Bulk import conversations from frontend localStorage."""
  imported = service.import_from_localstorage(req, owner_id=current_user.id)
  return {"status": "imported", "imported_count": imported}
