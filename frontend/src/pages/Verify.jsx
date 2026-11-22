import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Clock,
  FileText,
  ExternalLink,
  RefreshCw,
  Trash2,
  History,
  Plus,
  Search,
  BookOpen,
  Info,
  Layers,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card";
import { FileDropzone } from "../components/ui/FileDropzone";
import { useLanguage } from "../hooks/useLanguage";
import { useVerification } from "../hooks/useVerification";
import { useDocuments } from "../hooks/useDocuments";
import { sourcesService } from "../services/sourcesService";

const EXAMPLE_CLAIMS = [
  {
    en: "Applications for the Green Energy Rooftop Subsidy are open until 31 December 2025 with Rs. 2,50,000 grant amount.",
    ta: "பசுமை ஆற்றல் கூரை மானியத் திட்டத்தின் விண்ணப்பங்கள் ரூ. 2,50,000 மானியத்துடன் 31 டிசம்பர் 2025 வரை வரவேற்கப்படுகின்றன.",
  },
  {
    en: "The Tamil Nadu government reduced the minimum age for Old Age Pension to 58 years.",
    ta: "தமிழ்நாடு அரசு முதியோர் ஓய்வூதியத்திற்கான குறைந்தபட்ச வயதை 58 ஆகக் குறைத்துள்ளது.",
  },
  {
    en: "Annual property tax revisions will increase by 10% across all municipal corporations starting 1 April 2025.",
    ta: "அனைத்து மாநகராட்சிகளிலும் ஆண்டு சொத்து வரி ஏப்ரல் 1, 2025 முதல் 10% உயர்த்தப்படும்.",
  },
];

export function Verify() {
  const { t, language: uiLang } = useLanguage();
  const [searchParams] = useSearchParams();
  const {
    report,
    stage,
    progressPct,
    error,
    loading,
    isPolling,
    pastVerifications,
    activeId,
    startVerification,
    loadVerification,
    retryAnalysis,
    removeVerification,
    reset,
  } = useVerification();

  const { documents: userDocs } = useDocuments();

  // Tab State: 'verify' | 'library'
  const [activeTab, setActiveTab] = useState("verify");

  // Form State
  const [claim, setClaim] = useState("");
  const [scope, setScope] = useState("official"); // official | official_and_documents | documents
  const [language, setLanguage] = useState("auto");
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [force, setForce] = useState(false);

  // Official Sources Library State
  const [sources, setSources] = useState([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [sourcesError, setSourcesError] = useState(null);
  const [isAddSourceOpen, setIsAddSourceOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [rebuildingId, setRebuildingId] = useState(null);
  const [deletingSourceId, setDeletingSourceId] = useState(null);

  // Add Source Form State
  const [sourceForm, setSourceForm] = useState({
    title: "",
    issuing_authority: "",
    source_url: "",
    publication_date: "",
    effective_date: "",
    series_id: "",
    status: "current",
    superseded_by: "",
    notes: "",
  });
  const [sourceFile, setSourceFile] = useState(null);
  const [uploadingSource, setUploadingSource] = useState(false);
  const [sourceUploadError, setSourceUploadError] = useState(null);

  // Load official sources
  const fetchSources = useCallback(async () => {
    setLoadingSources(true);
    try {
      const data = await sourcesService.listSources();
      setSources(data.sources || []);
      setSourcesError(null);
    } catch (err) {
      setSourcesError(err.message || "Failed to load official sources.");
    } finally {
      setLoadingSources(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    sourcesService
      .listSources()
      .then((data) => {
        if (mounted) setSources(data.sources || []);
      })
      .catch((err) => {
        if (mounted) setSourcesError(err.message || "Failed to load official sources.");
      });
    return () => {
      mounted = false;
    };
  }, []);

  // URL query parameter ?id=... support
  useEffect(() => {
    const queryId = searchParams.get("id");
    if (queryId && queryId !== activeId) {
      loadVerification(queryId);
    }
  }, [searchParams, activeId, loadVerification]);

  // Handle Claim Submission
  const handleVerifySubmit = async (e) => {
    e?.preventDefault();
    if (!claim.trim() || loading || isPolling) return;

    try {
      await startVerification({
        claim: claim.trim(),
        language,
        scope,
        documentIds: selectedDocIds,
        force,
      });
    } catch {
      // Error handled in hook
    }
  };

  // Handle Add Source Form Submission
  const handleAddSourceSubmit = async (e) => {
    e.preventDefault();
    if (!sourceFile || !sourceForm.title.trim() || !sourceForm.issuing_authority.trim()) {
      setSourceUploadError("Please provide a title, issuing authority, and a PDF file.");
      return;
    }

    setUploadingSource(true);
    setSourceUploadError(null);

    try {
      const formData = new FormData();
      formData.append("file", sourceFile);
      formData.append("title", sourceForm.title.trim());
      formData.append("issuing_authority", sourceForm.issuing_authority.trim());
      if (sourceForm.source_url) formData.append("source_url", sourceForm.source_url.trim());
      if (sourceForm.publication_date) formData.append("publication_date", sourceForm.publication_date);
      if (sourceForm.effective_date) formData.append("effective_date", sourceForm.effective_date);
      if (sourceForm.series_id) formData.append("series_id", sourceForm.series_id.trim());
      if (sourceForm.status) formData.append("status", sourceForm.status);
      if (sourceForm.superseded_by) formData.append("superseded_by", sourceForm.superseded_by.trim());
      if (sourceForm.notes) formData.append("notes", sourceForm.notes.trim());

      await sourcesService.uploadSource(formData);
      setIsAddSourceOpen(false);
      setSourceFile(null);
      setSourceForm({
        title: "",
        issuing_authority: "",
        source_url: "",
        publication_date: "",
        effective_date: "",
        series_id: "",
        status: "current",
        superseded_by: "",
        notes: "",
      });
      await fetchSources();
    } catch (err) {
      setSourceUploadError(err.message || "Failed to upload official source.");
    } finally {
      setUploadingSource(false);
    }
  };

  // Rebuild Index
  const handleRebuildIndex = async (sourceId) => {
    setRebuildingId(sourceId);
    try {
      await sourcesService.rebuildIndex(sourceId);
      await fetchSources();
    } catch (err) {
      alert(`Index rebuild failed: ${err.message}`);
    } finally {
      setRebuildingId(null);
    }
  };

  // Delete Source
  const handleDeleteSource = async (sourceId) => {
    try {
      await sourcesService.deleteSource(sourceId);
      setDeletingSourceId(null);
      await fetchSources();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const isCharNearLimit = claim.length > 900;
  const isCharOverLimit = claim.length > 1000;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Top Header */}
      <PageHeader
        title={t("verify.title", "Civic Fact Verification")}
        description={t(
          "verify.subtitle",
          "Cross-examine public claims and news reports against curated official government orders and gazettes."
        )}
        badge={
          <Badge variant="primary" size="sm">
            Module 3 • Evidence-Based
          </Badge>
        }
      />

      {/* Main Tabs */}
      <div className="flex border-b border-slate-200 gap-6">
        <button
          type="button"
          onClick={() => setActiveTab("verify")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeTab === "verify"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <ShieldCheck className="w-4 h-4" />
          {t("verify.tabs.verify", "Verify Public Claim")}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("library")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeTab === "library"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <BookOpen className="w-4 h-4" />
          {t("verify.tabs.library", "Official Source Library")}
          <span className="ml-1 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono">
            {sources.length}
          </span>
        </button>
      </div>

      {/* ============================================================== */}
      {/* TAB 1: VERIFY PUBLIC CLAIM                                     */}
      {/* ============================================================== */}
      {activeTab === "verify" && (
        <div className="space-y-6">
          {/* Library Empty Banner if scope includes official */}
          {scope !== "documents" && sources.length === 0 && !loadingSources && (
            <Alert
              variant="warning"
              title={t("verify.libraryEmptyAlert.title", "Official Source Library is Empty")}
              className="flex items-center justify-between"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 w-full">
                <span>
                  {t(
                    "verify.libraryEmptyAlert.desc",
                    "No official government orders have been registered yet. Add official PDFs to enable fact-checking or switch scope to 'Uploaded Documents'."
                  )}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setActiveTab("library")}
                  className="whitespace-nowrap"
                >
                  {t("verify.libraryEmptyAlert.cta", "Manage Library")}
                </Button>
              </div>
            </Alert>
          )}

          {/* Claim Submission Card */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>{t("verify.claimInput.label", "Enter Public Claim or News Report")}</CardTitle>
                <CardDescription>
                  {t(
                    "verify.subtitle",
                    "Verify public claims against authoritative official state records."
                  )}
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsHistoryOpen(true)}
                className="gap-1.5 text-xs"
              >
                <History className="w-3.5 h-3.5" />
                {t("verify.claimInput.historyBtn", "Past Verifications")}
              </Button>
            </CardHeader>

            <CardContent className="space-y-4 pt-1">
              <form onSubmit={handleVerifySubmit} className="space-y-4">
                {/* Textarea */}
                <div>
                  <textarea
                    rows={3}
                    value={claim}
                    onChange={(e) => setClaim(e.target.value)}
                    placeholder={t(
                      "verify.claimInput.placeholder",
                      "e.g., Applications for the Green Energy Rooftop Subsidy are open until 31 December 2025 with Rs. 2,50,000 grant amount."
                    )}
                    className={`w-full rounded-lg border p-3 text-sm text-slate-900 transition-colors focus-visible:outline-none focus-visible:ring-3 ${
                      isCharOverLimit
                        ? "border-rose-400 focus:border-rose-500 focus-visible:ring-rose-100"
                        : "border-slate-300 focus:border-blue-600 focus-visible:ring-blue-100"
                    }`}
                  />
                  <div className="flex justify-between items-center text-xs text-slate-400 mt-1">
                    <span>
                      {isCharOverLimit && (
                        <span className="text-rose-600 font-medium">
                          {t("verify.claimInput.charLimitError", "Exceeds 1000 character limit.")}
                        </span>
                      )}
                    </span>
                    <span
                      className={`font-mono ${
                        isCharOverLimit
                          ? "text-rose-600 font-bold"
                          : isCharNearLimit
                          ? "text-amber-600 font-semibold"
                          : ""
                      }`}
                    >
                      {claim.length} / 1000
                    </span>
                  </div>
                </div>

                {/* Example Claims */}
                <div className="space-y-1.5">
                  <span className="text-xs font-semibold text-slate-500">
                    {t("verify.claimInput.examplesTitle", "Try an example civic claim:")}
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLE_CLAIMS.map((ex, idx) => {
                      const text = uiLang === "ta" ? ex.ta : ex.en;
                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => setClaim(text)}
                          className="text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-md text-left transition-colors cursor-pointer border border-slate-200 truncate max-w-md"
                          title={text}
                        >
                          "{text}"
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Controls Row: Scope, Language, Force */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                  {/* Scope Selector */}
                  <div className="flex flex-col gap-1 text-left">
                    <label className="text-xs font-semibold text-slate-700">
                      {t("verify.claimInput.scopeLabel", "Search Scope")}
                    </label>
                    <select
                      value={scope}
                      onChange={(e) => setScope(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus-visible:ring-3 focus-visible:ring-blue-100 focus-visible:outline-none"
                    >
                      <option value="official">
                        {t("verify.claimInput.scopeOfficial", "Official Sources Only (Curated)")}
                      </option>
                      <option value="official_and_documents">
                        {t("verify.claimInput.scopeOfficialAndDocs", "Official + Uploaded Documents")}
                      </option>
                      <option value="documents">
                        {t("verify.claimInput.scopeDocs", "Uploaded Documents Only")}
                      </option>
                    </select>
                  </div>

                  {/* Language Selector */}
                  <div className="flex flex-col gap-1 text-left">
                    <label className="text-xs font-semibold text-slate-700">
                      {t("verify.claimInput.languageLabel", "Response Language")}
                    </label>
                    <select
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus-visible:ring-3 focus-visible:ring-blue-100 focus-visible:outline-none"
                    >
                      <option value="auto">Auto Detect</option>
                      <option value="en">English</option>
                      <option value="ta">தமிழ்</option>
                    </select>
                  </div>

                  {/* Force Recheck Checkbox */}
                  <div className="flex items-end pb-2">
                    <label className="inline-flex items-center gap-2 cursor-pointer text-xs text-slate-600 select-none">
                      <input
                        type="checkbox"
                        checked={force}
                        onChange={(e) => setForce(e.target.checked)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4"
                      />
                      <span>{t("verify.claimInput.forceRecheck", "Bypass cache (re-verify)")}</span>
                    </label>
                  </div>
                </div>

                {/* Optional User Documents Selector (when scope includes documents) */}
                {scope !== "official" && (
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2">
                    <span className="text-xs font-semibold text-slate-700 block">
                      {t("verify.claimInput.selectDocsLabel", "Select User Documents to Include (max 5):")}
                    </span>
                    {userDocs.length === 0 ? (
                      <span className="text-xs text-slate-400">
                        No user documents uploaded yet. Upload documents in the Document Intelligence page.
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto">
                        {userDocs.map((doc) => {
                          const isSelected = selectedDocIds.includes(doc.document_id);
                          return (
                            <button
                              key={doc.document_id}
                              type="button"
                              onClick={() => {
                                if (isSelected) {
                                  setSelectedDocIds(selectedDocIds.filter((id) => id !== doc.document_id));
                                } else {
                                  if (selectedDocIds.length < 5) {
                                    setSelectedDocIds([...selectedDocIds, doc.document_id]);
                                  }
                                }
                              }}
                              className={`text-xs px-2.5 py-1 rounded-md border flex items-center gap-1.5 transition-colors cursor-pointer ${
                                isSelected
                                  ? "bg-blue-600 text-white border-blue-600 font-medium"
                                  : "bg-white text-slate-700 border-slate-300 hover:bg-slate-100"
                              }`}
                            >
                              <FileText className="w-3.5 h-3.5" />
                              <span className="truncate max-w-[180px]">{doc.filename}</span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Submit Button */}
                <div className="flex justify-end pt-2">
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={!claim.trim() || isCharOverLimit || loading || isPolling}
                    className="gap-2 px-6"
                  >
                    {loading || isPolling ? (
                      <>
                        <Spinner size="sm" />
                        {t("verify.claimInput.verifyingBtn", "Verifying Claim...")}
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="w-4 h-4" />
                        {t("verify.claimInput.verifyBtn", "Verify Claim")}
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Progress / Stage Indicator */}
          {(loading || isPolling) && (
            <Card className="border-blue-200 bg-blue-50/30 animate-pulse">
              <CardContent className="p-5 space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold text-blue-900">
                  <span className="flex items-center gap-2">
                    <Spinner size="sm" />
                    <span>
                      {t(`verify.stages.${stage}`, stage.replace(/_/g, " "))}
                    </span>
                  </span>
                  <span className="font-mono">{progressPct}%</span>
                </div>
                <div className="w-full bg-blue-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-500 ease-out"
                    style={{ width: `${Math.max(8, progressPct)}%` }}
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error Alert */}
          {error && (
            <Alert variant="danger" title="Fact Verification Error">
              {error}
            </Alert>
          )}

          {/* ============================================================== */}
          {/* VERIFICATION REPORT DISPLAY                                    */}
          {/* ============================================================== */}
          {report && (
            <div className="space-y-6">
              {/* Overall Verdict Header Card */}
              <Card
                className={`border-2 ${
                  report.overall_verdict === "supported"
                    ? "border-emerald-300 bg-emerald-50/20"
                    : report.overall_verdict === "contradicted"
                    ? "border-rose-300 bg-rose-50/20"
                    : report.overall_verdict === "outdated"
                    ? "border-purple-300 bg-purple-50/20"
                    : report.overall_verdict === "mixed"
                    ? "border-indigo-300 bg-indigo-50/20"
                    : "border-amber-300 bg-amber-50/20"
                }`}
              >
                <CardContent className="p-6 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-4">
                    <div className="space-y-1">
                      <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        {t("verify.cards.overallVerdict", "Overall Verdict")}
                      </span>
                      <div className="flex items-center gap-3">
                        <Badge variant={report.overall_verdict} size="md" className="text-sm px-3 py-1 font-bold">
                          {t(`verify.verdicts.${report.overall_verdict}`, report.overall_verdict.toUpperCase())}
                        </Badge>
                        <span className="text-xs text-slate-500">
                          ID: <span className="font-mono">{report.verification_id?.slice(0, 8)}</span>
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={reset}
                        className="text-xs"
                      >
                        {t("verify.cards.startNew", "Verify Another Claim")}
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => retryAnalysis(report.verification_id)}
                        className="text-xs gap-1.5"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        {t("verify.cards.retryAnalysis", "Retry Analysis")}
                      </Button>
                    </div>
                  </div>

                  {/* Plain Language Summary */}
                  <p className="text-sm text-slate-800 leading-relaxed font-medium">
                    {report.overall_summary}
                  </p>

                  {/* Limitation Sentence (Honest Scope) */}
                  <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-100/80 p-2.5 rounded-lg border border-slate-200">
                    <Info className="w-4 h-4 text-slate-400 flex-shrink-0" />
                    <span>
                      {t(
                        "verify.limitationNotice",
                        "Searched only the sources listed. Not finding evidence does not mean a claim is false."
                      )}
                    </span>
                  </div>
                </CardContent>
              </Card>

              {/* Per-Claim Breakdown Cards */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-600" />
                  {t("verify.cards.claimsBreakdown", `Evaluated Proposition(s) (${report.claims?.length || 0})`)}
                </h3>

                {report.claims?.map((claimItem, cIdx) => (
                  <ClaimEvaluationCard key={claimItem.claim_id || cIdx} item={claimItem} t={t} />
                ))}
              </div>

              {/* Coverage & Scope Details */}
              {report.coverage && (
                <Card className="bg-slate-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2 text-slate-700">
                      <Search className="w-4 h-4 text-slate-500" />
                      {t("verify.cards.coverage", "Verification Coverage & Sources")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="text-xs text-slate-600 space-y-2">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="p-2.5 bg-white rounded border border-slate-200">
                        <span className="text-slate-400 block mb-0.5">Official Sources Searched:</span>
                        <span className="font-semibold text-slate-800">
                          {report.coverage.official_sources_searched_count} source(s)
                        </span>
                      </div>
                      <div className="p-2.5 bg-white rounded border border-slate-200">
                        <span className="text-slate-400 block mb-0.5">Passages Examined:</span>
                        <span className="font-semibold text-slate-800">
                          {report.coverage.passages_examined_count} passage(s)
                        </span>
                      </div>
                      <div className="p-2.5 bg-white rounded border border-slate-200">
                        <span className="text-slate-400 block mb-0.5">Library Manifest Version:</span>
                        <span className="font-mono text-slate-800 font-semibold truncate block">
                          {report.coverage.library_version || "v1"}
                        </span>
                      </div>
                    </div>

                    {report.coverage.official_source_titles?.length > 0 && (
                      <div className="pt-2">
                        <span className="font-semibold text-slate-700 block mb-1">
                          Official Records Consulted:
                        </span>
                        <ul className="list-disc list-inside space-y-0.5 text-slate-600 pl-1">
                          {report.coverage.official_source_titles.map((title, i) => (
                            <li key={i}>{title}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* TAB 2: OFFICIAL SOURCE LIBRARY                                 */}
      {/* ============================================================== */}
      {activeTab === "library" && (
        <div className="space-y-6">
          {/* Header Action */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
            <div>
              <h2 className="text-base font-bold text-slate-900">
                {t("verify.library.title", "Official Government Source Library")}
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                {t(
                  "verify.library.subtitle",
                  "Curated collection of state government orders, notifications, gazettes, and official circulars."
                )}
              </p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsAddSourceOpen(true)}
              className="gap-1.5 whitespace-nowrap"
            >
              <Plus className="w-4 h-4" />
              {t("verify.library.addSourceBtn", "Add Official Source")}
            </Button>
          </div>

          {/* Sources List / Table */}
          {loadingSources ? (
            <div className="flex justify-center p-12">
              <Spinner size="lg" />
            </div>
          ) : sourcesError ? (
            <Alert variant="danger" title="Error">
              {sourcesError}
            </Alert>
          ) : sources.length === 0 ? (
            <EmptyState
              icon={BookOpen}
              title={t("verify.library.emptyTitle", "No Official Sources Added Yet")}
              description={t(
                "verify.library.emptyDesc",
                "Upload official Government Orders (GOs), gazette notifications, or departmental circulars to enable fact checking."
              )}
              action={
                <Button variant="primary" size="sm" onClick={() => setIsAddSourceOpen(true)} className="gap-1.5">
                  <Plus className="w-4 h-4" />
                  {t("verify.library.addSourceBtn", "Add Official Source")}
                </Button>
              }
            />
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-700">
                  <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                    <tr>
                      <th className="p-4">{t("verify.library.tableTitle", "Title & Authority")}</th>
                      <th className="p-4">{t("verify.library.tableDates", "Effective Date")}</th>
                      <th className="p-4">{t("verify.library.tableStatus", "Policy Status")}</th>
                      <th className="p-4">{t("verify.library.tableIndex", "Vector Index")}</th>
                      <th className="p-4 text-right">{t("verify.library.tableActions", "Actions")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sources.map((src) => (
                      <tr key={src.source_id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="p-4">
                          <div className="font-semibold text-slate-900">{src.title}</div>
                          <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                            <span>{src.issuing_authority}</span>
                            {src.source_url && (
                              <a
                                href={src.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-blue-600 hover:underline flex items-center gap-0.5"
                              >
                                <ExternalLink className="w-3 h-3" />
                                {t("verify.cards.sourceLink", "Source Link")}
                              </a>
                            )}
                          </div>
                        </td>
                        <td className="p-4 text-xs font-mono">
                          {src.effective_date || src.publication_date || "—"}
                        </td>
                        <td className="p-4">
                          <Badge
                            variant={
                              src.status === "current"
                                ? "success"
                                : src.status === "superseded"
                                ? "outdated"
                                : "outline"
                            }
                            size="sm"
                          >
                            {src.status}
                          </Badge>
                        </td>
                        <td className="p-4">
                          <Badge
                            variant={src.index_status === "indexed" ? "primary" : "outline"}
                            size="sm"
                          >
                            {src.index_status === "indexed" ? "Indexed" : "Not Indexed"}
                          </Badge>
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <a
                              href={sourcesService.getSourceFileUrl(src.source_id)}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium transition-colors"
                            >
                              {t("verify.library.viewPdf", "View PDF")}
                            </a>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleRebuildIndex(src.source_id)}
                              disabled={rebuildingId === src.source_id}
                              className="text-xs py-1 px-2"
                              title="Rebuild FAISS Vector Index"
                            >
                              {rebuildingId === src.source_id ? (
                                <Spinner size="sm" />
                              ) : (
                                <RefreshCw className="w-3.5 h-3.5" />
                              )}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setDeletingSourceId(src.source_id)}
                              className="text-xs py-1 px-2 text-rose-600 hover:bg-rose-50 hover:border-rose-300"
                              title="Delete source"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: ADD OFFICIAL SOURCE                                     */}
      {/* ============================================================== */}
      <Modal
        isOpen={isAddSourceOpen}
        onClose={() => setIsAddSourceOpen(false)}
        title={t("verify.library.uploadModalTitle", "Add Official Government Source")}
      >
        <form onSubmit={handleAddSourceSubmit} className="space-y-4">
          {sourceUploadError && (
            <Alert variant="danger" title="Upload Failed">
              {sourceUploadError}
            </Alert>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              {t("verify.library.formTitle", "Document Title *")}
            </label>
            <input
              type="text"
              required
              value={sourceForm.title}
              onChange={(e) => setSourceForm({ ...sourceForm, title: e.target.value })}
              placeholder="e.g. G.O. Ms. No. 42 - Solar Rooftop Subsidy Policy 2025"
              className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-blue-600 focus-visible:outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              {t("verify.library.formAuthority", "Issuing Authority / Department *")}
            </label>
            <input
              type="text"
              required
              value={sourceForm.issuing_authority}
              onChange={(e) => setSourceForm({ ...sourceForm, issuing_authority: e.target.value })}
              placeholder="e.g. Energy Department, Government of Tamil Nadu"
              className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-blue-600 focus-visible:outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              {t("verify.library.formSourceUrl", "Official Source URL (e.g., https://cms.tn.gov.in/...)")}
            </label>
            <input
              type="url"
              value={sourceForm.source_url}
              onChange={(e) => setSourceForm({ ...sourceForm, source_url: e.target.value })}
              placeholder="https://cms.tn.gov.in/sites/default/files/go/energy_e_42_2025.pdf"
              className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-blue-600 focus-visible:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                {t("verify.library.formEffDate", "Effective Date")}
              </label>
              <input
                type="date"
                value={sourceForm.effective_date}
                onChange={(e) => setSourceForm({ ...sourceForm, effective_date: e.target.value })}
                className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-blue-600 focus-visible:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                {t("verify.library.formStatus", "Policy Status")}
              </label>
              <select
                value={sourceForm.status}
                onChange={(e) => setSourceForm({ ...sourceForm, status: e.target.value })}
                className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-blue-600 focus-visible:outline-none bg-white"
              >
                <option value="current">{t("verify.library.statusCurrent", "Current / In Force")}</option>
                <option value="superseded">{t("verify.library.statusSuperseded", "Superseded")}</option>
                <option value="amended">{t("verify.library.statusAmended", "Amended")}</option>
                <option value="proposed">{t("verify.library.statusProposed", "Draft / Proposed")}</option>
                <option value="unknown">{t("verify.library.statusUnknown", "Unknown")}</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                {t("verify.library.formSeriesId", "Policy Series ID (optional)")}
              </label>
              <input
                type="text"
                value={sourceForm.series_id}
                onChange={(e) => setSourceForm({ ...sourceForm, series_id: e.target.value })}
                placeholder="e.g. SOLAR-SUBSIDY-TN"
                className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-blue-600 focus-visible:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                {t("verify.library.formSupersededBy", "Superseded By (Source ID)")}
              </label>
              <input
                type="text"
                value={sourceForm.superseded_by}
                onChange={(e) => setSourceForm({ ...sourceForm, superseded_by: e.target.value })}
                placeholder="UUID of newer document"
                className="w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-blue-600 focus-visible:outline-none"
              />
            </div>
          </div>

          {/* File Dropzone */}
          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              {t("verify.library.formFile", "Official PDF Document *")}
            </label>
            <FileDropzone
              onFileSelect={(file) => setSourceFile(file)}
              acceptedFormat=".pdf"
              maxSizeMB={25}
            />
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsAddSourceOpen(false)}
              disabled={uploadingSource}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              disabled={uploadingSource || !sourceFile}
              className="gap-2"
            >
              {uploadingSource ? (
                <>
                  <Spinner size="sm" />
                  {t("verify.library.uploading", "Uploading & Indexing...")}
                </>
              ) : (
                t("verify.library.submitUpload", "Upload & Build Index")
              )}
            </Button>
          </div>
        </form>
      </Modal>

      {/* ============================================================== */}
      {/* MODAL: PAST VERIFICATIONS                                      */}
      {/* ============================================================== */}
      <Modal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        title={t("verify.history.title", "Past Fact Verifications")}
      >
        <div className="space-y-3 max-h-[60vh] overflow-y-auto">
          {pastVerifications.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">
              {t("verify.history.empty", "No past verifications recorded yet.")}
            </p>
          ) : (
            pastVerifications.map((item) => (
              <div
                key={item.verification_id}
                className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between gap-3 hover:bg-slate-100/70 transition-colors"
              >
                <div className="space-y-1 text-left min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge variant={item.overall_verdict} size="sm">
                      {item.overall_verdict}
                    </Badge>
                    <span className="text-[11px] text-slate-400 font-mono">
                      {item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                  <p className="text-xs text-slate-800 font-medium truncate max-w-sm">
                    {item.claim_snippet}
                  </p>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      loadVerification(item.verification_id);
                      setIsHistoryOpen(false);
                    }}
                    className="text-xs py-1"
                  >
                    {t("verify.history.view", "View")}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => removeVerification(item.verification_id)}
                    className="text-xs py-1 text-rose-600 hover:bg-rose-50 hover:border-rose-300"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </Modal>

      {/* ============================================================== */}
      {/* MODAL: DELETE CONFIRMATION                                     */}
      {/* ============================================================== */}
      <Modal
        isOpen={!!deletingSourceId}
        onClose={() => setDeletingSourceId(null)}
        title={t("verify.library.deleteSource", "Delete Official Source")}
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-700">
            {t(
              "verify.library.deleteConfirm",
              "Are you sure you want to remove this official document from the library? Any associated vector index will also be deleted."
            )}
          </p>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="outline" size="sm" onClick={() => setDeletingSourceId(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => handleDeleteSource(deletingSourceId)}
            >
              {t("verify.library.deleteSource", "Delete Source")}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

/**
 * Subcomponent: ClaimEvaluationCard
 * Renders individual evaluated claim with verdict basis, aspects, fact comparisons, and evidence cards.
 */
function ClaimEvaluationCard({ item, t }) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <Card className="border-slate-200 shadow-xs">
      {/* Card Header / Summary Bar */}
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        className="p-4 bg-slate-50/70 border-b border-slate-200/80 flex items-center justify-between gap-3 cursor-pointer hover:bg-slate-100/50 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <Badge variant={item.verdict} size="sm">
            {t(`verify.verdicts.${item.verdict}`, item.verdict.toUpperCase())}
          </Badge>
          <span className="text-sm font-semibold text-slate-900 truncate">
            {item.claim_text}
          </span>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {item.verdict_basis && (
            <span className="text-[11px] font-mono text-slate-400 bg-white px-2 py-0.5 rounded border border-slate-200">
              {item.verdict_basis}
            </span>
          )}
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </div>

      {/* Card Body */}
      {isExpanded && (
        <CardContent className="p-5 space-y-4">
          {/* Explanation */}
          <p className="text-sm text-slate-700 leading-relaxed">
            {item.explanation}
          </p>

          {/* Matched & Unmatched Aspects */}
          {(item.matched_aspects?.length > 0 || item.unmatched_aspects?.length > 0) && (
            <div className="flex flex-wrap gap-2 pt-1">
              {item.matched_aspects?.map((aspect, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200"
                >
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                  {aspect}
                </span>
              ))}
              {item.unmatched_aspects?.map((aspect, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 text-[11px] font-medium px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200"
                >
                  <HelpCircle className="w-3 h-3 text-slate-400" />
                  {aspect}
                </span>
              ))}
            </div>
          )}

          {/* Time Sensitivity Warning */}
          {item.time_sensitivity_warning && (
            <Alert variant="warning" title={t("verify.cards.timeWarning", "Time Sensitivity Warning")}>
              {item.time_sensitivity_warning}
            </Alert>
          )}

          {/* Conflicting Sources Warning */}
          {item.conflicting_sources && (
            <Alert variant="warning" title={t("verify.cards.conflictingWarning", "Conflicting Sources Warning")}>
              Different official government records state conflicting parameters for this claim.
            </Alert>
          )}

          {/* Superseded By Outdated Notice */}
          {item.superseded_by_info && (
            <div className="p-4 bg-purple-50/60 border border-purple-200 rounded-lg space-y-3">
              <div className="flex items-center gap-2 text-purple-900 font-semibold text-xs uppercase tracking-wider">
                <Clock className="w-4 h-4 text-purple-700" />
                {t("verify.cards.outdatedNotice", "Superseded Policy Notice")}
              </div>
              <p className="text-xs text-purple-800">
                {t(
                  "verify.cards.outdatedDesc",
                  "This claim was governed by an earlier policy which has been officially replaced by a newer government order."
                )}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-2.5 bg-white rounded border border-purple-200">
                  <span className="text-slate-400 block mb-0.5">Older Document:</span>
                  <span className="font-semibold text-slate-800">
                    {item.superseded_by_info.older_source_title}
                  </span>
                  {item.superseded_by_info.older_quote && (
                    <blockquote className="mt-1.5 pl-2 border-l-2 border-slate-300 italic text-slate-600">
                      "{item.superseded_by_info.older_quote}"
                    </blockquote>
                  )}
                </div>
                <div className="p-2.5 bg-white rounded border border-purple-300">
                  <span className="text-purple-600 block mb-0.5 font-semibold">
                    Newer Active Document ({item.superseded_by_info.newer_effective_date || "Current"}):
                  </span>
                  <span className="font-bold text-purple-950">
                    {item.superseded_by_info.newer_source_title}
                  </span>
                  {item.superseded_by_info.newer_quote && (
                    <blockquote className="mt-1.5 pl-2 border-l-2 border-purple-400 italic text-purple-900 font-medium">
                      "{item.superseded_by_info.newer_quote}"
                    </blockquote>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Supporting Evidence Cards */}
          {item.supporting_evidence?.length > 0 && (
            <div className="space-y-2 pt-2">
              <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                {t("verify.cards.supporting", `Supporting Evidence (${item.supporting_evidence.length})`)}
              </span>
              <div className="space-y-2">
                {item.supporting_evidence.map((ev, i) => (
                  <EvidenceItemCard key={i} ev={ev} type="supporting" t={t} />
                ))}
              </div>
            </div>
          )}

          {/* Contradicting Evidence Cards */}
          {item.contradicting_evidence?.length > 0 && (
            <div className="space-y-2 pt-2">
              <span className="text-xs font-bold text-rose-800 uppercase tracking-wider flex items-center gap-1.5">
                <XCircle className="w-3.5 h-3.5 text-rose-600" />
                {t("verify.cards.contradicting", `Contradicting Evidence (${item.contradicting_evidence.length})`)}
              </span>
              <div className="space-y-2">
                {item.contradicting_evidence.map((ev, i) => (
                  <EvidenceItemCard key={i} ev={ev} type="contradicting" t={t} />
                ))}
              </div>
            </div>
          )}

          {/* Related Evidence Cards */}
          {item.related_evidence?.length > 0 && (
            <div className="space-y-2 pt-2">
              <span className="text-xs font-bold text-slate-600 uppercase tracking-wider flex items-center gap-1.5">
                <HelpCircle className="w-3.5 h-3.5 text-slate-400" />
                {t("verify.cards.related", `Related Context / Inconclusive (${item.related_evidence.length})`)}
              </span>
              <div className="space-y-2">
                {item.related_evidence.map((ev, i) => (
                  <EvidenceItemCard key={i} ev={ev} type="related" t={t} />
                ))}
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

/**
 * Subcomponent: EvidenceItemCard
 * Renders an evidence snippet with source tags, page reference, verified verbatim quote, and fact comparisons.
 */
function EvidenceItemCard({ ev, type, t }) {
  const isOfficial = ev.collection === "official";

  return (
    <div
      className={`p-3.5 rounded-lg border text-left space-y-2 transition-colors ${
        type === "supporting"
          ? "bg-emerald-50/30 border-emerald-200"
          : type === "contradicting"
          ? "bg-rose-50/30 border-rose-200"
          : "bg-slate-50 border-slate-200"
      }`}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap text-xs">
        <div className="flex items-center gap-2">
          <Badge variant={isOfficial ? "primary" : "outline"} size="sm">
            {isOfficial ? t("verify.cards.officialBadge", "Official Record") : t("verify.cards.userDocBadge", "User Document")}
          </Badge>
          <span className="font-semibold text-slate-900">{ev.source_title}</span>
          <span className="text-slate-400 font-mono">p. {ev.page_number}</span>
        </div>

        {ev.source_url && (
          <a
            href={ev.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 hover:underline flex items-center gap-1 text-[11px] font-medium"
          >
            <ExternalLink className="w-3 h-3" />
            {t("verify.cards.externalLink", "Open Official Record")}
          </a>
        )}
      </div>

      {/* Verified Verbatim Quote */}
      {ev.quote && (
        <div className="pl-3 border-l-2 border-blue-500 py-1 bg-white/80 rounded-r p-2 text-xs text-slate-800">
          <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider block mb-0.5">
            {t("verify.cards.quote", "Verified Verbatim Quote:")}
          </span>
          <p className="italic">"{ev.quote}"</p>
        </div>
      )}

      {/* Fact Comparisons Table if present */}
      {ev.fact_comparisons?.length > 0 && (
        <div className="pt-1 overflow-x-auto">
          <table className="w-full text-left text-[11px] text-slate-700 bg-white rounded border border-slate-200 overflow-hidden">
            <thead className="bg-slate-100/70 border-b border-slate-200 text-slate-600 font-semibold uppercase">
              <tr>
                <th className="p-1.5 pl-2">Fact Type</th>
                <th className="p-1.5">Claim Asserted</th>
                <th className="p-1.5">Official Value</th>
                <th className="p-1.5 pr-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {ev.fact_comparisons.map((fc, idx) => (
                <tr key={idx}>
                  <td className="p-1.5 pl-2 font-medium capitalize">{fc.fact_type}</td>
                  <td className="p-1.5">{fc.claim_value}</td>
                  <td className="p-1.5 font-semibold text-slate-900">{fc.evidence_value}</td>
                  <td className="p-1.5 pr-2">
                    <Badge
                      variant={
                        fc.status === "match"
                          ? "success"
                          : fc.status === "mismatch"
                          ? "danger"
                          : "outline"
                      }
                      size="sm"
                      className="text-[10px] py-0 px-1.5"
                    >
                      {fc.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
