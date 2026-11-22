"""API endpoints for the CivicLens Central AI Agent, tool inspection, and approvals."""

import collections
import logging
import time
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.agent.approval import ApprovalStore, get_approval_store
from app.agent.orchestrator import AgentOrchestrator, get_agent_orchestrator
from app.agent.tools import ToolRegistry, get_tool_registry
from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentNotFoundError,
    DocumentProcessingError,
)
from app.models.agent import (
    AgentChatRequest,
    AgentResponse,
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ToolDescriptor,
    ToolsListResponse,
)
from app.models.common import ErrorResponse

logger = logging.getLogger("civiclens.agent")
router = APIRouter(prefix="/agent", tags=["Central AI Agent"])


# In-memory rolling rate limiter for agent queries
class AgentRateLimiter:

  def __init__(self, max_requests: int = 10, window_seconds: int = 60):
    self.max_requests = max_requests
    self.window_seconds = window_seconds
    self._clients: Dict[str, collections.deque] = collections.defaultdict(collections.deque)

  def check(self, client_key: str) -> None:
    now = time.time()
    queue = self._clients[client_key]
    while queue and queue[0] <= now - self.window_seconds:
      queue.popleft()
    if len(queue) >= self.max_requests:
      raise HTTPException(
          status_code=status.HTTP_429_TOO_MANY_REQUESTS,
          detail=f"Agent rate limit exceeded ({self.max_requests} requests/minute). Please wait before asking again.",
      )
    queue.append(now)

  def reset(self) -> None:
    self._clients.clear()


_agent_rate_limiter = AgentRateLimiter()


def get_agent_rate_limiter() -> AgentRateLimiter:
  return _agent_rate_limiter


def reset_agent_rate_limit() -> None:
  _agent_rate_limiter.reset()


@router.post(
    "/chat",
    response_model=AgentResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Agent execution failed"},
    },
    summary="Send a message to the Central AI Agent with automatic tool calling",
)
async def agent_chat(
    body: AgentChatRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    limiter: AgentRateLimiter = Depends(get_agent_rate_limiter),
    settings: Settings = Depends(get_settings),
) -> AgentResponse:
  """Interact with the central agent, which decides whether to invoke backend tools."""
  client_ip = f"user:{current_user.id}" if current_user else (request.client.host if request.client else "unknown")
  limiter.max_requests = settings.AGENT_RATE_LIMIT_PER_MINUTE
  limiter.check(client_ip)

  req_id = getattr(request.state, "request_id", "unknown")

  response = await orchestrator.run(
      user_message=body.message,
      history=body.history,
      language=body.language,
      document_ids=body.document_ids,
      request_id=req_id,
      conversation_id=body.conversation_id,
      user_id=current_user.id,
  )

  # Safe privacy logging: never log user message, passage text, or response text
  logger.info(
      "Agent chat completed: req_id=%s, intent=%s, steps=%d, tools_count=%d, citations=%d, latency=%.2fms",
      req_id,
      response.intent,
      response.steps_used,
      len(response.tool_activity),
      len(response.sources),
      response.latency_ms,
  )

  return response


@router.get(
    "/tools",
    response_model=ToolsListResponse,
    summary="List all registered agent tools (available and planned)",
)
async def list_agent_tools(
    current_user: CurrentUser = Depends(get_current_user),
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ToolsListResponse:
  """Inspect the central agent tool registry and current availability status."""
  all_tools = registry.list_all()
  descriptors = [
      ToolDescriptor(
          name=t.name,
          description=t.description,
          risk_level=t.risk_level,
          requires_approval=t.requires_approval,
          status=t.status,
          ui_label_key=t.ui_label_key,
      )
      for t in all_tools
  ]

  available_count = sum(1 for t in all_tools if t.status == "available")
  planned_count = sum(1 for t in all_tools if t.status == "planned")

  return ToolsListResponse(
      tools=descriptors,
      total_available=available_count,
      total_planned=planned_count,
  )


@router.post(
    "/approvals/{approval_id}",
    response_model=ApprovalDecisionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Approval request not found or expired"},
    },
    summary="Submit citizen approval or denial for a sensitive agent action",
)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    orchestrator: AgentOrchestrator = Depends(get_agent_orchestrator),
    approvals: ApprovalStore = Depends(get_approval_store),
) -> ApprovalDecisionResponse:
  """Approve or deny an action requiring human authorization."""
  resumed = await orchestrator.resume_after_approval(
      approval_id=approval_id,
      decision=body.decision,
      user_id=current_user.id,
      is_admin=current_user.is_admin,
  )

  return ApprovalDecisionResponse(
      approval_id=approval_id,
      decision=body.decision,
      resumed_response=resumed,
      message=f"Action '{body.decision}' executed successfully.",
  )
