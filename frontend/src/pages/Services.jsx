import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Compass,
  ExternalLink,
  Shield,
  Copy,
  Printer,
  RotateCcw,
  Sparkles,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Building2,
  Search,
  FileText,
  Lock,
  ArrowLeft,
  ListChecks,
  CheckCircle2,
  Play,
  ArrowRight,
  Eye,
  FileCheck,
  Clock,
  ShieldAlert,
} from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Alert } from "../components/ui/Alert";
import { Card } from "../components/ui/Card";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { useLanguage } from "../hooks/useLanguage";
import { useToast } from "../hooks/useToast";
import { useDocuments } from "../hooks/useDocuments";
import { useServiceGuide } from "../hooks/useServiceGuide";
import { useChecklistProgress } from "../hooks/useChecklistProgress";
import { useBrowserSession } from "../hooks/useBrowserSession";
import { servicesService } from "../services/servicesService";
import { portalsService } from "../services/portalsService";
import { browserService } from "../services/browserService";

export function Services() {
  const { t, language } = useLanguage();
  const { addToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Active Tab
  const [activeTab, setActiveTab] = useState(() => searchParams.get("tab") || "guidance");

  // Sync tab with URL
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    const newParams = new URLSearchParams(searchParams);
    newParams.set("tab", tab);
    setSearchParams(newParams);
  };

  // ----------------------------------------------------
  // TAB 1: Public Service Guidance & Checklist State
  // ----------------------------------------------------
  const guideIdParam = searchParams.get("guide_id");
  const {
    guide,
    pastGuides,
    isGenerating,
    error: guideError,
    piiError,
    generateGuide,
    fetchGuide,
    clearActiveGuide,
  } = useServiceGuide(guideIdParam);

  const [queryInput, setQueryInput] = useState("");
  const [applicantType, setApplicantType] = useState("unspecified");
  const [applicantSituation, setApplicantSituation] = useState("");
  const [sourceScope, setSourceScope] = useState("all");
  const [showHistory, setShowHistory] = useState(false);
  const [expandedQuotes, setExpandedQuotes] = useState({});

  // Checklist Progress Hook
  const {
    checkedIds,
    isChecked,
    toggleItem,
    resetProgress,
    checkedCount,
    progressPct,
  } = useChecklistProgress(guide?.id, guide?.checklist_items?.length || 0);

  // Group checklist items by category
  const groupedChecklist = useMemo(() => {
    if (!guide?.checklist_items) return {};
    const groups = {
      documents: [],
      information: [],
      steps: [],
      fees_and_timelines: [],
      to_verify: [],
    };
    for (const item of guide.checklist_items) {
      if (groups[item.category]) {
        groups[item.category].push(item);
      } else {
        groups.to_verify.push(item);
      }
    }
    return groups;
  }, [guide]);

  // Handle Guide Submission
  const handleSubmitGuide = async (e, forceGeneral = false) => {
    if (e) e.preventDefault();
    const query = queryInput.trim();
    if (!query) return;

    const res = await generateGuide({
      query,
      applicantType,
      applicantSituation: applicantSituation.trim() || null,
      language: language === "ta" ? "ta" : "auto",
      allowGeneral: forceGeneral,
      sourceScope,
    });

    if (res?.id) {
      const newParams = new URLSearchParams(searchParams);
      newParams.set("guide_id", res.id);
      setSearchParams(newParams);
    }
  };

  // Copy checklist as formatted markdown
  const handleCopyChecklist = () => {
    if (!guide?.checklist_items) return;
    const lines = [
      `# Application Checklist: ${guide.query}`,
      `Procedure Overview:\n${guide.procedure_overview}\n`,
      `Progress: ${checkedCount}/${guide.checklist_items.length} completed (${progressPct}%)\n`,
    ];

    const categoryNames = {
      documents: "Required Documents",
      information: "Information to Prepare",
      steps: "Step-by-Step Procedure",
      fees_and_timelines: "Fees & Timelines",
      to_verify: "Points to Verify",
    };

    Object.entries(groupedChecklist).forEach(([catKey, items]) => {
      if (items.length === 0) return;
      lines.push(`\n## ${categoryNames[catKey] || catKey}`);
      items.forEach((item) => {
        const mark = checkedIds.has(item.id) ? "[x]" : "[ ]";
        const statusTag =
          item.status === "source_confirmed"
            ? `(Source-Confirmed: ${item.source_label || "Gazette"})`
            : item.status === "needs_check"
            ? "(Needs Check on Portal)"
            : "(General Guidance)";
        lines.push(`- ${mark} **${item.title}**: ${item.description} ${statusTag}`);
      });
    });

    if (guide.key_facts?.length > 0) {
      lines.push("\n## Authoritative Key Facts");
      guide.key_facts.forEach((kf) => {
        lines.push(`- **${kf.fact_type.toUpperCase()}**: ${kf.value_text} (${kf.source_label || "Verified"})`);
      });
    }

    lines.push("\n---\nGenerated by CivicLens Public Service Assistant (Understand. Verify. Act.)");

    navigator.clipboard.writeText(lines.join("\n"));
    addToast(t("services.guidanceTab.copiedToast", "Checklist copied to clipboard!"), "success");
  };

  // Example pills for fast exploration
  const exampleQueries = [
    { label: "Income Certificate (வருமான சான்றிதழ்)", q: "How do I apply for an income certificate in Tamil Nadu?" },
    { label: "Community Certificate (சாதி சான்றிதழ்)", q: "What is the procedure for community certificate application?" },
    { label: "Solar Pump Subsidy (சூரிய பம்ப் மானியம்)", q: "How to apply for solar pump subsidy for farmers?" },
    { label: "Old Age Pension (முதியோர் உதவித்தொகை)", q: "Old age pension eligibility and application steps" },
  ];

  // ----------------------------------------------------
  // TAB 2: Form Field Explainer State
  // ----------------------------------------------------
  const { documents } = useDocuments();
  const [formSourceMode, setFormSourceMode] = useState("paste"); // "paste" or "document"
  const [rawFormText, setRawFormText] = useState("");
  const [selectedFormDocId, setSelectedFormDocId] = useState("");
  const [detectedFields, setDetectedFields] = useState([]);
  const [selectedFieldIds, setSelectedFieldIds] = useState(new Set());
  const [isExtractingFields, setIsExtractingFields] = useState(false);
  const [isExplainingFields, setIsExplainingFields] = useState(false);
  const [formExplanations, setFormExplanations] = useState([]);
  const [formError, setFormError] = useState(null);

  // Extract Form Fields
  const handleExtractFields = async () => {
    setIsExtractingFields(true);
    setFormError(null);
    setFormExplanations([]);
    try {
      const payload = {};
      if (formSourceMode === "paste") {
        if (!rawFormText.trim()) throw new Error("Please paste some form text or instructions first.");
        payload.rawText = rawFormText;
      } else {
        if (!selectedFormDocId) throw new Error("Please select an uploaded document.");
        payload.documentId = selectedFormDocId;
      }

      const res = await servicesService.extractFormFields(payload);
      setDetectedFields(res.fields || []);
      // Default select all detected fields
      setSelectedFieldIds(new Set((res.fields || []).map((f) => f.id)));
    } catch (err) {
      setFormError(err?.message || "Failed to extract form fields.");
    } finally {
      setIsExtractingFields(false);
    }
  };

  // Explain Selected Fields
  const handleExplainFields = async () => {
    const fieldsToExplain = detectedFields.filter((f) => selectedFieldIds.has(f.id));
    if (fieldsToExplain.length === 0) return;

    setIsExplainingFields(true);
    setFormError(null);
    try {
      const res = await servicesService.explainFormFields({
        fields: fieldsToExplain,
        documentId: formSourceMode === "document" ? selectedFormDocId : null,
        contextText: formSourceMode === "paste" ? rawFormText : null,
        language: language === "ta" ? "ta" : "en",
      });
      setFormExplanations(res.explanations || []);
    } catch (err) {
      setFormError(err?.message || "Failed to explain form fields.");
    } finally {
      setIsExplainingFields(false);
    }
  };

  // ----------------------------------------------------
  // TAB 3: Official Portals State
  // ----------------------------------------------------
  const [portalsList, setPortalsList] = useState([]);
  const [portalsLoading, setPortalsLoading] = useState(false);
  const [portalSearch, setPortalSearch] = useState("");
  const [scopeFilter, setScopeFilter] = useState("all");
  const [serviceTypeFilter, setServiceTypeFilter] = useState("all");

  const loadPortals = useCallback(async () => {
    setPortalsLoading(true);
    try {
      const res = await portalsService.listPortals({ status: "active" });
      setPortalsList(res.portals || []);
    } catch {
      // Non-critical
    } finally {
      setPortalsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "portals") {
      loadPortals();
    }
  }, [activeTab, loadPortals]);

  // Filtered portals
  const filteredPortals = useMemo(() => {
    const q = portalSearch.toLowerCase().trim();
    return portalsList.filter((p) => {
      if (scopeFilter !== "all" && p.scope !== scopeFilter) return false;
      if (serviceTypeFilter !== "all" && !p.service_types?.includes(serviceTypeFilter)) return false;
      if (!q) return true;
      const haystack = `${p.name} ${p.name_ta || ""} ${p.description} ${p.department} ${p.keywords?.join(" ") || ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [portalsList, portalSearch, scopeFilter, serviceTypeFilter]);

  // ----------------------------------------------------
  // TAB 4: Controlled Browser Demo Workflow State
  // ----------------------------------------------------
  const {
    session: browserSession,
    manifest: demoManifest,
    pastSessions: pastDemoSessions,
    preview: demoPreview,
    submissionResult: demoResult,
    isActing: isDemoActing,
    error: demoError,
    piiError: demoPiiError,
    startSession: startDemoSession,
    fillStep: fillDemoStep,
    nextStep: nextDemoStep,
    prevStep: prevDemoStep,
    loadPreview: loadDemoPreview,
    submitDemo: submitDemoWorkflow,
    closeSession: closeDemoSession,
    resetSession: resetDemoWorkflow,
  } = useBrowserSession();

  const [activeStepValues, setActiveStepValues] = useState({});
  const [fictionalAcknowledged, setFictionalAcknowledged] = useState(false);
  const [selectedScreenshotUrl, setSelectedScreenshotUrl] = useState(null);

  // Sync step values when session step changes or session starts
  useEffect(() => {
    if (browserSession && demoManifest) {
      const stepIdx = browserSession.current_step;
      const stepDef = demoManifest.steps?.find((s) => s.step_index === stepIdx);
      if (stepDef) {
        const initial = {};
        stepDef.fields.forEach((f) => {
          initial[f.name] = browserSession.filled_values?.[f.name] ?? f.sample_value ?? "";
        });
        // oxlint-disable-next-line react/set-state-in-effect
        setActiveStepValues(initial);
      }
      if (stepIdx === 5 && !demoPreview) {
        loadDemoPreview();
      }
    }
  }, [browserSession, demoManifest, demoPreview, loadDemoPreview]);

  // Handle filling sample fictional data for current step
  const handleFillStepSample = () => {
    if (!demoManifest || !browserSession) return;
    const stepIdx = browserSession.current_step;
    const stepDef = demoManifest.steps?.find((s) => s.step_index === stepIdx);
    if (!stepDef) return;
    const sample = {};
    stepDef.fields.forEach((f) => {
      sample[f.name] = demoManifest.fictional_sample_values?.[f.name] ?? f.sample_value ?? "";
    });
    setActiveStepValues(sample);
  };

  const handleFieldChange = (name, value) => {
    setActiveStepValues((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleContinueStep = async () => {
    if (!browserSession) return;
    const curStep = browserSession.current_step;
    const updated = await fillDemoStep(curStep, activeStepValues, true);
    if (updated) {
      await nextDemoStep();
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Page Header */}
      <PageHeader
        title={t("services.title", "Public Service Assistant")}
        description={t(
          "services.subtitle",
          "Understand government application procedures, generate interactive checklists, and inspect form fields with verified official guidance."
        )}
        badge={<Badge variant="primary">Module 4 • Phase 12 Active</Badge>}
      />

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 overflow-x-auto gap-2">
        <button
          type="button"
          onClick={() => handleTabChange("guidance")}
          className={`py-3 px-4 text-sm font-medium border-b-2 whitespace-nowrap flex items-center gap-2 cursor-pointer transition-colors ${
            activeTab === "guidance"
              ? "border-blue-600 text-blue-700 font-semibold"
              : "border-transparent text-slate-600 hover:text-slate-900"
          }`}
        >
          <ListChecks className="w-4 h-4" />
          <span>{t("services.tabs.guidance", "Guidance & Checklist")}</span>
        </button>

        <button
          type="button"
          onClick={() => handleTabChange("formExplainer")}
          className={`py-3 px-4 text-sm font-medium border-b-2 whitespace-nowrap flex items-center gap-2 cursor-pointer transition-colors ${
            activeTab === "formExplainer"
              ? "border-blue-600 text-blue-700 font-semibold"
              : "border-transparent text-slate-600 hover:text-slate-900"
          }`}
        >
          <FileText className="w-4 h-4" />
          <span>{t("services.tabs.formExplainer", "Explain Form Fields")}</span>
        </button>

        <button
          type="button"
          onClick={() => handleTabChange("portals")}
          className={`py-3 px-4 text-sm font-medium border-b-2 whitespace-nowrap flex items-center gap-2 cursor-pointer transition-colors ${
            activeTab === "portals"
              ? "border-blue-600 text-blue-700 font-semibold"
              : "border-transparent text-slate-600 hover:text-slate-900"
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>{t("services.tabs.portals", "Official Portals")}</span>
        </button>

        <button
          type="button"
          onClick={() => handleTabChange("demo")}
          className={`py-3 px-4 text-sm font-medium border-b-2 whitespace-nowrap flex items-center gap-2 cursor-pointer transition-colors ${
            activeTab === "demo"
              ? "border-blue-600 text-blue-700 font-semibold"
              : "border-transparent text-slate-600 hover:text-slate-900"
          }`}
        >
          <Compass className="w-4 h-4" />
          <span>{t("services.tabs.demo", "Demo Workflow")}</span>
          <Badge variant="primary" size="sm" className="text-[10px]">
            Playwright Simulation
          </Badge>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: GUIDANCE & CHECKLIST                                               */}
      {/* ========================================================================= */}
      {activeTab === "guidance" && (
        <div className="space-y-6">
          {/* Active Guide View */}
          {guide ? (
            <div className="space-y-6">
              {/* Top Action Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    clearActiveGuide();
                    const newParams = new URLSearchParams(searchParams);
                    newParams.delete("guide_id");
                    setSearchParams(newParams);
                  }}
                  className="self-start flex items-center gap-1.5"
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>{t("services.guidanceTab.backToList", "Back to Guidance Form")}</span>
                </Button>

                <div className="flex items-center gap-2 flex-wrap">
                  {guide.mode !== "no_sources" && (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleCopyChecklist}
                        className="flex items-center gap-1.5"
                      >
                        <Copy className="w-4 h-4" />
                        <span>{t("services.guidanceTab.copyChecklist", "Copy Checklist")}</span>
                      </Button>

                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => window.print()}
                        className="flex items-center gap-1.5"
                      >
                        <Printer className="w-4 h-4" />
                        <span>{t("services.guidanceTab.printChecklist", "Print Checklist")}</span>
                      </Button>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={resetProgress}
                        className="text-slate-500 hover:text-rose-600 flex items-center gap-1"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                        <span>{t("services.guidanceTab.resetChecklist", "Reset Progress")}</span>
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {/* Guide Header Banner */}
              <Card className="p-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge
                        variant={
                          guide.mode === "source_grounded"
                            ? "supported"
                            : guide.mode === "no_sources"
                            ? "unverified"
                            : "mixed"
                        }
                        size="md"
                      >
                        {guide.mode === "source_grounded"
                          ? "OFFICIAL SOURCE GROUNDED"
                          : guide.mode === "no_sources"
                          ? "NO OFFICIAL SOURCES"
                          : "GENERAL GUIDANCE"}
                      </Badge>
                      {guide.applicant_type !== "unspecified" && (
                        <Badge variant="outline" size="sm" className="capitalize">
                          {t(`services.applicantTypes.${guide.applicant_type}`, guide.applicant_type)}
                        </Badge>
                      )}
                    </div>
                    <h2 className="text-xl font-bold text-slate-900 pt-1">{guide.query}</h2>
                  </div>

                  {guide.checklist_items?.length > 0 && (
                    <div className="bg-blue-50/70 border border-blue-200 rounded-lg p-3 min-w-[220px]">
                      <div className="flex justify-between text-xs font-semibold text-blue-900 mb-1.5">
                        <span>Checklist Completion</span>
                        <span>{progressPct}%</span>
                      </div>
                      <div className="w-full bg-blue-200 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>
                      <span className="text-[11px] text-blue-700 mt-1 block text-right font-medium">
                        {checkedCount} / {guide.checklist_items.length} completed
                      </span>
                    </div>
                  )}
                </div>

                {/* Procedure Overview */}
                <div className="pt-4 space-y-2">
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider text-slate-500">
                    {t("services.guidanceTab.overviewTitle", "Procedure Overview")}
                  </h3>
                  <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-line bg-slate-50 p-4 rounded-lg border border-slate-200/80">
                    {language === "ta" && guide.procedure_overview_ta
                      ? guide.procedure_overview_ta
                      : guide.procedure_overview}
                  </p>
                </div>
              </Card>

              {/* No Sources Guardrail Alert */}
              {guide.mode === "no_sources" && (
                <Card className="p-6 border-amber-200 bg-amber-50/50 space-y-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-amber-950">
                        {t("services.guidanceTab.noSourcesTitle", "No Official Sources Found in Library")}
                      </h3>
                      <p className="text-sm text-amber-900 leading-relaxed">
                        {t(
                          "services.guidanceTab.noSourcesDesc",
                          "No official gazettes or policy orders match this query in the library. You can review the official portal directory or request general administrative guidance."
                        )}
                      </p>
                    </div>
                  </div>

                  {guide.offer_general_guidance && (
                    <div className="pt-2">
                      <Button
                        variant="primary"
                        onClick={() => handleSubmitGuide(null, true)}
                        isLoading={isGenerating}
                        className="flex items-center gap-2"
                      >
                        <Sparkles className="w-4 h-4" />
                        <span>
                          {t("services.guidanceTab.requestGeneralBtn", "Generate General Guidance")}
                        </span>
                      </Button>
                    </div>
                  )}
                </Card>
              )}

              {/* Interactive Categorized Checklist */}
              {guide.checklist_items?.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                      <ListChecks className="w-5 h-5 text-blue-600" />
                      <span>{t("services.guidanceTab.checklistTitle", "Interactive Application Checklist")}</span>
                    </h3>
                    <span className="text-xs text-slate-500 font-medium hidden sm:inline">
                      {t("services.guidanceTab.privacyNotice", "Progress saved in your browser.")}
                    </span>
                  </div>

                  {Object.entries(groupedChecklist).map(([catKey, items]) => {
                    if (items.length === 0) return null;
                    return (
                      <Card key={catKey} className="overflow-hidden">
                        <div className="bg-slate-100/70 px-4 py-2.5 border-b border-slate-200 flex items-center justify-between">
                          <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                            {t(`services.categories.${catKey}`, catKey)} ({items.length})
                          </span>
                        </div>
                        <div className="divide-y divide-slate-100">
                          {items.map((item) => {
                            const checked = isChecked(item.id);
                            const hasQuote = Boolean(item.source_quote);
                            const quoteExpanded = Boolean(expandedQuotes[item.id]);

                            return (
                              <div
                                key={item.id}
                                className={`p-4 transition-colors ${
                                  checked ? "bg-slate-50/80" : "bg-white hover:bg-slate-50/40"
                                }`}
                              >
                                <div className="flex items-start gap-3">
                                  <input
                                    type="checkbox"
                                    id={`chk_${item.id}`}
                                    checked={checked}
                                    onChange={() => toggleItem(item.id)}
                                    className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                  />

                                  <div className="flex-1 space-y-1">
                                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
                                      <label
                                        htmlFor={`chk_${item.id}`}
                                        className={`text-sm font-semibold cursor-pointer ${
                                          checked ? "text-slate-400 line-through" : "text-slate-900"
                                        }`}
                                      >
                                        {item.title}
                                      </label>

                                      <div className="flex items-center gap-1.5">
                                        <Badge
                                          variant={
                                            item.status === "source_confirmed"
                                              ? "supported"
                                              : item.status === "needs_check"
                                              ? "unverified"
                                              : "default"
                                          }
                                          size="sm"
                                        >
                                          {t(`services.confirmation.${item.status}`, item.status)}
                                        </Badge>

                                        {item.source_label && (
                                          <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                                            {item.source_label}
                                          </Badge>
                                        )}
                                      </div>
                                    </div>

                                    <p
                                      className={`text-xs leading-relaxed ${
                                        checked ? "text-slate-400 line-through" : "text-slate-600"
                                      }`}
                                    >
                                      {item.description}
                                    </p>

                                    {/* Expandable Verified Verbatim Quote */}
                                    {hasQuote && (
                                      <div className="pt-1">
                                        <button
                                          type="button"
                                          onClick={() =>
                                            setExpandedQuotes((prev) => ({
                                              ...prev,
                                              [item.id]: !prev[item.id],
                                            }))
                                          }
                                          className="text-[11px] text-blue-700 hover:text-blue-900 font-medium inline-flex items-center gap-1 cursor-pointer"
                                        >
                                          <span>Verified Source Quote</span>
                                          {quoteExpanded ? (
                                            <ChevronUp className="w-3 h-3" />
                                          ) : (
                                            <ChevronDown className="w-3 h-3" />
                                          )}
                                        </button>

                                        {quoteExpanded && (
                                          <div className="mt-1 p-2 rounded bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-950 font-mono italic">
                                            "{item.source_quote}"
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </Card>
                    );
                  })}
                </div>
              )}

              {/* Authoritative Key Facts Grid */}
              {guide.key_facts?.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <Shield className="w-5 h-5 text-emerald-600" />
                    <span>{t("services.guidanceTab.keyFactsTitle", "Authoritative Key Facts")}</span>
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {guide.key_facts.map((kf, idx) => (
                      <Card key={idx} className="p-4 border-slate-200 bg-white space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                            {kf.fact_type}
                          </span>
                          {kf.source_label && (
                            <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                              {kf.source_label} (p. {kf.page_number})
                            </Badge>
                          )}
                        </div>

                        <p className="text-base font-bold text-slate-900">{kf.value_text}</p>

                        {kf.source_quote && (
                          <p className="text-[11px] text-slate-500 italic bg-slate-50 p-2 rounded border border-slate-100 font-mono">
                            "{kf.source_quote}"
                          </p>
                        )}
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* Matched Official Government Portals */}
              {guide.matched_portals?.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <Building2 className="w-5 h-5 text-blue-600" />
                    <span>{t("services.guidanceTab.matchedPortalsTitle", "Official Portals for Application")}</span>
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {guide.matched_portals.map((m, idx) => {
                      const portal = m.portal;
                      return (
                        <Card key={idx} className="p-5 border-slate-200 bg-white space-y-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="space-y-1">
                              <h4 className="text-sm font-bold text-slate-900">{portal.name}</h4>
                              {portal.name_ta && (
                                <p className="text-xs text-slate-500 font-tamil">{portal.name_ta}</p>
                              )}
                              <p className="text-xs text-slate-600">{portal.department}</p>
                            </div>
                            <Badge variant="primary" size="sm" className="uppercase text-[10px]">
                              {portal.scope}
                            </Badge>
                          </div>

                          <p className="text-xs text-slate-700 leading-relaxed">{portal.description}</p>

                          {portal.domain_hint && (
                            <div className="text-[11px] font-mono text-slate-500 flex items-center gap-1.5">
                              <Lock className="w-3 h-3 text-emerald-600" />
                              <span>{portal.domain_hint}</span>
                            </div>
                          )}

                          {portal.caution_notes && (
                            <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900">
                              <span className="font-semibold">{t("services.portalsTab.cautionNote", "Caution:")} </span>
                              {portal.caution_notes}
                            </div>
                          )}

                          <div className="pt-1 flex items-center justify-between">
                            <span className="text-[10px] text-slate-400 italic">
                              {m.match_reason}
                            </span>
                            <a
                              href={portal.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-2xs"
                            >
                              <span>{t("services.portalsTab.visitPortal", "Visit Official Portal")}</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Citations Box */}
              {guide.cited_sources?.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    Cited Evidence Records ({guide.cited_sources.length})
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {guide.cited_sources.map((src, i) => (
                      <div
                        key={i}
                        className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1"
                      >
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                            {src.label}
                          </Badge>
                          <span className="font-semibold text-slate-900 truncate">{src.title}</span>
                        </div>
                        <span className="text-[11px] text-slate-500 block">
                          {src.issuing_authority || "Official Gazette"} • Page {src.page_number}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Disclaimers */}
              {guide.disclaimers?.length > 0 && (
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-600 space-y-1">
                  <span className="font-bold text-slate-700 block">
                    {t("services.guidanceTab.disclaimersTitle", "Important Citizen Notices")}
                  </span>
                  {guide.disclaimers.map((d, i) => (
                    <p key={i}>• {d}</p>
                  ))}
                </div>
              )}
            </div>
          ) : (
            /* Input / Query Form */
            <div className="space-y-6">
              <Card className="p-6">
                <form onSubmit={handleSubmitGuide} className="space-y-5">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-900 block">
                      {t("services.guidanceTab.queryLabel", "What public service do you need help with? *")}
                    </label>
                    <input
                      type="text"
                      value={queryInput}
                      onChange={(e) => setQueryInput(e.target.value)}
                      placeholder={t(
                        "services.guidanceTab.queryPlaceholder",
                        "e.g., How do I apply for an income certificate in Tamil Nadu?"
                      )}
                      maxLength={600}
                      className="w-full px-4 py-2.5 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />

                    {/* Example pills */}
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      <span className="text-xs text-slate-400 self-center mr-1">Examples:</span>
                      {exampleQueries.map((ex, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setQueryInput(ex.q)}
                          className="text-xs px-2.5 py-1 rounded-full bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 cursor-pointer transition-colors"
                        >
                          {ex.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-slate-900 block">
                        {t("services.guidanceTab.applicantTypeLabel", "Applicant Category")}
                      </label>
                      <select
                        value={applicantType}
                        onChange={(e) => setApplicantType(e.target.value)}
                        className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="unspecified">{t("services.applicantTypes.unspecified")}</option>
                        <option value="student">{t("services.applicantTypes.student")}</option>
                        <option value="farmer">{t("services.applicantTypes.farmer")}</option>
                        <option value="worker">{t("services.applicantTypes.worker")}</option>
                        <option value="senior_citizen">{t("services.applicantTypes.senior_citizen")}</option>
                        <option value="woman">{t("services.applicantTypes.woman")}</option>
                        <option value="business_owner">{t("services.applicantTypes.business_owner")}</option>
                        <option value="other">{t("services.applicantTypes.other")}</option>
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label className="text-sm font-semibold text-slate-900 block">
                        {t("services.guidanceTab.scopeLabel", "Evidence Sources")}
                      </label>
                      <select
                        value={sourceScope}
                        onChange={(e) => setSourceScope(e.target.value)}
                        className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="all">{t("services.guidanceTab.scopeAll", "Official Library & Citizen Documents")}</option>
                        <option value="official_only">{t("services.guidanceTab.scopeOfficial", "Official Source Library Only")}</option>
                        <option value="user_documents_only">{t("services.guidanceTab.scopeUser", "Uploaded Documents Only")}</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-900 block">
                      {t("services.guidanceTab.situationLabel", "Specific Situation / Context (Optional)")}
                    </label>
                    <input
                      type="text"
                      value={applicantSituation}
                      onChange={(e) => setApplicantSituation(e.target.value)}
                      placeholder={t(
                        "services.guidanceTab.situationPlaceholder",
                        "e.g., College scholarship application, rural background, first-time applicant..."
                      )}
                      maxLength={400}
                      className="w-full px-4 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  {/* PII Detection Warning Alert */}
                  {piiError && (
                    <Alert variant="danger" title="Personal Identifiers Detected">
                      <p className="text-xs text-rose-900">{piiError}</p>
                    </Alert>
                  )}

                  {/* General Error Alert */}
                  {guideError && (
                    <Alert variant="danger" title="Guidance Error">
                      <p className="text-xs text-rose-900">{guideError}</p>
                    </Alert>
                  )}

                  <div className="pt-2 flex items-center justify-between">
                    <Button
                      type="submit"
                      variant="primary"
                      isLoading={isGenerating}
                      disabled={!queryInput.trim()}
                      className="flex items-center gap-2"
                    >
                      <ListChecks className="w-4 h-4" />
                      <span>
                        {isGenerating
                          ? t("services.guidanceTab.submitting", "Analyzing policy records...")
                          : t("services.guidanceTab.submitBtn", "Generate Procedural Guidance")}
                      </span>
                    </Button>

                    {pastGuides.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setShowHistory(!showHistory)}
                        className="text-xs text-blue-700 hover:text-blue-900 font-medium cursor-pointer"
                      >
                        {t("services.guidanceTab.pastGuides", "Past Service Guides")} ({pastGuides.length})
                      </button>
                    )}
                  </div>
                </form>
              </Card>

              {/* Past Guides Drawer / Section */}
              {showHistory && pastGuides.length > 0 && (
                <Card className="p-5 space-y-3">
                  <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                    {t("services.guidanceTab.pastGuides", "Past Service Guides")}
                  </h3>
                  <div className="divide-y divide-slate-100">
                    {pastGuides.map((g) => (
                      <div
                        key={g.id}
                        className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                      >
                        <div className="space-y-0.5">
                          <p className="text-sm font-semibold text-slate-900">{g.query}</p>
                          <span className="text-xs text-slate-500">
                            {new Date(g.created_at).toLocaleDateString()} • {g.checklist_items?.length || 0} items
                          </span>
                        </div>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => {
                            fetchGuide(g.id);
                            const newParams = new URLSearchParams(searchParams);
                            newParams.set("guide_id", g.id);
                            setSearchParams(newParams);
                          }}
                        >
                          {t("services.guidanceTab.viewGuide", "View Guide")}
                        </Button>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: EXPLAIN FORM FIELDS                                                */}
      {/* ========================================================================= */}
      {activeTab === "formExplainer" && (
        <div className="space-y-6">
          <Card className="p-6 space-y-5">
            <div className="space-y-1">
              <h3 className="text-base font-bold text-slate-900">
                {t("services.formTab.title", "Form Field Explainer")}
              </h3>
              <p className="text-xs text-slate-600">
                {t(
                  "services.formTab.subtitle",
                  "Confused by bureaucratic terms in an application form? Paste text or select an uploaded form to get plain-language explanations."
                )}
              </p>
            </div>

            {/* Source Toggle */}
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-sm font-medium text-slate-800 cursor-pointer">
                <input
                  type="radio"
                  name="formSource"
                  checked={formSourceMode === "paste"}
                  onChange={() => setFormSourceMode("paste")}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span>{t("services.formTab.sourcePaste", "Paste Form Text")}</span>
              </label>

              <label className="flex items-center gap-2 text-sm font-medium text-slate-800 cursor-pointer">
                <input
                  type="radio"
                  name="formSource"
                  checked={formSourceMode === "document"}
                  onChange={() => setFormSourceMode("document")}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span>{t("services.formTab.sourceDocument", "Select Uploaded Document")}</span>
              </label>
            </div>

            {/* Input by Mode */}
            {formSourceMode === "paste" ? (
              <div className="space-y-1.5">
                <textarea
                  rows={5}
                  value={rawFormText}
                  onChange={(e) => setRawFormText(e.target.value)}
                  placeholder={t(
                    "services.formTab.pastePlaceholder",
                    "Paste form field labels, instructions, or entire sections here..."
                  )}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
                />
              </div>
            ) : (
              <div className="space-y-1.5">
                <select
                  value={selectedFormDocId}
                  onChange={(e) => setSelectedFormDocId(e.target.value)}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">{t("services.formTab.selectDocPlaceholder", "-- Select an uploaded document --")}</option>
                  {documents.map((d) => (
                    <option key={d.document_id} value={d.document_id}>
                      {d.display_filename} ({d.page_count} pages)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {formError && (
              <Alert variant="danger" title="Form Analysis Error">
                <p className="text-xs text-rose-900">{formError}</p>
              </Alert>
            )}

            <Button
              variant="primary"
              onClick={handleExtractFields}
              isLoading={isExtractingFields}
              className="flex items-center gap-2"
            >
              <Search className="w-4 h-4" />
              <span>{t("services.formTab.extractBtn", "Detect Fields")}</span>
            </Button>
          </Card>

          {/* Detected Fields Selection */}
          {detectedFields.length > 0 && (
            <Card className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-slate-900">
                  {t("services.formTab.fieldsDetected", "Detected Form Fields ({count})").replace(
                    "{count}",
                    detectedFields.length
                  )}
                </h4>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedFieldIds(new Set(detectedFields.map((f) => f.id)))}
                  >
                    Select All
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedFieldIds(new Set())}
                  >
                    Clear All
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                {detectedFields.map((f) => {
                  const checked = selectedFieldIds.has(f.id);
                  return (
                    <div
                      key={f.id}
                      onClick={() =>
                        setSelectedFieldIds((prev) => {
                          const next = new Set(prev);
                          if (next.has(f.id)) next.delete(f.id);
                          else next.add(f.id);
                          return next;
                        })
                      }
                      className={`p-3 rounded-lg border text-xs cursor-pointer transition-all ${
                        checked
                          ? "bg-blue-50/80 border-blue-300 text-blue-950 font-medium"
                          : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <span className="font-semibold truncate">{f.name}</span>
                        {f.page_number && (
                          <span className="text-[10px] text-slate-400">p. {f.page_number}</span>
                        )}
                      </div>
                      {f.context_snippet && (
                        <p className="text-[11px] text-slate-500 truncate mt-1">
                          "{f.context_snippet}"
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="pt-2">
                <Button
                  variant="primary"
                  onClick={handleExplainFields}
                  isLoading={isExplainingFields}
                  disabled={selectedFieldIds.size === 0}
                  className="flex items-center gap-2"
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{t("services.formTab.explainBtn", "Explain Selected Fields")}</span>
                </Button>
              </div>
            </Card>
          )}

          {/* Explanations Grid */}
          {formExplanations.length > 0 && (
            <div className="space-y-4">
              <h4 className="text-base font-bold text-slate-900">
                Form Field Explanations ({formExplanations.length})
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {formExplanations.map((exp, idx) => (
                  <Card key={idx} className="p-5 space-y-3 bg-white border-slate-200">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <h5 className="text-sm font-bold text-slate-900">{exp.field_name}</h5>
                        {exp.page_number && (
                          <span className="text-[11px] text-slate-400">Page {exp.page_number}</span>
                        )}
                      </div>
                      <Badge
                        variant={exp.basis === "stated_in_form_text" ? "supported" : "primary"}
                        size="sm"
                      >
                        {exp.basis === "stated_in_form_text"
                          ? t("services.formTab.basisStated", "Stated in Form")
                          : t("services.formTab.basisGeneral", "General Knowledge")}
                      </Badge>
                    </div>

                    <p className="text-xs text-slate-800 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100">
                      {exp.plain_explanation}
                    </p>

                    {exp.typical_document && (
                      <div className="text-xs space-y-1">
                        <span className="font-semibold text-slate-700">
                          {t("services.formTab.whereToFind", "Where to Find / Document:")}
                        </span>
                        <p className="text-slate-600">{exp.typical_document}</p>
                      </div>
                    )}

                    {exp.common_mistakes && (
                      <div className="p-2.5 rounded-lg bg-amber-50/70 border border-amber-200 text-xs text-amber-900 space-y-0.5">
                        <span className="font-semibold">
                          {t("services.formTab.commonMistakes", "Common Mistakes to Avoid:")}
                        </span>
                        <p>{exp.common_mistakes}</p>
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: OFFICIAL GOVERNMENT PORTALS                                        */}
      {/* ========================================================================= */}
      {activeTab === "portals" && (
        <div className="space-y-5">
          {/* Search & Filters */}
          <Card className="p-4 space-y-3">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
              <input
                type="text"
                value={portalSearch}
                onChange={(e) => setPortalSearch(e.target.value)}
                placeholder={t(
                  "services.portalsTab.searchPlaceholder",
                  "Search portals by name, service, department, or keyword..."
                )}
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Scope Filter Pills */}
            <div className="flex flex-wrap gap-2 pt-1 text-xs">
              <span className="text-slate-400 self-center mr-1">Scope:</span>
              {["all", "state", "central", "local"].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setScopeFilter(s)}
                  className={`px-3 py-1 rounded-full border cursor-pointer transition-colors ${
                    scopeFilter === s
                      ? "bg-blue-600 text-white border-blue-600 font-semibold"
                      : "bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200"
                  }`}
                >
                  {s === "all"
                    ? t("services.portalsTab.allScopes", "All Scopes")
                    : s === "state"
                    ? t("services.portalsTab.stateScope", "State (TN)")
                    : s === "central"
                    ? t("services.portalsTab.centralScope", "Central")
                    : t("services.portalsTab.localScope", "Local")}
                </button>
              ))}

              <span className="text-slate-400 self-center ml-2 mr-1">Type:</span>
              {["all", "certificates", "revenue", "agriculture", "welfare"].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setServiceTypeFilter(st)}
                  className={`px-3 py-1 rounded-full border cursor-pointer capitalize transition-colors ${
                    serviceTypeFilter === st
                      ? "bg-blue-600 text-white border-blue-600 font-semibold"
                      : "bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200"
                  }`}
                >
                  {st === "all" ? t("services.portalsTab.allServices", "All Types") : st}
                </button>
              ))}
            </div>
          </Card>

          {/* Portals Grid */}
          {portalsLoading ? (
            <div className="py-12 flex justify-center">
              <Spinner size="lg" />
            </div>
          ) : filteredPortals.length === 0 ? (
            <EmptyState
              icon={Building2}
              title={t("services.portalsTab.emptyPortals", "No official portals match your filter criteria.")}
              description="Try adjusting your search terms or filter selection."
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {filteredPortals.map((p) => (
                <Card key={p.id} className="p-5 flex flex-col justify-between space-y-3 bg-white border-slate-200 hover:border-slate-300 transition-colors">
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-0.5">
                        <h4 className="text-sm font-bold text-slate-900 leading-snug">{p.name}</h4>
                        {p.name_ta && (
                          <p className="text-xs text-slate-500 font-tamil">{p.name_ta}</p>
                        )}
                      </div>
                      <Badge variant="primary" size="sm" className="uppercase text-[9px]">
                        {p.scope}
                      </Badge>
                    </div>

                    <p className="text-xs text-blue-900 font-medium">{p.department}</p>
                    <p className="text-xs text-slate-600 leading-relaxed">{p.description}</p>

                    {p.domain_hint && (
                      <div className="text-[11px] font-mono text-slate-500 flex items-center gap-1.5 pt-1">
                        <Lock className="w-3 h-3 text-emerald-600" />
                        <span>{p.domain_hint}</span>
                      </div>
                    )}

                    {p.coverage_area && (
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <span className="font-semibold text-slate-600">Coverage:</span>
                        <span>{p.coverage_area}</span>
                      </div>
                    )}

                    {p.caution_notes && (
                      <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900">
                        <span className="font-semibold">{t("services.portalsTab.cautionNote", "Caution:")} </span>
                        {p.caution_notes}
                      </div>
                    )}
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {p.service_types?.slice(0, 2).map((st, i) => (
                        <span
                          key={i}
                          className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium"
                        >
                          {st}
                        </span>
                      ))}
                    </div>

                    <a
                      href={p.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors shadow-2xs"
                    >
                      <span>{t("services.portalsTab.visitPortal", "Visit Portal")}</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: DEMO WORKFLOW (CONTROLLED PLAYWRIGHT SIMULATION)                    */}
      {/* ========================================================================= */}
      {activeTab === "demo" && (
        <div className="space-y-6">
          {/* Top Educational Simulation Banner */}
          <div className="bg-amber-50 border-2 border-amber-300 rounded-xl p-4 text-amber-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-2xs">
            <div className="flex items-start gap-3">
              <ShieldAlert className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
              <div>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" size="sm" className="bg-amber-200 text-amber-900 border-amber-400 font-bold">
                    EDUCATIONAL SIMULATION ONLY
                  </Badge>
                  <span className="text-xs font-bold text-amber-900">Loopback Sandbox</span>
                </div>
                <p className="text-xs text-amber-800 mt-1 leading-relaxed">
                  This workflow executes strictly inside a controlled local browser sandbox (
                  <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[11px]">http://127.0.0.1:8000/demo-portal/</code>
                  ). No data is sent to external servers or government databases. Real personal data (Aadhaar, PAN, phone numbers) is strictly blocked.
                </p>
              </div>
            </div>
            <a
              href="http://127.0.0.1:8000/demo-portal/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-200 hover:bg-amber-300 text-amber-900 text-xs font-semibold whitespace-nowrap transition-colors self-start sm:self-center"
            >
              <span>{t("services.browserDemo.openStandalone", "Open Standalone Portal")}</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* Alerts */}
          {demoPiiError && (
            <Alert variant="danger" title={t("services.browserDemo.piiBlockedTitle", "Personal Identifiers Blocked")}>
              {demoPiiError}
            </Alert>
          )}

          {demoError && (
            <Alert variant="danger" title={t("services.browserDemo.errorTitle", "Simulation Error")}>
              {demoError}
            </Alert>
          )}

          {/* 1. Submission Success View */}
          {demoResult ? (
            <Card className="p-8 border-emerald-300 bg-emerald-50/50 text-center space-y-5 max-w-2xl mx-auto shadow-md">
              <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-700 mx-auto flex items-center justify-center text-3xl font-bold shadow-2xs">
                ✓
              </div>
              <div className="space-y-2">
                <Badge variant="outline" size="md" className="bg-emerald-200 text-emerald-900 border-emerald-400 font-bold">
                  DEMO SIMULATION RECORDED
                </Badge>
                <h3 className="text-2xl font-bold text-slate-900">
                  {t("services.browserDemo.successTitle", "Demo Application Completed Successfully")}
                </h3>
                <p className="text-sm text-slate-600 max-w-lg mx-auto leading-relaxed">
                  {language === "ta" ? demoResult.confirmation_message_ta : demoResult.confirmation_message}
                </p>
              </div>

              <div className="p-4 rounded-xl bg-white border border-emerald-200 text-left space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Demo Application Reference:</span>
                  <span className="font-mono font-bold text-blue-700 text-sm">{demoResult.application_number}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Timestamp:</span>
                  <span className="text-slate-800">{new Date(demoResult.timestamp).toLocaleString()}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500 font-medium">Service Workflow:</span>
                  <span className="text-slate-800">Income Certificate (Educational Simulation)</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-500 font-medium">Environment:</span>
                  <span className="text-emerald-700 font-semibold">Playwright Chromium Local Sandbox</span>
                </div>
              </div>

              <div className="flex items-center justify-center gap-3 pt-2">
                <Button
                  variant="primary"
                  onClick={resetDemoWorkflow}
                  className="inline-flex items-center gap-2"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>{t("services.browserDemo.startNew", "Start New Practice Simulation")}</span>
                </Button>
                <a
                  href="http://127.0.0.1:8000/demo-portal/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-slate-300 bg-white text-slate-700 text-sm font-semibold hover:bg-slate-50 transition-colors"
                >
                  <span>{t("services.browserDemo.viewStandalone", "View Standalone Portal")}</span>
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </Card>
          ) : browserSession ? (
            /* 2. Active Session Multi-Step Form & Live Preview */
            <div className="space-y-6">
              {/* Active Session Status Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
                <div className="flex items-center gap-3">
                  <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-900">
                        {demoManifest?.title || "Demo Income Certificate Application"}
                      </span>
                      <Badge variant="primary" size="sm">
                        Step {browserSession.current_step} of {browserSession.total_steps}
                      </Badge>
                    </div>
                    <span className="text-[11px] font-mono text-slate-500">
                      Session ID: {browserSession.session_id.slice(0, 13)}... • Actions: {browserSession.actions_count}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={closeDemoSession}
                    disabled={isDemoActing}
                    className="text-xs text-rose-700 hover:bg-rose-50 border-rose-300"
                  >
                    {t("services.browserDemo.cancelSession", "Cancel Session")}
                  </Button>
                </div>
              </div>

              {/* Multi-Step Progress Indicator */}
              <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
                <div className="grid grid-cols-5 gap-2 text-center text-xs">
                  {demoManifest?.steps?.map((st) => {
                    const isPassed = st.step_index < browserSession.current_step;
                    const isCurrent = st.step_index === browserSession.current_step;
                    return (
                      <div
                        key={st.step_index}
                        className={`p-2 rounded-lg border transition-all ${
                          isCurrent
                            ? "border-blue-600 bg-blue-50 text-blue-900 font-bold shadow-2xs"
                            : isPassed
                            ? "border-emerald-300 bg-emerald-50/60 text-emerald-800"
                            : "border-slate-200 bg-slate-50 text-slate-500"
                        }`}
                      >
                        <div className="flex items-center justify-center gap-1.5 mb-1">
                          <span
                            className={`w-5 h-5 rounded-full inline-flex items-center justify-center text-[11px] font-bold ${
                              isCurrent
                                ? "bg-blue-600 text-white"
                                : isPassed
                                ? "bg-emerald-600 text-white"
                                : "bg-slate-300 text-slate-700"
                            }`}
                          >
                            {isPassed ? "✓" : st.step_index}
                          </span>
                        </div>
                        <span className="block truncate text-[11px]">
                          {language === "ta" && st.title_ta ? st.title_ta : st.title}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Main Content: Form + Screenshot / Event Audit */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Form Step Column (7 cols) */}
                <div className="lg:col-span-7 space-y-4">
                  <Card className="p-6 border-slate-200 shadow-2xs">
                    {/* Step Title */}
                    <div className="flex items-start justify-between gap-4 mb-4 pb-3 border-b border-slate-100">
                      <div>
                        <h4 className="text-base font-bold text-slate-900">
                          {(() => {
                            const cur = demoManifest?.steps?.find((s) => s.step_index === browserSession.current_step);
                            return language === "ta" && cur?.title_ta ? cur.title_ta : cur?.title || `Step ${browserSession.current_step}`;
                          })()}
                        </h4>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {(() => {
                            const cur = demoManifest?.steps?.find((s) => s.step_index === browserSession.current_step);
                            return language === "ta" && cur?.description_ta ? cur.description_ta : cur?.description || "Complete the required details.";
                          })()}
                        </p>
                      </div>

                      {browserSession.current_step < 5 && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleFillStepSample}
                          className="text-xs flex items-center gap-1.5 text-blue-700 border-blue-300 hover:bg-blue-50"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>{t("services.browserDemo.fillSampleBtn", "Fill Fictional Sample")}</span>
                        </Button>
                      )}
                    </div>

                    {/* Step Form Fields (Steps 1 to 4) */}
                    {browserSession.current_step < 5 && (
                      <div className="space-y-4">
                        {demoManifest?.steps
                          ?.find((s) => s.step_index === browserSession.current_step)
                          ?.fields?.map((field) => (
                            <div key={field.name} className="space-y-1">
                              <label className="block text-xs font-semibold text-slate-700">
                                {language === "ta" && field.label_ta ? field.label_ta : field.label}
                                {field.required && <span className="text-rose-600 ml-0.5">*</span>}
                              </label>

                              {field.field_type === "select" ? (
                                <select
                                  value={activeStepValues[field.name] ?? ""}
                                  onChange={(e) => handleFieldChange(field.name, e.target.value)}
                                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                >
                                  <option value="">-- Select option --</option>
                                  {field.options?.map((opt) => (
                                    <option key={opt.value} value={opt.value}>
                                      {language === "ta" && opt.label_ta ? opt.label_ta : opt.label}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type={field.field_type === "number" ? "number" : field.field_type === "date" ? "date" : "text"}
                                  value={activeStepValues[field.name] ?? ""}
                                  placeholder={field.placeholder || ""}
                                  onChange={(e) => handleFieldChange(field.name, e.target.value)}
                                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 font-sans"
                                />
                              )}

                              {field.help_text && (
                                <span className="text-[11px] text-slate-500 block">
                                  {language === "ta" && field.help_text_ta ? field.help_text_ta : field.help_text}
                                </span>
                              )}
                            </div>
                          ))}
                      </div>
                    )}

                    {/* Step 5: Review & Confirmation */}
                    {browserSession.current_step === 5 && (
                      <div className="space-y-4">
                        <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-amber-950 text-xs">
                          <div className="flex items-center gap-1.5 font-bold mb-1">
                            <Shield className="w-4 h-4 text-amber-700" />
                            <span>Canonical Review State Verified</span>
                          </div>
                          <p className="text-[11px] text-amber-800">
                            Submitting this simulation records practice verification only. Human approval is bound to this SHA-256 hash:
                          </p>
                          <code className="block mt-1 font-mono text-[10px] bg-white p-1 rounded border border-amber-300 text-amber-900 break-all select-all">
                            {demoPreview?.review_hash || "Generating canonical SHA-256 hash..."}
                          </code>
                        </div>

                        {/* Review Summary Table */}
                        <div className="border border-slate-200 rounded-lg overflow-hidden">
                          <table className="w-full text-left text-xs border-collapse">
                            <thead>
                              <tr className="bg-slate-100 text-slate-700 border-b border-slate-200 font-semibold">
                                <th className="p-2.5">Field</th>
                                <th className="p-2.5">Value (Demo)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                              {Object.entries(browserSession.filled_values || {}).map(([k, val]) => (
                                <tr key={k} className="hover:bg-slate-50/80">
                                  <td className="p-2.5 font-medium text-slate-600 capitalize">
                                    {k.replace(/_/g, " ")}
                                  </td>
                                  <td className="p-2.5 font-semibold text-slate-900">
                                    {String(val)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>

                        {/* Confirmation Checkbox */}
                        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                          <label className="flex items-start gap-2.5 cursor-pointer text-xs font-semibold text-slate-800">
                            <input
                              type="checkbox"
                              checked={fictionalAcknowledged}
                              onChange={(e) => setFictionalAcknowledged(e.target.checked)}
                              className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                            />
                            <span>
                              {t(
                                "services.browserDemo.confirmFictionalCheckbox",
                                "I confirm that all entered details are fictional demo data for educational purposes. No real personal identifiers have been entered."
                              )}
                            </span>
                          </label>
                        </div>
                      </div>
                    )}

                    {/* Step Action Buttons */}
                    <div className="flex items-center justify-between pt-5 mt-5 border-t border-slate-100">
                      {browserSession.current_step > 1 ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={prevDemoStep}
                          disabled={isDemoActing}
                          className="inline-flex items-center gap-1.5 text-xs"
                        >
                          <ArrowLeft className="w-3.5 h-3.5" />
                          <span>{t("common.back", "Back")}</span>
                        </Button>
                      ) : (
                        <div></div>
                      )}

                      {browserSession.current_step < 5 ? (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={handleContinueStep}
                          disabled={isDemoActing}
                          className="inline-flex items-center gap-1.5 text-xs"
                        >
                          {isDemoActing ? (
                            <Spinner size="xs" className="text-white" />
                          ) : (
                            <>
                              <span>{t("services.browserDemo.continueBtn", "Save & Continue")}</span>
                              <ArrowRight className="w-3.5 h-3.5" />
                            </>
                          )}
                        </Button>
                      ) : (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => submitDemoWorkflow(demoPreview?.review_hash, true)}
                          disabled={isDemoActing || !fictionalAcknowledged || !demoPreview?.review_hash}
                          className="inline-flex items-center gap-1.5 text-xs bg-emerald-700 hover:bg-emerald-800 border-emerald-800"
                        >
                          {isDemoActing ? (
                            <Spinner size="xs" className="text-white" />
                          ) : (
                            <>
                              <FileCheck className="w-3.5 h-3.5" />
                              <span>{t("services.browserDemo.submitBtn", "Submit Demo Application")}</span>
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </Card>
                </div>

                {/* Visual Audit & Screenshot Column (5 cols) */}
                <div className="lg:col-span-5 space-y-4">
                  {/* Live Screenshot Card */}
                  <Card className="p-4 border-slate-200 shadow-2xs space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <Eye className="w-4 h-4 text-blue-700" />
                        <h5 className="text-xs font-bold text-slate-900">
                          {t("services.browserDemo.liveViewTitle", "Playwright Sandbox View")}
                        </h5>
                      </div>
                      <Badge variant="outline" size="sm" className="text-[10px]">
                        1024x720 JPEG
                      </Badge>
                    </div>

                    <div className="rounded-lg border border-slate-200 bg-slate-100 overflow-hidden relative group">
                      {browserSession.last_screenshot_url ? (
                        <img
                          src={browserService.getScreenshotUrl(browserSession.session_id, browserSession.last_screenshot_id)}
                          alt="Playwright Demo Sandbox Screenshot"
                          className="w-full h-auto object-cover cursor-pointer hover:opacity-95 transition-opacity"
                          onClick={() => setSelectedScreenshotUrl(browserService.getScreenshotUrl(browserSession.session_id, browserSession.last_screenshot_id))}
                        />
                      ) : (
                        <div className="h-44 flex flex-col items-center justify-center text-slate-400 text-xs p-4 text-center">
                          <Compass className="w-8 h-8 text-slate-300 mb-2 animate-spin" />
                          <span>Capturing browser viewport snapshot...</span>
                        </div>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400 block text-center">
                      Click image to view enlarged visual audit snapshot
                    </span>
                  </Card>

                  {/* Execution Event Timeline */}
                  <Card className="p-4 border-slate-200 shadow-2xs space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-4 h-4 text-slate-600" />
                        <h5 className="text-xs font-bold text-slate-900">
                          {t("services.browserDemo.auditLogTitle", "Automation Event Audit Log")}
                        </h5>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400">
                        {browserSession.events?.length || 0} event(s)
                      </span>
                    </div>

                    <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                      {browserSession.events?.slice().reverse().map((ev, i) => (
                        <div key={i} className="p-2 rounded bg-slate-50 border border-slate-100 text-[11px] space-y-0.5">
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-blue-900 capitalize">{ev.action.replace(/_/g, " ")}</span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              {new Date(ev.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                            </span>
                          </div>
                          <p className="text-slate-600 text-[10px]">{ev.message}</p>
                        </div>
                      ))}
                    </div>
                  </Card>
                </div>
              </div>
            </div>
          ) : (
            /* 3. Launch Screen (No Active Session) */
            <div className="space-y-6">
              <Card className="p-8 border-slate-200 bg-white text-center space-y-5 max-w-3xl mx-auto shadow-2xs">
                <div className="inline-flex p-4 rounded-full bg-blue-100 text-blue-700 mb-1">
                  <Play className="w-8 h-8" />
                </div>

                <div className="space-y-2 max-w-xl mx-auto">
                  <Badge variant="primary" size="md">
                    {t("services.browserDemo.liveBadge", "Interactive Public Service Simulation")}
                  </Badge>
                  <h3 className="text-2xl font-bold text-slate-900">
                    {t("services.browserDemo.launchTitle", "Practice Applying for an Income Certificate")}
                  </h3>
                  <p className="text-sm text-slate-600 leading-relaxed">
                    {t(
                      "services.browserDemo.launchDesc",
                      "Experience the complete 5-step certificate application workflow in an isolated Playwright browser sandbox. Learn what information is requested, inspect locators, and review submission receipts without risk."
                    )}
                  </p>
                </div>

                {/* Safety Guarantee Columns */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-xl mx-auto text-left text-xs pt-2">
                  <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-1">
                    <span className="font-bold text-slate-900 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5 text-blue-600" />
                      <span>100% Localhost Sandbox</span>
                    </span>
                    <p className="text-slate-600 text-[11px]">
                      Runs strictly on local loopback host. Never contacts real government servers.
                    </p>
                  </div>

                  <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-1">
                    <span className="font-bold text-slate-900 flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Strict PII Protection</span>
                    </span>
                    <p className="text-slate-600 text-[11px]">
                      Aadhaar, PAN, and phone numbers are rejected by backend guardrails.
                    </p>
                  </div>

                  <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-1">
                    <span className="font-bold text-slate-900 flex items-center gap-1.5">
                      <Eye className="w-3.5 h-3.5 text-indigo-600" />
                      <span>Visual Audit Snapshots</span>
                    </span>
                    <p className="text-slate-600 text-[11px]">
                      Live screenshots capture every action and field change transparently.
                    </p>
                  </div>

                  <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-1">
                    <span className="font-bold text-slate-900 flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-amber-600" />
                      <span>SHA-256 Approval Binding</span>
                    </span>
                    <p className="text-slate-600 text-[11px]">
                      Simulation submission requires verified citizen review hash confirmation.
                    </p>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-3">
                  <Button
                    variant="primary"
                    onClick={() => startDemoSession({ portalId: "prt_demo_portal", lang: language })}
                    disabled={isDemoActing}
                    className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold shadow-sm"
                  >
                    {isDemoActing ? (
                      <Spinner size="xs" className="text-white" />
                    ) : (
                      <>
                        <Play className="w-4 h-4 fill-white" />
                        <span>{t("services.browserDemo.startBtn", "Launch Interactive Demo Workflow")}</span>
                      </>
                    )}
                  </Button>

                  <a
                    href="http://127.0.0.1:8000/demo-portal/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-slate-300 bg-white text-slate-700 text-sm font-semibold hover:bg-slate-50 transition-colors"
                  >
                    <span>{t("services.browserDemo.openStandaloneBtn", "Open Standalone Portal")}</span>
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
              </Card>

              {/* Past Demo Sessions Table */}
              {pastDemoSessions?.length > 0 && (
                <Card className="p-6 border-slate-200 shadow-2xs space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <h4 className="text-sm font-bold text-slate-900">
                      {t("services.browserDemo.pastSessionsTitle", "Recent Practice Sessions")}
                    </h4>
                    <span className="text-xs text-slate-500 font-mono">
                      {pastDemoSessions.length} recorded session(s)
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
                          <th className="p-2.5">Session Ref</th>
                          <th className="p-2.5">Status</th>
                          <th className="p-2.5">Step Reached</th>
                          <th className="p-2.5">Actions</th>
                          <th className="p-2.5">Date</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {pastDemoSessions.map((ps) => (
                          <tr key={ps.session_id} className="hover:bg-slate-50/80">
                            <td className="p-2.5 font-mono text-blue-700 font-medium">
                              {ps.application_number || `${ps.session_id.slice(0, 8)}...`}
                            </td>
                            <td className="p-2.5">
                              <Badge
                                variant={ps.status === "submitted" ? "success" : ps.status === "active" ? "primary" : "neutral"}
                                size="sm"
                              >
                                {ps.status?.toUpperCase()}
                              </Badge>
                            </td>
                            <td className="p-2.5 font-medium text-slate-800">
                              Step {ps.current_step} / {ps.total_steps}
                            </td>
                            <td className="p-2.5 text-slate-600 font-mono">
                              {ps.actions_count} action(s)
                            </td>
                            <td className="p-2.5 text-slate-500">
                              {new Date(ps.created_at).toLocaleDateString()} {new Date(ps.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* Screenshot Enlarge Modal */}
          {selectedScreenshotUrl && (
            <div
              className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
              onClick={() => setSelectedScreenshotUrl(null)}
            >
              <div className="bg-white rounded-xl overflow-hidden max-w-4xl w-full shadow-2xl relative" onClick={(e) => e.stopPropagation()}>
                <div className="p-3 bg-slate-900 text-white flex items-center justify-between text-xs">
                  <span className="font-bold flex items-center gap-1.5">
                    <Eye className="w-4 h-4 text-blue-400" />
                    <span>Visual Audit Sandbox Snapshot</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => setSelectedScreenshotUrl(null)}
                    className="text-slate-400 hover:text-white font-bold px-2 py-0.5 rounded cursor-pointer"
                  >
                    ✕
                  </button>
                </div>
                <div className="p-2 bg-slate-100 flex items-center justify-center max-h-[80vh] overflow-auto">
                  <img src={selectedScreenshotUrl} alt="Visual Audit Snapshot Enlarged" className="max-w-full h-auto rounded shadow" />
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
