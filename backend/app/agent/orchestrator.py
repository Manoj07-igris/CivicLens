"""Central AI Agent Orchestrator for CivicLens.

Executes a bounded, safe function-calling loop with the Gemini API:
- Validates tool arguments with Pydantic models
- Enforces strict document authorization boundaries
- Intercepts sensitive actions for human approval
- Manages an EvidenceLedger and performs strict backend citation verification
- Prevents infinite loops, duplicate calls, and quota waste
"""

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

try:
  from google.genai import types
except ImportError:
  types = None  # type: ignore

from app.agent.approval import ApprovalStore, get_approval_store
from app.agent.tools import (
    AgentContext,
    EvidenceItem,
    EvidenceLedger,
    ToolDefinition,
    ToolRegistry,
    get_tool_registry,
)
from app.core.config import Settings, get_settings
from app.core.errors import (
    DocumentNotFoundError,
    DocumentProcessingError,
)
from app.core.pii_guard import ensure_no_pii
from app.core.prompts import get_agent_system_prompt
from app.models.agent import (
    AgentBrowserSessionSummaryItem,
    AgentChecklistSummaryItem,
    AgentGrievanceSummaryItem,
    AgentResponse,
    AgentSourceItem,
    AgentToolActivityItem,
    AgentVerificationSummaryItem,
    PendingApprovalInfo,
)
from app.models.chat import ChatMessage
from app.models.gemini import GeminiTokenUsage
from app.services.browser_service import BrowserService, get_browser_service
from app.services.comparison_service import ComparisonService, get_comparison_service
from app.services.document_store import DocumentStore, get_document_store
from app.services.gemini_service import (
    GeminiAPIError,
    GeminiError,
    GeminiService,
    ToolCallItem,
    get_gemini_service,
)
from app.services.language_service import (
    detect_language,
    resolve_reply_language,
)
from app.services.public_service_service import (
    PublicServiceService,
    get_public_service_service,
)
from app.services.rag_service import RAGService, get_rag_service
from app.services.source_library import SourceLibraryService, get_source_library_service
from app.services.verification_service import VerificationService, get_verification_service

logger = logging.getLogger("civiclens.agent.orchestrator")

UUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
CITATION_LABEL_REGEX = re.compile(r"\[([ECS]\d+)\]", re.IGNORECASE)


class AgentOrchestrator:
  """Central agent orchestrating tool calling, evidence gathering, and grounded answers."""

  def __init__(
      self,
      gemini_service: Optional[GeminiService] = None,
      tool_registry: Optional[ToolRegistry] = None,
      document_store: Optional[DocumentStore] = None,
      rag_service: Optional[RAGService] = None,
      comparison_service: Optional[ComparisonService] = None,
      source_service: Optional[SourceLibraryService] = None,
      verification_service: Optional[VerificationService] = None,
      public_service_service: Optional[PublicServiceService] = None,
      browser_service: Optional[BrowserService] = None,
      approval_store: Optional[ApprovalStore] = None,
      settings: Optional[Settings] = None,
  ) -> None:
    self._gemini = gemini_service or get_gemini_service()
    self._registry = tool_registry or get_tool_registry()
    self._store = document_store or get_document_store()
    self._rag = rag_service or get_rag_service()
    self._comparison = comparison_service or get_comparison_service()
    self._source_service = source_service or get_source_library_service()
    self._verification_service = verification_service or get_verification_service()
    self._public_service = public_service_service or get_public_service_service()
    self._browser_service = browser_service or get_browser_service()
    self._approvals = approval_store or get_approval_store()
    self._settings = settings or get_settings()

  async def run(
      self,
      user_message: str,
      history: Optional[List[ChatMessage]] = None,
      language: str = "auto",
      document_ids: Optional[List[str]] = None,
      request_id: Optional[str] = None,
      conversation_id: Optional[str] = None,
      user_id: Optional[str] = None,
  ) -> AgentResponse:
    """Execute the full agent reasoning loop for a citizen question."""
    clean_message = (user_message or "").strip()
    if not clean_message:
      raise DocumentProcessingError("Message content cannot be blank.")
    ensure_no_pii(clean_message, field_name="message")

    start_time = time.perf_counter()
    req_id = request_id or uuid.uuid4().hex[:12]
    active_doc_ids = [d.strip() for d in (document_ids or []) if d.strip()]

    # Load history from conversation storage if conversation_id provided and history empty
    active_history = list(history or [])
    if conversation_id and not active_history:
      try:
        from app.services.conversation_service import get_conversation_service
        stored_msgs, _ = get_conversation_service().get_messages(conversation_id, limit=20, owner_id=user_id)
        total_chars = 0
        loaded_history: List[ChatMessage] = []
        for m in reversed(stored_msgs):
          if total_chars + len(m.content) > 8000:
            break
          loaded_history.append(ChatMessage(role=m.role, content=m.content))
          total_chars += len(m.content)
        loaded_history.reverse()
        active_history = loaded_history
      except Exception as exc:
        logger.warning("[%s] Failed to load history for conversation %s: %s", req_id, conversation_id, exc)

    # 1. Resolve response language
    detected_lang = detect_language(clean_message)
    target_lang = resolve_reply_language(
        user_text=clean_message,
        selected_language=language,
        ui_language="en",
    )

    # 2. Build selected documents context block
    doc_context_str, verified_selected_ids = self._build_document_context(active_doc_ids, owner_id=user_id)

    # 3. Build system instruction
    system_instruction = get_agent_system_prompt(
        reply_language=target_lang,
        selected_documents_context=doc_context_str,
    )

    # 4. Get active tool declarations
    declarations = self._registry.to_gemini_declarations()

    # 5. Initialize run state
    evidence_ledger = EvidenceLedger()
    tool_activity: List[AgentToolActivityItem] = []
    warnings: List[str] = []
    verifications: List[AgentVerificationSummaryItem] = []
    checklists: List[AgentChecklistSummaryItem] = []
    grievances: List[AgentGrievanceSummaryItem] = []
    executed_call_signatures: Set[str] = set()

    agent_context = AgentContext(
        store=get_document_store(),
        rag_service=get_rag_service(),
        comparison_service=get_comparison_service(),
        source_service=get_source_library_service(),
        verification_service=get_verification_service(),
        public_service_service=get_public_service_service(),
        browser_service=get_browser_service(),
        selected_document_ids=verified_selected_ids,
        evidence_ledger=evidence_ledger,
        request_id=req_id,
        conversation_id=conversation_id,
        language=target_lang,
        user_id=user_id,
    )

    # 6. Format initial conversation messages into SDK Content
    contents = self._build_initial_contents(active_history, clean_message)

    max_steps = self._settings.AGENT_MAX_STEPS
    max_tools_per_run = self._settings.AGENT_MAX_TOOL_CALLS_PER_RUN
    total_tools_executed = 0
    step_count = 0
    final_reply: Optional[str] = None
    finish_reason: Optional[str] = None
    total_prompt_tokens = 0
    total_candidate_tokens = 0

    # 7. Multi-step Agent Loop
    while step_count < max_steps:
      step_count += 1

      step_result = await self._gemini.generate_with_tools(
          prompt_or_messages=contents,
          tools=declarations,
          system_instruction=system_instruction,
          temperature=0.1,
          timeout_seconds=self._settings.GEMINI_TIMEOUT_SECONDS,
      )

      if step_result.prompt_tokens:
        total_prompt_tokens += step_result.prompt_tokens
      if step_result.candidates_tokens:
        total_candidate_tokens += step_result.candidates_tokens

      # If model did not request any tools, it provided final text
      if not step_result.tool_calls:
        final_reply = step_result.text or ""
        finish_reason = step_result.finish_reason
        break

      # Model requested one or more tool calls
      requested_calls = step_result.tool_calls[:3]  # Max 3 tools per step

      # Append model turn with function calls to contents
      contents.append(self._make_model_function_call_content(requested_calls))

      # Execute each tool through Safe Execution Pipeline
      tool_responses_for_step = []

      for call in requested_calls:
        if total_tools_executed >= max_tools_per_run:
          logger.warning("[%s] Per-run tool limit (%d) reached. Skipping tool %s", req_id, max_tools_per_run, call.name)
          tool_activity.append(
              AgentToolActivityItem(
                  tool_name=call.name,
                  ui_label_key="tools.limitReached",
                  status="skipped",
                  summary="Per-run tool execution cap reached.",
                  duration_ms=0.0,
              )
          )
          tool_responses_for_step.append({
              "name": call.name,
              "response": {"error": "Maximum tool call limit for this request reached."},
          })
          continue

        # Check for approval requirement
        tool_def = self._registry.get(call.name)
        if tool_def and tool_def.status == "available" and tool_def.requires_approval:
          # Pause loop and create pending approval
          run_state = {
              "contents": self._serialize_contents(contents),
              "system_instruction": system_instruction,
              "declarations": declarations,
              "verified_selected_ids": verified_selected_ids,
              "target_lang": target_lang,
              "step_count": step_count,
              "total_tools_executed": total_tools_executed,
              "pending_tool_call": {"name": call.name, "args": call.args},
              "req_id": req_id,
              "user_id": user_id,
          }

          approval_desc = f"Action '{call.name}' requires citizen authorization."
          paused_intent = "document_explanation"
          paused_reply = "This action requires your confirmation before proceeding."

          if call.name == "register_demo_complaint":
            from app.services.grievance_store import get_grievance_store
            gid = call.args.get("grievance_id", "")
            try:
              g_rec = get_grievance_store().get(gid, owner_id=user_id)
              cat_name = g_rec.category.replace("_", " ").title()
              sub_name = g_rec.draft.subject_line or "Civic Complaint"
              approval_desc = f"Create a DEMO complaint record for: {cat_name} - {sub_name}. Nothing will be sent to any authority."
              call.args["draft_hash"] = g_rec.draft_hash
            except Exception:
              approval_desc = f"Create a DEMO complaint record for grievance '{gid}'. Nothing will be sent to any authority."
            paused_intent = "civic_complaint"
            paused_reply = "This action requires your confirmation before proceeding. This creates a DEMO record inside CivicLens. Nothing will be sent to any government authority."
          elif call.name == "open_service_portal":
            approval_desc = "Launch a controlled demo browser simulation of the public service portal (Income Certificate) on localhost."
            paused_intent = "browser_demo"
            paused_reply = "To practice the public service application workflow, CivicLens can launch a local demo simulation on localhost. Please confirm to start the demo portal session."
          elif call.name == "fill_demo_form":
            s_idx = call.args.get("step_index", 1)
            f_keys = list(call.args.get("values", {}).keys())
            approval_desc = f"Fill Step {s_idx} with fictional values: {f_keys}. Strictly educational demo."
            paused_intent = "browser_demo"
            paused_reply = f"CivicLens is ready to fill Step {s_idx} of the demo form with fictional details. Please confirm these values before they are entered."
          elif call.name == "submit_demo_application":
            approval_desc = "Submit the simulated demo application. This records a practice reference only; no real data is transmitted."
            paused_intent = "browser_demo"
            paused_reply = "You have reviewed the demo application. Please confirm to finalize this practice simulation."
          elif tool_def.status == "planned":
            paused_intent = "unavailable_feature"

          appr = self._approvals.create_approval(
              tool_name=call.name,
              description=approval_desc,
              args=call.args,
              run_state=run_state,
              user_id=user_id,
          )

          tool_activity.append(
              AgentToolActivityItem(
                  tool_name=call.name,
                  ui_label_key=tool_def.ui_label_key or f"tools.{call.name}",
                  status="pending_approval",
                  summary=f"Awaiting human approval for {call.name}.",
                  duration_ms=0.0,
              )
          )

          latency_ms = (time.perf_counter() - start_time) * 1000.0
          res = AgentResponse(
              reply=paused_reply,
              language_used=target_lang,
              intent=paused_intent,
              grounded=True,
              sources=[],
              verifications=[],
              checklists=[],
              grievances=[],
              browser_sessions=[],
              tool_activity=tool_activity,
              steps_used=step_count,
              model=self._gemini.active_model,
              latency_ms=round(latency_ms, 2),
              token_usage=GeminiTokenUsage(
                  prompt_tokens=total_prompt_tokens,
                  candidates_tokens=total_candidate_tokens,
                  total_tokens=total_prompt_tokens + total_candidate_tokens,
              ),
              pending_approval=appr.to_info(),
              conversation_id=conversation_id,
              warnings=["Paused pending citizen approval."],
          )
          if conversation_id:
            try:
              from app.services.conversation_service import get_conversation_service
              get_conversation_service().save_exchange(conversation_id, clean_message, res)
            except Exception as exc:
              logger.warning("[%s] Failed to persist paused exchange: %s", req_id, exc)
          return res

        # Execute single tool safely
        res_dict, activity_item = await self._execute_safe_pipeline(
            call=call,
            context=agent_context,
            executed_signatures=executed_call_signatures,
        )

        total_tools_executed += 1
        tool_activity.append(activity_item)
        tool_responses_for_step.append({
            "name": call.name,
            "response": res_dict,
        })

        if call.name == "check_claim" and isinstance(res_dict, dict) and "verification_id" in res_dict:
          claim_v_id = res_dict.get("verification_id", "")
          overall_v = res_dict.get("overall_verdict", "unverified")
          overall_s = res_dict.get("overall_summary", "")
          claims_info = [
              {"claim_id": c.get("claim_id", ""), "verdict": c.get("verdict", ""), "basis": c.get("verdict_basis", "")}
              for c in res_dict.get("claims", [])
          ]
          verifications.append(
              AgentVerificationSummaryItem(
                  verification_id=claim_v_id,
                  overall_verdict=overall_v,
                  claim_snippet=clean_message[:100],
                  overall_summary=overall_s,
                  per_claim_verdicts=claims_info,
              )
          )

        if call.name == "generate_checklist" and isinstance(res_dict, dict) and "guide_id" in res_dict:
          checklists.append(
              AgentChecklistSummaryItem(
                  guide_id=res_dict.get("guide_id", ""),
                  query=clean_message[:100],
                  mode=res_dict.get("mode", "source_grounded"),
                  total_items=res_dict.get("total_checklist_items", 0),
                  confirmed_items_count=res_dict.get("confirmed_items_count", 0),
                  sample_items=[i.get("text", "") for i in res_dict.get("checklist_items", [])[:3]],
                  matched_portals=[
                      {"name": p.get("name", ""), "url": p.get("url", "")}
                      for p in res_dict.get("vetted_portals", [])
                  ],
              )
          )

        if call.name in ("draft_complaint", "register_demo_complaint") and isinstance(res_dict, dict) and "grievance_id" in res_dict:
          g_id = res_dict.get("grievance_id", "")
          g_cat = res_dict.get("category", "")
          g_sev = res_dict.get("severity", "medium")
          g_safety = res_dict.get("safety_risk", False)
          g_state = "demo_registered" if call.name == "register_demo_complaint" else "draft"
          g_sub = res_dict.get("draft_subject", "") or res_dict.get("subject_line", "")
          g_demo_id = res_dict.get("demo_id")
          g_demo_status = res_dict.get("status")
          g_channels = [
              {"name": ch.get("name", ""), "url": ch.get("declared_link", "") or ch.get("url", "")}
              for ch in res_dict.get("matched_channels", [])
          ]
          grievances.append(
              AgentGrievanceSummaryItem(
                  grievance_id=g_id,
                  category=g_cat,
                  severity=g_sev,
                  safety_risk=g_safety,
                  state=g_state,
                  subject_line=g_sub,
                  demo_id=g_demo_id,
                  demo_status=g_demo_status,
                  matched_channels=g_channels,
              )
          )

      # Append tool response turn to contents
      contents.append(self._make_tool_response_content(tool_responses_for_step))

    # If loop ended because of step limit without final text
    if final_reply is None:
      logger.warning("[%s] Agent reached step limit (%d) without concluding.", req_id, max_steps)
      warnings.append("Step budget exceeded before conclusion. Answer reflects verified evidence gathered.")
      final_reply = (
          "I gathered available document evidence, but was unable to complete all reasoning steps. "
          "Here is the verified information found so far."
          if target_lang == "en"
          else "ஆவண ஆதாரங்கள் சேகரிக்கப்பட்டன, ஆனால் அனைத்துப் படிநிலைகளையும் முடிக்க இயலவில்லை. "
          "இதுவரை சரிபார்க்கப்பட்ட தகவல்கள் கீழே வழங்கப்பட்டுள்ளன."
      )

    # 8. Strict Backend Citation Verification
    verified_sources, grounded = self._verify_citations(
        reply_text=final_reply,
        ledger=evidence_ledger,
        tool_activity=tool_activity,
        warnings=warnings,
    )

    # 9. Derive Intent without extra LLM call
    intent = self._derive_intent(tool_activity)

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    logger.info(
        "Agent run finished: req_id=%s, intent=%s, steps=%d, tools_executed=%d, citations=%d, grounded=%s, latency=%.2fms",
        req_id,
        intent,
        step_count,
        total_tools_executed,
        len(verified_sources),
        grounded,
        latency_ms,
    )

    browser_sessions = [
        AgentBrowserSessionSummaryItem(
            session_id=s.session_id,
            portal_name=getattr(s, "portal_id", "CivicLens Demo Portal"),
            action=s.events[-1].action if s.events else "browser_action",
            current_step=s.current_step,
            total_steps=s.total_steps,
            status=s.status,
            application_number=getattr(s, "application_number", None),
            screenshot_url=getattr(s, "last_screenshot_url", None),
            summary=s.events[-1].message if s.events else "Browser session active",
        )
        for s in agent_context.browser_sessions
    ]

    res = AgentResponse(
        reply=final_reply,
        language_used=target_lang,
        intent=intent,
        grounded=grounded,
        sources=verified_sources,
        verifications=verifications,
        checklists=checklists,
        grievances=grievances,
        browser_sessions=browser_sessions,
        tool_activity=tool_activity,
        steps_used=step_count,
        model=self._gemini.active_model,
        latency_ms=round(latency_ms, 2),
        token_usage=GeminiTokenUsage(
            prompt_tokens=total_prompt_tokens,
            candidates_tokens=total_candidate_tokens,
            total_tokens=total_prompt_tokens + total_candidate_tokens,
        ) if (total_prompt_tokens or total_candidate_tokens) else None,
        pending_approval=None,
        conversation_id=conversation_id,
        warnings=warnings,
    )
    if conversation_id:
      try:
        from app.services.conversation_service import get_conversation_service
        get_conversation_service().save_exchange(conversation_id, clean_message, res, owner_id=user_id)
      except Exception as exc:
        logger.warning("[%s] Failed to persist final exchange: %s", req_id, exc)
    return res

  async def resume_after_approval(
      self,
      approval_id: str,
      decision: str,
      user_id: Optional[str] = None,
      is_admin: bool = False,
  ) -> AgentResponse:
    """Resume execution of a paused agent run after citizen decision."""
    appr = self._approvals.get_and_consume(approval_id, user_id=user_id, is_admin=is_admin)
    state = appr.run_state
    req_id = state.get("req_id", "approval_resume")
    clean_decision = str(decision).strip().lower()

    # Record approval decision into database
    try:
      from app.db.database import get_database, utc_now_iso
      db = get_database()
      owner_val = appr.user_id or state.get("user_id") or "local"
      sql = """
        INSERT INTO approvals (
          approval_id, owner_id, tool_name, risk_level, decision,
          bound_hash, reference_type, reference_id, method, created_at, decided_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ui', ?, ?);
      """
      pending_call = state.get("pending_tool_call", {})
      call_args_peek = pending_call.get("args", appr.args)
      b_hash = None
      r_type = None
      r_id = None
      if isinstance(call_args_peek, dict):
        b_hash = call_args_peek.get("draft_hash") or call_args_peek.get("review_hash")
        if "grievance_id" in call_args_peek:
          r_type = "grievance"
          r_id = call_args_peek["grievance_id"]
        elif "session_id" in call_args_peek:
          r_type = "browser_session"
          r_id = call_args_peek["session_id"]
      with db.transaction():
        db.execute(sql, (
            approval_id,
            owner_val,
            appr.tool_name,
            "sensitive",
            "approved" if clean_decision == "approve" else "denied",
            b_hash,
            r_type,
            r_id,
            getattr(appr, "created_at", utc_now_iso()),
            utc_now_iso(),
        ))
    except Exception as exc:
      logger.warning("[%s] Failed to record approval in database: %s", req_id, exc)

    logger.info("[%s] Resuming agent after approval decision: %s for tool %s", req_id, clean_decision, appr.tool_name)

    start_time = time.perf_counter()
    evidence_ledger = EvidenceLedger()
    tool_activity: List[AgentToolActivityItem] = []
    warnings: List[str] = []

    verified_selected_ids = state.get("verified_selected_ids", [])
    target_lang = state.get("target_lang", "en")
    system_instruction = state.get("system_instruction", "")
    declarations = state.get("declarations", [])

    agent_context = AgentContext(
        store=self._store,
        rag_service=self._rag,
        comparison_service=self._comparison,
        source_service=self._source_service,
        verification_service=self._verification_service,
        browser_service=self._browser_service,
        selected_document_ids=verified_selected_ids,
        evidence_ledger=evidence_ledger,
        request_id=req_id,
        language=target_lang,
        user_id=state.get("user_id") or user_id,
    )

    contents = self._deserialize_contents(state.get("contents", []))
    pending_call = state.get("pending_tool_call", {})
    call_name = pending_call.get("name", appr.tool_name)
    call_args = pending_call.get("args", appr.args)

    if clean_decision == "approve":
      # Execute the tool directly (skipping approval check)
      tool_def = self._registry.get(call_name)
      if tool_def:
        t_start = time.perf_counter()
        try:
          validated = tool_def.args_model.model_validate(call_args)
          res_dict = await asyncio.wait_for(
              tool_def.handler(validated, agent_context),
              timeout=tool_def.timeout_seconds,
          )
          dur = (time.perf_counter() - t_start) * 1000.0
          tool_activity.append(
              AgentToolActivityItem(
                  tool_name=call_name,
                  ui_label_key=tool_def.ui_label_key or f"tools.{call_name}",
                  status="success",
                  summary=f"Citizen approved action: {call_name}.",
                  duration_ms=round(dur, 1),
              )
          )
        except Exception as exc:
          dur = (time.perf_counter() - t_start) * 1000.0
          res_dict = {"error": f"Tool execution failed after approval: {exc}"}
          tool_activity.append(
              AgentToolActivityItem(
                  tool_name=call_name,
                  ui_label_key=tool_def.ui_label_key or f"tools.{call_name}",
                  status="error",
                  summary=f"Action failed after approval: {exc}",
                  duration_ms=round(dur, 1),
              )
          )
      else:
        res_dict = {"error": f"Tool '{call_name}' no longer available."}
    else:
      res_dict = {"status": "declined", "message": "The citizen declined to approve the execution of this action."}
      tool_activity.append(
          AgentToolActivityItem(
              tool_name=call_name,
              ui_label_key=f"tools.{call_name}",
              status="rejected",
              summary="Citizen declined authorization for this action.",
              duration_ms=0.0,
          )
      )

    # Append function response to contents and resume single conclusion step
    contents.append(self._make_tool_response_content([{"name": call_name, "response": res_dict}]))

    step_result = await self._gemini.generate_with_tools(
        prompt_or_messages=contents,
        tools=declarations,
        system_instruction=system_instruction,
        temperature=0.1,
    )

    final_reply = step_result.text or (
        "Action was canceled as requested." if clean_decision == "deny" else "Action completed."
    )

    verified_sources, grounded = self._verify_citations(
        reply_text=final_reply,
        ledger=evidence_ledger,
        tool_activity=tool_activity,
        warnings=warnings,
    )

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    resumed_grievances: List[AgentGrievanceSummaryItem] = []
    if clean_decision == "approve" and call_name == "register_demo_complaint" and isinstance(res_dict, dict) and "grievance_id" in res_dict:
      resumed_grievances.append(
          AgentGrievanceSummaryItem(
              grievance_id=res_dict.get("grievance_id", ""),
              category=res_dict.get("category", ""),
              severity="medium",
              safety_risk=False,
              state="demo_registered",
              subject_line=res_dict.get("subject_line", ""),
              demo_id=res_dict.get("demo_id"),
              demo_status=res_dict.get("status"),
          )
      )

    resumed_browser_sessions: List[AgentBrowserSessionSummaryItem] = []
    if clean_decision == "approve" and call_name in ("open_service_portal", "fill_demo_form", "submit_demo_application"):
      resumed_browser_sessions = [
          AgentBrowserSessionSummaryItem(
              session_id=s.session_id,
              portal_name=getattr(s, "portal_id", "CivicLens Demo Portal"),
              action=s.events[-1].action if s.events else "browser_action",
              current_step=s.current_step,
              total_steps=s.total_steps,
              status=s.status,
              application_number=getattr(s, "application_number", None),
              screenshot_url=getattr(s, "last_screenshot_url", None),
              summary=s.events[-1].message if s.events else "Browser session active",
          )
          for s in agent_context.browser_sessions
      ]

    resumed_intent = (
        "browser_demo"
        if (call_name in ("open_service_portal", "fill_demo_form", "submit_demo_application") and clean_decision == "approve")
        else (
            "civic_complaint"
            if (call_name in ("draft_complaint", "register_demo_complaint") and clean_decision == "approve")
            else ("unavailable_feature" if clean_decision == "deny" else "document_explanation")
        )
    )

    return AgentResponse(
        reply=final_reply,
        language_used=target_lang,
        intent=resumed_intent,
        grounded=grounded,
        sources=verified_sources,
        grievances=resumed_grievances,
        browser_sessions=resumed_browser_sessions,
        tool_activity=tool_activity,
        steps_used=1,
        model=self._gemini.active_model,
        latency_ms=round(latency_ms, 2),
        token_usage=GeminiTokenUsage(
            prompt_tokens=step_result.prompt_tokens,
            candidates_tokens=step_result.candidates_tokens,
            total_tokens=step_result.total_tokens,
        ) if step_result.prompt_tokens else None,
        pending_approval=None,
        warnings=warnings,
    )

  # --- Internal Safe Execution Pipeline ---

  async def _execute_safe_pipeline(
      self,
      call: ToolCallItem,
      context: AgentContext,
      executed_signatures: Set[str],
  ) -> Tuple[Dict[str, Any], AgentToolActivityItem]:
    """Execute a single tool call through the 7-stage Safe Execution Pipeline."""
    fn_name = call.name.strip()
    fn_args = call.args or {}
    t_start = time.perf_counter()

    def _record_and_return(
        payload: Dict[str, Any], activity_item: AgentToolActivityItem, risk: str = "read_only"
    ) -> Tuple[Dict[str, Any], AgentToolActivityItem]:
      try:
        from app.db.database import get_database, utc_now_iso
        db = get_database()
        tr_id = str(uuid.uuid4())
        created_at = utc_now_iso()
        sql = """
          INSERT INTO tool_runs (
            id, owner_id, conversation_id, message_id, request_id,
            tool_name, risk_level, status, duration_ms, summary_key, step_index, created_at
          ) VALUES (?, 'local', ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with db.transaction():
          db.execute(sql, (
              tr_id,
              getattr(context, "conversation_id", None),
              context.request_id or "agent_run",
              activity_item.tool_name,
              risk,
              activity_item.status,
              int(activity_item.duration_ms),
              activity_item.ui_label_key,
              getattr(context, "current_step", 0),
              created_at,
          ))
      except Exception as exc:
        logger.warning("Failed to record tool_run in history: %s", exc)
      return payload, activity_item

    # Stage 1: Existence and Status check
    tool_def = self._registry.get(fn_name)
    if not tool_def or tool_def.status != "available":
      dur = (time.perf_counter() - t_start) * 1000.0
      logger.warning("Agent requested unavailable tool '%s'", fn_name)
      return _record_and_return(
          {
              "error": f"Tool '{fn_name}' is not available in this version. Explain plainly that this feature is not supported yet.",
              "status": "unavailable",
          },
          AgentToolActivityItem(
              tool_name=fn_name,
              ui_label_key=f"tools.{fn_name}",
              status="rejected",
              summary=f"Requested unavailable capability: {fn_name}.",
              duration_ms=round(dur, 1),
          ),
          risk="read_only",
      )

    ui_key = tool_def.ui_label_key or f"tools.{fn_name}"
    risk_level = tool_def.risk_level or "read_only"

    # Stage 2: Argument Validation with Pydantic
    try:
      validated_args = tool_def.args_model.model_validate(fn_args)
    except Exception as val_err:
      dur = (time.perf_counter() - t_start) * 1000.0
      logger.warning("Tool '%s' argument validation failed: %s", fn_name, val_err)
      return _record_and_return(
          {
              "error": f"Invalid arguments for tool '{fn_name}': {val_err}. Please correct your parameters.",
              "status": "validation_error",
          },
          AgentToolActivityItem(
              tool_name=fn_name,
              ui_label_key=ui_key,
              status="error",
              summary=f"Argument validation failed for {fn_name}.",
              duration_ms=round(dur, 1),
          ),
          risk=risk_level,
      )

    # Stage 3: Document Authorization & UUID Verification
    doc_id_arg = getattr(validated_args, "document_id", None)
    if doc_id_arg:
      clean_doc_id = str(doc_id_arg).strip()
      if not UUID_REGEX.match(clean_doc_id):
        dur = (time.perf_counter() - t_start) * 1000.0
        logger.warning("Rejected non-UUID document_id: %s", clean_doc_id)
        return _record_and_return(
            {
                "error": f"Document ID '{clean_doc_id}' is not a valid UUID format.",
                "status": "invalid_id",
            },
            AgentToolActivityItem(
                tool_name=fn_name,
                ui_label_key=ui_key,
                status="rejected",
                summary="Rejected invalid document identifier.",
                duration_ms=round(dur, 1),
            ),
            risk=risk_level,
        )

      doc_meta = self._store.get_metadata(clean_doc_id, owner_id=getattr(context, "user_id", None))
      if not doc_meta or doc_meta.get("status") not in ("ready", "ready_with_warnings"):
        dur = (time.perf_counter() - t_start) * 1000.0
        logger.warning("Requested document_id '%s' was not found or is not ready", clean_doc_id)
        return _record_and_return(
            {
                "error": f"Document '{clean_doc_id}' does not exist or is not ready for processing.",
                "status": "not_found",
            },
            AgentToolActivityItem(
                tool_name=fn_name,
                ui_label_key=ui_key,
                status="rejected",
                summary=f"Document not found or not ready: {clean_doc_id[:8]}...",
                duration_ms=round(dur, 1),
            ),
            risk=risk_level,
        )

      # If the user explicitly restricted context to a set of documents, enforce it
      if context.selected_document_ids and clean_doc_id not in context.selected_document_ids:
        dur = (time.perf_counter() - t_start) * 1000.0
        logger.warning("Document '%s' was not selected by user in active context", clean_doc_id)
        return _record_and_return(
            {
                "error": f"Document '{clean_doc_id}' is not among the documents selected for this inquiry.",
                "status": "unauthorized_document",
            },
            AgentToolActivityItem(
                tool_name=fn_name,
                ui_label_key=ui_key,
                status="rejected",
                summary=f"Access denied: document not selected by citizen.",
                duration_ms=round(dur, 1),
            ),
            risk=risk_level,
        )

    # Stage 4: Duplicate Call Loop Prevention
    call_sig = f"{fn_name}:{json.dumps(fn_args, sort_keys=True, default=str)}"
    if call_sig in executed_signatures:
      dur = (time.perf_counter() - t_start) * 1000.0
      logger.info("Short-circuiting duplicate tool call: %s", fn_name)
      return _record_and_return(
          {
              "notice": f"An identical call to tool '{fn_name}' was already executed in this session. Use the prior results.",
              "status": "already_executed",
          },
          AgentToolActivityItem(
              tool_name=fn_name,
              ui_label_key=ui_key,
              status="skipped",
              summary=f"Skipped identical repeated call to {fn_name}.",
              duration_ms=round(dur, 1),
          ),
          risk=risk_level,
      )
    executed_signatures.add(call_sig)

    # Stage 5: Execution with Timeout and Exception Guard
    timeout = tool_def.timeout_seconds or self._settings.AGENT_TOOL_TIMEOUT_SECONDS
    try:
      raw_result = await asyncio.wait_for(
          tool_def.handler(validated_args, context),
          timeout=timeout,
      )
      dur = (time.perf_counter() - t_start) * 1000.0

      # Generate safe, informative summary (no secrets or full text)
      summary = self._generate_safe_summary(fn_name, validated_args, raw_result)

      return _record_and_return(
          raw_result,
          AgentToolActivityItem(
              tool_name=fn_name,
              ui_label_key=ui_key,
              status="success",
              summary=summary,
              duration_ms=round(dur, 1),
          ),
          risk=risk_level,
      )

    except asyncio.TimeoutError:
      dur = (time.perf_counter() - t_start) * 1000.0
      logger.warning("Tool '%s' timed out after %ds", fn_name, timeout)
      return _record_and_return(
          {
              "error": f"Tool '{fn_name}' timed out after {timeout} seconds.",
              "status": "timeout",
          },
          AgentToolActivityItem(
              tool_name=fn_name,
              ui_label_key=ui_key,
              status="error",
              summary=f"Tool timed out after {timeout}s.",
              duration_ms=round(dur, 1),
          ),
          risk=risk_level,
      )
    except Exception as exc:
      dur = (time.perf_counter() - t_start) * 1000.0
      logger.exception("Unexpected exception executing tool '%s': %s", fn_name, exc)
      return _record_and_return(
          {
              "error": f"Tool '{fn_name}' encountered an error: {str(exc)}",
              "status": "execution_failed",
          },
          AgentToolActivityItem(
              tool_name=fn_name,
              ui_label_key=ui_key,
              status="error",
              summary=f"Error executing {fn_name}: {exc.__class__.__name__}.",
              duration_ms=round(dur, 1),
          ),
          risk=risk_level,
      )

  # --- Helpers ---

  def _build_document_context(
      self, document_ids: List[str], owner_id: Optional[str] = None
  ) -> Tuple[str, List[str]]:
    """Build a concise, un-spoofed context listing verified document metadata."""
    if not document_ids:
      return "", []

    lines = []
    verified_ids = []
    for d_id in document_ids:
      if not UUID_REGEX.match(d_id):
        continue
      meta = self._store.get_metadata(d_id, owner_id=owner_id)
      if meta and meta.get("status") in ("ready", "ready_with_warnings"):
        filename = meta.get("filename", "document.pdf")
        pages = meta.get("page_count", 1)
        lang = meta.get("language", "en")
        lines.append(f"- Document ID: {d_id} | Name: {filename} | Pages: {pages} | Language: {lang}")
        verified_ids.append(d_id)

    return "\n".join(lines), verified_ids

  def _build_initial_contents(
      self, history: List[ChatMessage], current_message: str
  ) -> List[Any]:
    """Convert conversational history and current message into SDK Content parts."""
    contents: List[Any] = []
    if types is None:
      for m in history:
        role = "user" if m.role == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.content}]})
      contents.append({"role": "user", "parts": [{"text": current_message}]})
      return contents

    for m in history:
      role = "user" if m.role == "user" else "model"
      contents.append(
          types.Content(
              role=role,
              parts=[types.Part.from_text(text=m.content)],
          )
      )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=current_message)],
        )
    )
    return contents

  def _make_model_function_call_content(self, calls: List[ToolCallItem]) -> Any:
    """Create a model Content turn requesting function calls."""
    if types is None:
      return {
          "role": "model",
          "parts": [{"function_call": {"name": c.name, "args": c.args}} for c in calls],
      }

    parts = [
        types.Part.from_function_call(name=c.name, args=c.args)
        for c in calls
    ]
    return types.Content(role="model", parts=parts)

  def _make_tool_response_content(self, responses: List[Dict[str, Any]]) -> Any:
    """Create a user Content turn providing function responses."""
    if types is None:
      return {
          "role": "user",
          "parts": [
              {"function_response": {"name": r["name"], "response": r["response"]}}
              for r in responses
          ],
      }

    parts = [
        types.Part.from_function_response(name=r["name"], response=r["response"])
        for r in responses
    ]
    return types.Content(role="user", parts=parts)

  def _serialize_contents(self, contents: List[Any]) -> List[Dict[str, Any]]:
    """Serialize contents into JSON-compatible dicts for approval persistence."""
    serialized = []
    for c in contents:
      if isinstance(c, dict):
        serialized.append(c)
      elif hasattr(c, "role") and hasattr(c, "parts"):
        parts_data = []
        for p in c.parts:
          fn_call = getattr(p, "function_call", None)
          fn_resp = getattr(p, "function_response", None)
          text = getattr(p, "text", None)
          if fn_call:
            parts_data.append({"function_call": {"name": fn_call.name, "args": fn_call.args}})
          elif fn_resp:
            parts_data.append({"function_response": {"name": fn_resp.name, "response": fn_resp.response}})
          elif text:
            parts_data.append({"text": text})
        serialized.append({"role": c.role, "parts": parts_data})
    return serialized

  def _deserialize_contents(self, serialized: List[Dict[str, Any]]) -> List[Any]:
    """Reconstruct Content objects from serialized approval data."""
    if types is None:
      return serialized

    reconstructed: List[Any] = []
    for item in serialized:
      role = item.get("role", "user")
      parts: List[Any] = []
      for p in item.get("parts", []):
        if "function_call" in p:
          fc = p["function_call"]
          parts.append(types.Part.from_function_call(name=fc["name"], args=fc.get("args", {})))
        elif "function_response" in p:
          fr = p["function_response"]
          parts.append(types.Part.from_function_response(name=fr["name"], response=fr.get("response", {})))
        elif "text" in p:
          parts.append(types.Part.from_text(text=p["text"]))
      reconstructed.append(types.Content(role=role, parts=parts))
    return reconstructed

  def _generate_safe_summary(self, tool_name: str, args: Any, result: Dict[str, Any]) -> str:
    """Generate safe, readable tool activity summary without leaking raw passages or secrets."""
    if tool_name == "list_documents":
      count = result.get("total_ready_count", 0)
      return f"Discovered {count} ready document(s)."
    elif tool_name == "retrieve_evidence":
      q = getattr(args, "query", "")
      preview_q = q[:40] + ("..." if len(q) > 40 else "")
      doc_name = result.get("filename", "policy document")
      count = result.get("passages_count", 0)
      lvl = result.get("evidence_level", "unknown")
      return f"Searched '{preview_q}' in {doc_name}: {count} passages ({lvl} evidence)."
    elif tool_name == "read_document":
      doc_name = result.get("filename", "document")
      pages = result.get("pages_read", 0)
      return f"Read {pages} page(s) from {doc_name}."
    elif tool_name == "compare_documents":
      old_n = result.get("old_document_name", "document")
      new_n = result.get("new_document_name", "document")
      counts = result.get("counts", {})
      return f"Compared {old_n} and {new_n}: {counts.get('modified', 0)} modified, {counts.get('added', 0)} added, {counts.get('removed', 0)} removed."
    elif tool_name == "search_official_sources":
      q = getattr(args, "query", "")
      preview_q = q[:40] + ("..." if len(q) > 40 else "")
      count = result.get("passages_count", 0)
      lvl = result.get("evidence_level", "unknown")
      return f"Searched official records for '{preview_q}': {count} passage(s) ({lvl} evidence)."
    elif tool_name == "check_claim":
      verdict = result.get("overall_verdict", "unverified")
      v_id = result.get("verification_id", "")
      return f"Fact verified claim: verdict '{verdict.upper()}' (report: {v_id[:8] if v_id else 'n/a'})."
    return f"Completed execution of {tool_name}."

  def _verify_citations(
      self,
      reply_text: str,
      ledger: EvidenceLedger,
      tool_activity: List[AgentToolActivityItem],
      warnings: List[str],
  ) -> Tuple[List[AgentSourceItem], bool]:
    """Parse bracketed citations [E1], [C1], [S1], drop unverified labels, and populate metadata."""
    found_labels = CITATION_LABEL_REGEX.findall(reply_text)
    unique_labels = list(dict.fromkeys([l.upper() for l in found_labels]))

    verified_sources: List[AgentSourceItem] = []
    dropped_count = 0

    for label in unique_labels:
      item = ledger.get_item(label)
      if item:
        verified_sources.append(
            AgentSourceItem(
                source_id=item.label,
                document_id=item.document_id,
                document_name=item.document_name,
                page_number=item.page_number,
                excerpt=item.excerpt,
                score=item.score if item.score > 0 else None,
                collection=item.collection,
                issuing_authority=item.issuing_authority,
                effective_date=item.effective_date,
                status=item.status,
                source_url=item.source_url,
                old_page_number=item.old_page_number,
                new_page_number=item.new_page_number,
                old_document_id=item.old_document_id,
                new_document_id=item.new_document_id,
                comparison_id=item.comparison_id,
            )
        )
      else:
        dropped_count += 1
        logger.warning("Dropped hallucinated/unverified citation label '[%s]'", label)

    if dropped_count > 0:
      warnings.append(f"Dropped {dropped_count} unverified citation reference(s).")

    # Check whether document claims were made without citations
    used_doc_tools = any(a.tool_name in ("retrieve_evidence", "read_document", "compare_documents", "search_official_sources", "check_claim") for a in tool_activity)
    has_evidence = len(ledger.list_items()) > 0

    grounded = True
    if used_doc_tools and has_evidence and not verified_sources:
      grounded = False
      warnings.append("Answer makes document references but could not be verified against cited passages.")

    return verified_sources, grounded

  def _derive_intent(self, tool_activity: List[AgentToolActivityItem]) -> str:
    """Derive intent category from backend execution history without extra LLM calls."""
    tool_names = [a.tool_name for a in tool_activity]
    statuses = [a.status for a in tool_activity]

    if "rejected" in statuses:
      return "unavailable_feature"

    if any(t in ("open_service_portal", "fill_demo_form", "submit_demo_application") for t in tool_names):
      return "browser_demo"

    if any(t in ("draft_complaint", "register_demo_complaint") for t in tool_names):
      return "civic_complaint"

    if "generate_checklist" in tool_names:
      return "public_service_guidance"

    if any(t in ("check_claim", "search_official_sources") for t in tool_names):
      return "fact_verification"

    if "compare_documents" in tool_names:
      return "policy_comparison"

    if any(t in ("retrieve_evidence", "read_document", "list_documents") for t in tool_names):
      return "document_explanation"

    return "general_civic_information"


# --- Service Singleton ---

_orchestrator_instance: Optional[AgentOrchestrator] = None


def get_agent_orchestrator() -> AgentOrchestrator:
  """Dependency provider returning shared AgentOrchestrator."""
  global _orchestrator_instance
  if _orchestrator_instance is None:
    _orchestrator_instance = AgentOrchestrator()
  return _orchestrator_instance


def set_agent_orchestrator(orchestrator: Optional[AgentOrchestrator]) -> None:
  """Test helper to inject or reset the AgentOrchestrator."""
  global _orchestrator_instance
  _orchestrator_instance = orchestrator
