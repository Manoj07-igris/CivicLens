import React, { useState, useEffect, useRef } from "react";
import { useSearchParams, useLocation, useNavigate, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  Bot,
  Send,
  Square,
  RotateCcw,
  Plus,
  Trash2,
  Edit2,
  Copy,
  Check,
  Paperclip,
  Languages,
  Sparkles,
  MessageSquare,
  AlertTriangle,
  PanelLeftClose,
  PanelLeftOpen,
  Info,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  FileText,
  ExternalLink,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { useLanguage } from "../hooks/useLanguage";
import { useChat } from "../hooks/useChat";
import { useToast } from "../hooks/useToast";
import { useDocuments } from "../hooks/useDocuments";

/**
 * Collapsible section for displaying agent tool execution steps and verified citations.
 */
function MessageActivityTimeline({
  toolActivity = [],
  sources = [],
  intent,
  grounded,
  warnings = [],
  verifications = [],
  checklists = [],
  grievances = [],
  browserSessions = [],
  onInspectSource,
  t,
}) {
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const hasContent =
    toolActivity.length > 0 ||
    sources.length > 0 ||
    verifications.length > 0 ||
    checklists.length > 0 ||
    grievances.length > 0 ||
    browserSessions.length > 0;

  if (!hasContent) return null;

  return (
    <div className="mt-3 pt-2 border-t border-slate-200/60">
      {/* Browser Demo Simulation Card if present */}
      {browserSessions.length > 0 && (
        <div className="mb-3 space-y-2 p-3 bg-blue-50/50 border border-blue-200 rounded-lg text-left">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-blue-900 uppercase tracking-wider block">
              Browser Demo Simulation (Module 4)
            </span>
            <Badge variant="outline" size="sm" className="bg-amber-100 text-amber-900 border-amber-300 font-bold">
              DEMO SIMULATION
            </Badge>
          </div>
          {browserSessions.map((bs, i) => (
            <div
              key={i}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white p-2.5 rounded border border-blue-200"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Badge variant={bs.status === "submitted" ? "success" : "primary"} size="sm">
                    {bs.status === "submitted" ? "DEMO SUBMITTED" : `STEP ${bs.current_step} OF ${bs.total_steps}`}
                  </Badge>
                  {bs.application_number && (
                    <span className="text-[10px] font-mono font-bold text-emerald-800 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-300">
                      {bs.application_number}
                    </span>
                  )}
                  <span className="text-xs font-semibold text-slate-900 truncate max-w-sm">
                    {bs.portal_name || "CivicLens Demo Portal"}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600">
                  {bs.summary || "Interactive public service application simulation."}
                </p>
                <div className="flex items-center gap-3 text-[10px] text-slate-500 pt-0.5">
                  <span className="capitalize">Action: {bs.action?.replace(/_/g, " ")}</span>
                  <span>•</span>
                  <span>Loopback Sandbox Only</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => navigate(`/services?tab=demo&session_id=${bs.session_id}`)}
                className="text-xs px-2.5 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 font-medium flex items-center gap-1 whitespace-nowrap self-start sm:self-center cursor-pointer transition-colors"
              >
                <span>View in Demo Workflow</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Civic Grievance Complaint Card if present */}
      {grievances.length > 0 && (
        <div className="mb-3 space-y-2 p-3 bg-slate-50 border border-slate-200 rounded-lg text-left">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
            Civic Complaint Representation (Module 5)
          </span>
          {grievances.map((g, i) => (
            <div
              key={i}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white p-2.5 rounded border border-slate-200"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Badge variant={g.safety_risk ? "danger" : "primary"} size="sm">
                    {g.category?.replace(/_/g, " ").toUpperCase()} • {g.severity?.toUpperCase()}
                  </Badge>
                  {g.demo_id && (
                    <span className="text-[10px] font-mono font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                      {g.demo_id}
                    </span>
                  )}
                  <span className="text-xs font-semibold text-slate-900 truncate max-w-sm">
                    {g.subject_line || "Civic Complaint Draft"}
                  </span>
                </div>
                {g.safety_risk && (
                  <p className="text-[11px] text-rose-700 font-semibold">
                    Immediate safety hazard signal flagged for this issue.
                  </p>
                )}
                <div className="flex items-center gap-3 text-[10px] text-slate-500 pt-0.5">
                  <span className="capitalize">Status: {g.state?.replace(/_/g, " ") || "Draft"}</span>
                  {g.channels_count > 0 && (
                    <>
                      <span>•</span>
                      <span>{g.channels_count} official channel(s)</span>
                    </>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => navigate(`/grievance?id=${g.grievance_id}`)}
                className="text-xs px-2.5 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 font-medium flex items-center gap-1 whitespace-nowrap self-start sm:self-center cursor-pointer transition-colors"
              >
                <span>Open in Grievance Centre</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
      {/* Public Service Guidance & Checklist Summary Card if present */}
      {checklists.length > 0 && (
        <div className="mb-3 space-y-2 p-3 bg-slate-50 border border-slate-200 rounded-lg text-left">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
            Public Service Guidance & Checklist
          </span>
          {checklists.map((c, i) => (
            <div
              key={i}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white p-2.5 rounded border border-slate-200"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Badge variant={c.mode === "source_grounded" ? "success" : "warning"} size="sm">
                    {c.mode === "source_grounded" ? "OFFICIAL SOURCE GROUNDED" : "GENERAL GUIDANCE"}
                  </Badge>
                  <span className="text-xs font-semibold text-slate-900 truncate max-w-sm">
                    {c.query}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 line-clamp-2">
                  {c.procedure_overview}
                </p>
                <div className="flex items-center gap-3 text-[10px] text-slate-500 pt-0.5">
                  <span>{c.total_items} checklist items</span>
                  <span>•</span>
                  <span className="text-emerald-700 font-medium">{c.confirmed_items} source-confirmed</span>
                  {c.key_facts_count > 0 && (
                    <>
                      <span>•</span>
                      <span>{c.key_facts_count} key facts</span>
                    </>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => navigate(`/services?guide_id=${c.guide_id}`)}
                className="text-xs px-2.5 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 font-medium flex items-center gap-1 whitespace-nowrap self-start sm:self-center cursor-pointer transition-colors"
              >
                <span>Open Full Guide</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Verification Summary Card if present */}
      {verifications.length > 0 && (
        <div className="mb-3 space-y-2 p-3 bg-slate-50 border border-slate-200 rounded-lg text-left">
          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider block">
            Fact Verification Outcome
          </span>
          {verifications.map((v, i) => (
            <div
              key={i}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white p-2.5 rounded border border-slate-200"
            >
              <div className="space-y-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Badge variant={v.overall_verdict} size="sm">
                    {v.overall_verdict.toUpperCase()}
                  </Badge>
                  <span className="text-xs font-semibold text-slate-900 truncate max-w-sm">
                    {v.claim_text}
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 line-clamp-2">
                  {v.overall_summary}
                </p>
              </div>
              <button
                type="button"
                onClick={() => navigate(`/verify?id=${v.verification_id}`)}
                className="text-xs px-2.5 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 font-medium flex items-center gap-1 whitespace-nowrap self-start sm:self-center cursor-pointer transition-colors"
              >
                <span>Full Verification</span>
                <ExternalLink className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between text-xs text-slate-500 hover:text-slate-800 transition-colors py-1 cursor-pointer"
        aria-expanded={isOpen}
      >
        <span className="flex items-center gap-1.5 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-600" />
          <span>{t("agent.sourcesTimeline.title", "Sources & Tool Activity")}</span>
          {sources.length > 0 && (
            <Badge variant="outline" size="sm" className="text-[10px] py-0 px-1 font-semibold text-blue-700 bg-blue-50/50">
              {sources.length} {t("documents.citationsTitle", "Citations")}
            </Badge>
          )}
          {toolActivity.length > 0 && (
            <span className="text-[10px] text-slate-400">
              ({toolActivity.length} {t("agent.sourcesTimeline.stepsUsed", "steps")})
            </span>
          )}
        </span>
        {isOpen ? (
          <ChevronUp className="w-3.5 h-3.5 text-slate-400" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
        )}
      </button>

      {isOpen && (
        <div className="mt-2.5 space-y-2.5 text-xs animate-fadeIn">
          {/* Intent & Verification Badge */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Intent:
            </span>
            <Badge variant="outline" size="sm" className="text-[10px] font-medium capitalize">
              {t(`agent.intent.${intent}`, intent || "Civic Query")}
            </Badge>
            {grounded === false && (
              <Badge variant="warning" size="sm" className="text-[10px]">
                Unverified Excerpts
              </Badge>
            )}
          </div>

          {/* Tool Execution Pipeline */}
          {toolActivity.length > 0 && (
            <div className="space-y-1.5">
              {toolActivity.map((act, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-2 p-2 rounded-lg bg-white/80 border border-slate-200 text-xs shadow-2xs"
                >
                  <span className="mt-0.5 flex-shrink-0">
                    {act.status === "success" ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : act.status === "rejected" || act.status === "skipped" ? (
                      <XCircle className="w-3.5 h-3.5 text-amber-500" />
                    ) : (
                      <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
                    )}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-semibold text-slate-800 text-[11px]">
                        {t(act.ui_label_key || `tools.${act.tool_name}`, act.tool_name)}
                      </span>
                      {act.duration_ms !== undefined && (
                        <span className="text-[10px] font-mono text-slate-400">
                          {act.duration_ms}ms
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-600 break-words mt-0.5">{act.summary}</p>
                    {act.tool_name === "compare_documents" && (
                      <button
                        type="button"
                        onClick={() => navigate("/compare")}
                        className="mt-1 inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        <span>Open Policy Comparison</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Numbered Verified Sources */}
          {sources.length > 0 && (
            <div className="space-y-1.5 pt-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                {t("documents.citationsTitle", "Verified Citations")}:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {sources.map((s, idx) => {
                  const isComparison = s.source_id?.startsWith("C");
                  const isOfficial = s.source_id?.startsWith("S") || s.collection === "official";
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => {
                        if (isComparison) {
                          if (s.comparison_id) {
                            navigate(`/compare?id=${s.comparison_id}`);
                          } else {
                            navigate("/compare");
                          }
                        } else if (isOfficial) {
                          navigate("/verify");
                        } else {
                          onInspectSource(s.document_id, s.page_number);
                        }
                      }}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-900 border border-blue-200 hover:bg-blue-100 hover:border-blue-400 transition-colors cursor-pointer text-left"
                      title={
                        isComparison
                          ? "Click to open full Policy Comparison"
                          : isOfficial
                          ? `Click to view Official Source Library (p. ${s.page_number})`
                          : `${t("documents.citationJumpTooltip", "Click to jump to Page")} ${s.page_number}`
                      }
                    >
                      <span className="font-bold text-blue-700 font-mono">[{s.source_id}]</span>
                      <span className="max-w-[160px] truncate">{s.document_name}</span>
                      {isComparison ? (
                        <span className="text-[10px] bg-indigo-100 text-indigo-900 px-1 rounded font-semibold">
                          {s.old_page_number ? `p.${s.old_page_number}` : ""}→{s.new_page_number ? `p.${s.new_page_number}` : ""}
                        </span>
                      ) : isOfficial ? (
                        <span className="text-[10px] bg-emerald-100 text-emerald-900 px-1 rounded font-semibold">
                          Official p.{s.page_number}
                        </span>
                      ) : (
                        <span className="text-[10px] bg-blue-200/80 text-blue-950 px-1 rounded font-semibold">
                          p. {s.page_number}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Warnings & Grounding Alert */}
          {(!grounded || (warnings && warnings.length > 0)) && (
            <div className="p-2 rounded-lg bg-amber-50/90 border border-amber-200 text-[11px] text-amber-900 flex items-start gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0 mt-0.5" />
              <span>{t("agent.sourcesTimeline.unverifiedAlert")}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function Assistant() {
  const { t, language: uiLanguage } = useLanguage();
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { documents } = useDocuments();

  const {
    conversations,
    activeId,
    messages,
    isLoading,
    language: chatLanguage,
    setLanguage: setChatLanguage,
    selectedDocumentIds,
    toggleDocumentId,
    setSelectedDocumentIds,
    sendMessage,
    submitApproval,
    retryLastMessage,
    stopGeneration,
    startNewChat,
    switchConversation,
    deleteChat,
    renameChat,
    unmigratedCount,
    isMigrating,
    migrateLocalConversations,
    dismissMigration,
  } = useChat(uiLanguage === "ta" ? "ta" : "auto");

  const [inputMessage, setInputMessage] = useState(
    () => searchParams.get("q") || location.state?.prompt || ""
  );
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [isDocPickerOpen, setIsDocPickerOpen] = useState(false);

  // Ready documents eligible for agent context
  const readyDocs = documents.filter(
    (d) => d.status === "ready" || d.status === "ready_with_warnings"
  );

  // Modal state for delete confirmation
  const [deleteModalState, setDeleteModalState] = useState({
    isOpen: false,
    convId: null,
  });

  // Rename inline state
  const [editingConvId, setEditingConvId] = useState(null);
  const [editTitleInput, setEditTitleInput] = useState("");

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // 1. Check for incoming prefill from Dashboard suggestion chip
  useEffect(() => {
    const prefilled = searchParams.get("q") || location.state?.prompt;
    if (prefilled && typeof prefilled === "string") {
      // oxlint-disable-next-line react/set-state-in-effect
      setInputMessage(prefilled);
      setSearchParams({}, { replace: true });
      navigate(location.pathname, { replace: true, state: {} });
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }
  }, [searchParams, location.state, location.pathname, setSearchParams, navigate]);

  // 2. Auto-scroll to bottom of messages when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // 3. Auto-grow Textarea height
  const handleInputChange = (e) => {
    const value = e.target.value;
    if (value.length <= 4000) {
      setInputMessage(value);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (!inputMessage.trim() || isLoading) return;
    sendMessage(inputMessage);
    setInputMessage("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleCopy = (id, text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    showToast({ message: t("assistant.copied"), type: "success", duration: 2500 });
    setTimeout(() => setCopiedId(null), 2500);
  };

  const handleInspectSource = (documentId, pageNumber) => {
    navigate("/documents", {
      state: {
        documentId,
        pageNumber,
      },
    });
  };

  const handleSamplePromptClick = (promptText) => {
    setInputMessage(promptText);
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  };

  const openDeleteModal = (id, e) => {
    e.stopPropagation();
    setDeleteModalState({ isOpen: true, convId: id });
  };

  const confirmDelete = () => {
    if (deleteModalState.convId) {
      deleteChat(deleteModalState.convId);
    }
    setDeleteModalState({ isOpen: false, convId: null });
  };

  const startRename = (conv, e) => {
    e.stopPropagation();
    setEditingConvId(conv.id);
    setEditTitleInput(conv.title);
  };

  const saveRename = (id) => {
    if (editTitleInput.trim()) {
      renameChat(id, editTitleInput.trim());
    }
    setEditingConvId(null);
  };

  const samplePrompts = [
    t("assistant.sample1"),
    t("assistant.sample2"),
    t("assistant.sample3"),
    t("assistant.sample4"),
  ];

  const charCount = inputMessage.length;
  const isNearLimit = charCount > 3500;

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
      {/* Top Chat Toolbar */}
      <div className="h-14 px-4 sm:px-6 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 cursor-pointer"
            title={sidebarOpen ? "Hide conversations" : "Show conversations"}
            aria-label="Toggle conversations sidebar"
          >
            {sidebarOpen ? (
              <PanelLeftClose className="w-5 h-5" />
            ) : (
              <PanelLeftOpen className="w-5 h-5" />
            )}
          </button>

          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-blue-900 text-white flex items-center justify-center shadow-xs">
              <Bot className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-900 leading-tight">
                {t("pages.assistant.title")}
              </h1>
              <span className="text-[10px] text-slate-500 font-medium hidden sm:inline-block">
                Gemini Central Agent • Function Calling • English & Tamil
              </span>
            </div>
          </div>
        </div>

        {/* Right Toolbar Actions */}
        <div className="flex items-center gap-2">
          {/* Language Preference Selector */}
          <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-0.5 text-xs shadow-2xs">
            <Languages className="w-3.5 h-3.5 text-slate-400 ml-1.5" />
            <select
              value={chatLanguage}
              onChange={(e) => setChatLanguage(e.target.value)}
              className="bg-transparent text-slate-700 text-xs py-1 px-1.5 rounded focus:outline-none cursor-pointer font-medium"
              aria-label="Assistant response language"
            >
              <option value="auto">{t("assistant.langAuto")}</option>
              <option value="en">{t("assistant.langEn")}</option>
              <option value="ta">{t("assistant.langTa")}</option>
            </select>
          </div>

          {/* New Chat Button */}
          <Button
            variant="secondary"
            size="sm"
            onClick={startNewChat}
            icon={Plus}
            className="h-8 text-xs font-semibold shadow-2xs"
          >
            <span className="hidden sm:inline">{t("assistant.newChat")}</span>
          </Button>
        </div>
      </div>

      {/* Main Chat Body: Sidebar + Messages Viewport */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Conversations Sidebar Drawer */}
        <aside
          className={`
            absolute sm:relative z-20 inset-y-0 left-0 w-64 bg-slate-50 border-r border-slate-200
            transform transition-transform duration-200 ease-in-out flex flex-col
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full sm:hidden"}
          `}
        >
          <div className="p-3 border-b border-slate-200 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              {t("assistant.conversations")}
            </span>
            <button
              type="button"
              onClick={() => setSidebarOpen(false)}
              className="p-1 rounded text-slate-400 hover:text-slate-600 sm:hidden"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversations.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-400">
                {t("assistant.noConversations")}
              </div>
            ) : (
              conversations.map((conv) => {
                const isActive = conv.id === activeId;
                const isEditing = conv.id === editingConvId;

                return (
                  <div
                    key={conv.id}
                    onClick={() => !isEditing && switchConversation(conv.id)}
                    className={`group flex items-center justify-between p-2 rounded-xl text-xs cursor-pointer transition-colors ${
                      isActive
                        ? "bg-blue-100/70 text-blue-900 font-semibold"
                        : "text-slate-700 hover:bg-slate-200/50"
                    }`}
                  >
                    {isEditing ? (
                      <input
                        type="text"
                        value={editTitleInput}
                        onChange={(e) => setEditTitleInput(e.target.value)}
                        onBlur={() => saveRename(conv.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveRename(conv.id);
                          if (e.key === "Escape") setEditingConvId(null);
                        }}
                        autoFocus
                        className="w-full bg-white px-2 py-0.5 rounded border border-blue-400 text-xs focus:outline-none"
                      />
                    ) : (
                      <>
                        <div className="flex items-center gap-2 truncate pr-1">
                          <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-slate-400 group-hover:text-blue-600" />
                          <span className="truncate">{conv.title}</span>
                        </div>

                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            type="button"
                            onClick={(e) => startRename(conv, e)}
                            className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-200/50"
                            title={t("assistant.renameConversation")}
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => openDeleteModal(conv.id, e)}
                            className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                            title={t("assistant.deleteConversation")}
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </aside>

        {/* Mobile backdrop when sidebar is open */}
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-10 bg-slate-900/20 sm:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        {/* Chat Messages Viewport */}
        <div className="flex-1 flex flex-col min-w-0 bg-white">
          {/* LocalStorage Migration Banner */}
          {unmigratedCount > 0 && (
            <div className="mx-4 mt-3 p-3 bg-blue-50 border border-blue-200 rounded-xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-blue-900 shadow-2xs">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <div>
                  <p className="font-semibold text-blue-950">
                    {t("assistant.migration.bannerTitle", "Local Chat History Detected")}
                  </p>
                  <p className="text-[11px] text-blue-700">
                    {t(
                      "assistant.migration.bannerDesc",
                      `You have ${unmigratedCount} conversation(s) stored in your browser cache. Migrate them to the SQLite database to keep them safely persisted and synced across browser sessions.`
                    ).replace("{count}", unmigratedCount)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 self-end sm:self-auto flex-shrink-0">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={async () => {
                    try {
                      const count = await migrateLocalConversations();
                      showToast({
                        title: t("assistant.migration.bannerTitle", "Migration Complete"),
                        message: t(
                          "assistant.migration.migrationSuccess",
                          `Successfully migrated ${count} conversation(s) to the database!`
                        ).replace("{count}", count),
                        variant: "success",
                      });
                    } catch (err) {
                      showToast({
                        title: "Migration Failed",
                        message: err?.message || "Could not migrate conversations.",
                        variant: "error",
                      });
                    }
                  }}
                  disabled={isMigrating}
                  className="h-7 text-xs bg-blue-700 hover:bg-blue-800"
                >
                  {isMigrating
                    ? t("assistant.migration.migrating", "Migrating...")
                    : t("assistant.migration.migrateBtn", "Migrate to Database")}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={dismissMigration}
                  disabled={isMigrating}
                  className="h-7 text-xs text-slate-500 hover:text-slate-800"
                >
                  {t("assistant.migration.dismissBtn", "Dismiss")}
                </Button>
              </div>
            </div>
          )}

          <div
            className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6"
            aria-live="polite"
            role="log"
          >
            {messages.length === 0 ? (
              /* Welcoming Empty State */
              <div className="max-w-2xl mx-auto py-8 sm:py-12 space-y-8 animate-fadeIn">
                <div className="text-center space-y-3">
                  <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-900 to-blue-700 text-white flex items-center justify-center mx-auto shadow-md">
                    <Sparkles className="w-6 h-6 text-blue-200" />
                  </div>
                  <h2 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight">
                    {t("assistant.emptyTitle")}
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed max-w-lg mx-auto">
                    {t("assistant.emptySubtitle")}
                  </p>
                </div>

                {/* Honest Prototype Limitation Alert */}
                <Alert variant="info" title="CivicLens Prototype Guidance">
                  <p className="text-xs text-blue-900 leading-relaxed">
                    {t("assistant.limitationsNotice")}
                  </p>
                </Alert>

                {/* Sample Prompt Pills */}
                <div className="space-y-3">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block text-center">
                    {t("assistant.samplePromptsTitle")}
                  </span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {samplePrompts.map((prompt, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSamplePromptClick(prompt)}
                        className="text-left p-3 rounded-xl border border-slate-200 bg-slate-50/70 hover:bg-blue-50/60 hover:border-blue-300 transition-all text-xs text-slate-700 font-medium group cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 flex items-start gap-2.5"
                      >
                        <MessageSquare className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0 group-hover:scale-105 transition-transform" />
                        <span className="leading-snug">{prompt}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* Messages Thread */
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${
                    msg.role === "user" ? "items-end" : "items-start"
                  }`}
                >
                  <div
                    className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-2xs ${
                      msg.role === "user"
                        ? "bg-blue-900 text-white rounded-br-xs"
                        : msg.error
                        ? "bg-rose-50 border border-rose-200 text-rose-950 rounded-bl-xs"
                        : "bg-slate-50 border border-slate-200 text-slate-900 rounded-bl-xs"
                    }`}
                  >
                    {/* Assistant Header Avatar and Meta */}
                    {msg.role === "assistant" && (
                      <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200/60 text-xs">
                        <div className="flex items-center gap-1.5 font-semibold text-blue-950">
                          <Bot className="w-3.5 h-3.5 text-blue-700" />
                          <span>CivicLens</span>
                          {msg.languageUsed && (
                            <Badge variant="outline" size="sm" className="ml-1 uppercase text-[9px]">
                              {msg.languageUsed}
                            </Badge>
                          )}
                        </div>
                        {msg.latencyMs && (
                          <span className="text-[10px] text-slate-400 font-mono">
                            {msg.latencyMs}ms
                          </span>
                        )}
                      </div>
                    )}

                    {/* Content Body (Rendered as safe Markdown for assistant) */}
                    {msg.role === "assistant" && !msg.error ? (
                      <div className="prose prose-xs sm:prose-sm max-w-none text-slate-800 leading-relaxed break-words">
                        <ReactMarkdown
                          components={{
                            a: ({ ...props }) => (
                              <a
                                {...props}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-700 underline font-medium hover:text-blue-900"
                              />
                            ),
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                    )}

                    {/* Pending Citizen Authorization Card */}
                    {msg.pendingApproval && (
                      <div className="mt-3 p-3.5 rounded-xl border border-amber-300 bg-amber-50/90 text-amber-950 shadow-2xs">
                        <div className="flex items-start gap-2.5">
                          <ShieldAlert className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
                          <div className="flex-1 space-y-2">
                            <div>
                              <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wide">
                                {t("agent.approval.title")}
                              </h4>
                              <p className="text-xs text-amber-800 mt-0.5 leading-relaxed">
                                {msg.pendingApproval.description}
                              </p>
                            </div>
                            <div className="p-2 rounded-lg bg-white/80 border border-amber-200 text-[11px] font-mono text-amber-900 space-y-1">
                              <div>
                                <span className="font-semibold text-slate-600">{t("agent.approval.toolName")}:</span> {msg.pendingApproval.tool_name}
                              </div>
                              {msg.pendingApproval.args && Object.keys(msg.pendingApproval.args).length > 0 && (
                                <div>
                                  <span className="font-semibold text-slate-600">{t("agent.approval.parameters")}:</span>{" "}
                                  <span className="break-all">{JSON.stringify(msg.pendingApproval.args)}</span>
                                </div>
                              )}
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                              <Button
                                variant="primary"
                                size="sm"
                                onClick={() => submitApproval(msg.id, msg.pendingApproval.approval_id, "approve")}
                                disabled={isLoading}
                                className="h-7 text-xs bg-emerald-700 hover:bg-emerald-800 border-emerald-800"
                              >
                                {t("agent.approval.approveBtn")}
                              </Button>
                              <Button
                                variant="secondary"
                                size="sm"
                                onClick={() => submitApproval(msg.id, msg.pendingApproval.approval_id, "deny")}
                                disabled={isLoading}
                                className="h-7 text-xs text-rose-700 hover:bg-rose-50 border-rose-300"
                              >
                                {t("agent.approval.denyBtn")}
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Collapsible Sources & Tool Activity Timeline */}
                    {msg.role === "assistant" && !msg.error && (
                      <MessageActivityTimeline
                        toolActivity={msg.toolActivity}
                        sources={msg.sources}
                        intent={msg.intent}
                        grounded={msg.grounded}
                        warnings={msg.warnings}
                        verifications={msg.verifications}
                        checklists={msg.checklists}
                        grievances={msg.grievances}
                        browserSessions={msg.browserSessions || []}
                        onInspectSource={handleInspectSource}
                        t={t}
                      />
                    )}

                    {/* Assistant Message Actions & Meta */}
                    {msg.role === "assistant" && !msg.error && (
                      <div className="flex items-center justify-between pt-2 mt-2 border-t border-slate-200/50 text-[11px] text-slate-400">
                        <span className="text-[10px]">
                          {new Date(msg.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopy(msg.id, msg.content)}
                          className="hover:text-blue-700 transition-colors inline-flex items-center gap-1 text-[11px] font-medium cursor-pointer"
                          title={t("assistant.copy")}
                        >
                          {copiedId === msg.id ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-600" />
                              <span className="text-emerald-700">{t("assistant.copied")}</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>{t("assistant.copy")}</span>
                            </>
                          )}
                        </button>
                      </div>
                    )}

                    {/* Retry Button on Error Turn */}
                    {msg.error && (
                      <div className="pt-2 mt-2 border-t border-rose-200 flex items-center justify-between">
                        <span className="text-xs text-rose-700 flex items-center gap-1">
                          <AlertTriangle className="w-3 h-3" />
                          <span>{t("assistant.errorPrefix")}</span>
                        </span>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={retryLastMessage}
                          icon={RotateCcw}
                          className="h-7 text-xs"
                        >
                          {t("assistant.retry")}
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {/* In-Flight Typing Indicator */}
            {isLoading && (
              <div className="flex items-start gap-2 animate-fadeIn">
                <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-800 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 animate-bounce" />
                </div>
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-2xl rounded-bl-xs text-xs text-slate-500 flex items-center gap-2">
                  <span className="inline-flex gap-1.5 items-center">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping" />
                    <span className="font-medium text-slate-700">{t("agent.statusAnalyzing")}</span>
                  </span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input Dock Area */}
          <div className="p-3 sm:p-4 bg-slate-50/70 border-t border-slate-200">
            <div className="max-w-4xl mx-auto space-y-2">
              {/* Selected Documents Context Chip Row */}
              {selectedDocumentIds.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pb-1">
                  <span className="text-xs text-slate-500 font-medium flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5 text-blue-700" />
                    <span>{t("agent.documentPicker.title")}:</span>
                  </span>
                  {selectedDocumentIds.map((docId) => {
                    const doc = documents.find((d) => d.document_id === docId);
                    const name = doc?.filename || docId.slice(0, 8);
                    return (
                      <span
                        key={docId}
                        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs bg-blue-50 border border-blue-200 text-blue-900 font-medium shadow-2xs"
                      >
                        <span className="max-w-[140px] truncate">{name}</span>
                        <button
                          type="button"
                          onClick={() => toggleDocumentId(docId)}
                          className="text-blue-500 hover:text-blue-800 cursor-pointer ml-0.5 text-sm leading-none"
                          title="Remove document context"
                        >
                          ×
                        </button>
                      </span>
                    );
                  })}
                  <button
                    type="button"
                    onClick={() => setSelectedDocumentIds([])}
                    className="text-[11px] text-slate-400 hover:text-slate-600 underline ml-1 cursor-pointer"
                  >
                    {t("agent.documentPicker.clearAll")}
                  </button>
                </div>
              )}

              <div className="relative bg-white rounded-xl border border-slate-300 focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-600/20 shadow-2xs transition-all">
                <textarea
                  ref={textareaRef}
                  value={inputMessage}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  placeholder={t("assistant.inputPlaceholder")}
                  disabled={isLoading}
                  className="w-full pl-3 pr-24 py-2.5 text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 bg-transparent resize-none focus:outline-none min-h-[42px] max-h-[160px]"
                />

                <div className="absolute right-2 bottom-2 flex items-center gap-1.5">
                  {/* Attach Button (Opens Document Picker Modal) */}
                  <button
                    type="button"
                    onClick={() => setIsDocPickerOpen(true)}
                    className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                      selectedDocumentIds.length > 0
                        ? "text-blue-700 bg-blue-50 hover:bg-blue-100"
                        : "text-slate-400 hover:text-blue-600 hover:bg-slate-100"
                    }`}
                    title={t("agent.documentPicker.buttonLabel")}
                    aria-label={t("agent.documentPicker.buttonLabel")}
                  >
                    <Paperclip className="w-4 h-4" />
                  </button>

                  {/* Send or Stop Button */}
                  {isLoading ? (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={stopGeneration}
                      icon={Square}
                      className="h-8 w-8 p-0 rounded-lg flex items-center justify-center"
                      title={t("assistant.stop")}
                      aria-label={t("assistant.stop")}
                    />
                  ) : (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleSubmit}
                      disabled={!inputMessage.trim()}
                      icon={Send}
                      className="h-8 w-8 p-0 rounded-lg flex items-center justify-center"
                      title={t("assistant.send")}
                      aria-label={t("assistant.send")}
                    />
                  )}
                </div>
              </div>

              {/* Input Meta Footer */}
              <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
                <span className="flex items-center gap-1">
                  <Info className="w-3 h-3 text-slate-400" />
                  <span>CivicLens verifies official procedures; never fabricates legal details.</span>
                </span>
                <span className={isNearLimit ? "text-amber-600 font-semibold" : ""}>
                  {charCount}/4000 {t("assistant.charsRemaining")}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Document Picker Modal */}
      <Modal
        isOpen={isDocPickerOpen}
        onClose={() => setIsDocPickerOpen(false)}
        title={t("agent.documentPicker.title")}
        confirmText={t("agent.documentPicker.apply")}
        onConfirm={() => setIsDocPickerOpen(false)}
        cancelText={t("common.cancel")}
      >
        <div className="space-y-3">
          <p className="text-xs text-slate-600 leading-relaxed">
            {t("agent.documentPicker.subtitle")}
          </p>

          <div className="max-h-60 overflow-y-auto space-y-2 py-1">
            {readyDocs.length === 0 ? (
              <div className="p-4 text-center text-xs text-slate-500 bg-slate-50 rounded-xl border border-slate-200">
                <p>{t("agent.documentPicker.noDocuments")}</p>
                <Link
                  to="/documents"
                  className="inline-block mt-2 text-blue-700 font-semibold hover:underline"
                  onClick={() => setIsDocPickerOpen(false)}
                >
                  Go to Document Intelligence →
                </Link>
              </div>
            ) : (
              readyDocs.map((doc) => {
                const isSelected = selectedDocumentIds.includes(doc.document_id);
                const isMax = selectedDocumentIds.length >= 5 && !isSelected;

                return (
                  <div
                    key={doc.document_id}
                    onClick={() => !isMax && toggleDocumentId(doc.document_id)}
                    className={`flex items-center justify-between p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                      isSelected
                        ? "bg-blue-50/80 border-blue-400 text-blue-950 font-medium"
                        : isMax
                        ? "bg-slate-50/50 border-slate-200 text-slate-400 cursor-not-allowed opacity-60"
                        : "bg-white border-slate-200 text-slate-800 hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                      <div
                        className={`w-4 h-4 rounded border flex items-center justify-center text-[10px] ${
                          isSelected
                            ? "bg-blue-700 border-blue-700 text-white font-bold"
                            : "border-slate-300 bg-white"
                        }`}
                      >
                        {isSelected && "✓"}
                      </div>
                      <div className="truncate">
                        <div className="font-semibold truncate">{doc.filename}</div>
                        <div className="text-[10px] text-slate-500">
                          {doc.page_count} pages • {doc.language.toUpperCase()}
                        </div>
                      </div>
                    </div>
                    {isSelected && (
                      <Badge variant="success" size="sm" className="text-[10px]">
                        Attached
                      </Badge>
                    )}
                  </div>
                );
              })
            )}
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
            <span>
              {selectedDocumentIds.length}/5 {t("agent.documentPicker.selectedCount")}
            </span>
            {selectedDocumentIds.length > 0 && (
              <button
                type="button"
                onClick={() => setSelectedDocumentIds([])}
                className="text-xs text-rose-600 hover:underline cursor-pointer"
              >
                {t("agent.documentPicker.clearAll")}
              </button>
            )}
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModalState.isOpen}
        onClose={() => setDeleteModalState({ isOpen: false, convId: null })}
        title={t("assistant.deleteConversation")}
        onConfirm={confirmDelete}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        confirmVariant="danger"
      >
        <p className="text-sm text-slate-600">
          {t("assistant.deleteConfirm")}
        </p>
      </Modal>
    </div>
  );
}
