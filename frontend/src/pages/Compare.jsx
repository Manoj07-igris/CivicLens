import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  GitCompare,
  ArrowLeftRight,
  AlertTriangle,
  Trash2,
  Copy,
  Check,
  Search,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  PlusCircle,
  MinusCircle,
  Edit3,
  Sparkles,
  Layers,
  History,
  FileCheck,
} from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { useLanguage } from "../hooks/useLanguage";
import { useToast } from "../hooks/useToast";
import { useDocuments } from "../hooks/useDocuments";
import { useComparison } from "../hooks/useComparison";
import { comparisonService } from "../services/comparisonService";

export function Compare() {
  const { t, language: uiLang } = useLanguage();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { documents, isLoading: isDocsLoading } = useDocuments();

  const {
    comparison,
    status,
    progress,
    currentStep,
    error: compareError,
    loading: isCompareLoading,
    startComparison,
    fetchComparison,
  } = useComparison();

  // Slot states initialized directly from search parameters if present
  const [oldDocId, setOldDocId] = useState(() => searchParams.get("old") || "");
  const [newDocId, setNewDocId] = useState(() => searchParams.get("new") || "");
  const [targetLang, setTargetLang] = useState(uiLang === "ta" ? "ta" : "en");
  const [forceRecompute, setForceRecompute] = useState(false);

  // View & Filter states
  const [viewMode, setViewMode] = useState("cards"); // 'cards' | 'table'
  const [copied, setCopied] = useState(false);
  const [showMinorDiffs, setShowMinorDiffs] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedImportance, setSelectedImportance] = useState("all");
  const [selectedType, setSelectedType] = useState("all");
  const [materialOnly, setMaterialOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  // Past comparisons modal state
  const [isPastModalOpen, setIsPastModalOpen] = useState(false);
  const [pastList, setPastList] = useState([]);
  const [isLoadingPast, setIsLoadingPast] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  // Filter ready documents
  const readyDocs = useMemo(() => {
    return (documents || []).filter(
      (d) => d.status === "ready" || d.status === "ready_with_warnings"
    );
  }, [documents]);

  const selectedOldDoc = useMemo(
    () => readyDocs.find((d) => d.document_id === oldDocId),
    [readyDocs, oldDocId]
  );
  const selectedNewDoc = useMemo(
    () => readyDocs.find((d) => d.document_id === newDocId),
    [readyDocs, newDocId]
  );

  // 1. Fetch comparison when ?id= query param is present
  useEffect(() => {
    const queryCompId = searchParams.get("id");
    if (queryCompId) {
      fetchComparison(queryCompId);
    }
  }, [searchParams, fetchComparison]);

  // Sync document slots when comparison report loads
  useEffect(() => {
    if (comparison) {
      if (comparison.old_document_id && !oldDocId) {
        // oxlint-disable-next-line react/set-state-in-effect
        setOldDocId(comparison.old_document_id);
      }
      if (comparison.new_document_id && !newDocId) {
        // oxlint-disable-next-line react/set-state-in-effect
        setNewDocId(comparison.new_document_id);
      }
    }
  }, [comparison, oldDocId, newDocId]);

  // Handle Swap
  const handleSwap = () => {
    setOldDocId(newDocId);
    setNewDocId(oldDocId);
  };

  // Start comparison action
  const handleStartCompare = async () => {
    if (!oldDocId || !newDocId) {
      showToast({ message: t("compare.empty.selectBothToStart"), type: "warning" });
      return;
    }
    if (oldDocId === newDocId) {
      showToast({ message: "Cannot compare a document with itself.", type: "error" });
      return;
    }

    try {
      const job = await startComparison({
        oldDocumentId: oldDocId,
        newDocumentId: newDocId,
        language: targetLang,
        force: forceRecompute,
      });
      if (job?.comparison_id) {
        setSearchParams({ id: job.comparison_id }, { replace: true });
      }
    } catch (err) {
      showToast({ message: err.message || "Failed to start comparison", type: "error" });
    }
  };

  // Copy Executive Summary
  const handleCopySummary = async () => {
    const textToCopy = comparison?.overall_summary;
    if (!textToCopy) return;

    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      showToast({ message: t("compare.copied"), type: "success" });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      showToast({ message: "Failed to copy text", type: "error" });
    }
  };

  // Load Past Comparisons
  const handleOpenPastModal = async () => {
    setIsPastModalOpen(true);
    setIsLoadingPast(true);
    try {
      const res = await comparisonService.listComparisons(30);
      setPastList(res.comparisons || []);
    } catch (err) {
      showToast({ message: err.message || "Failed to load past comparisons", type: "error" });
    } finally {
      setIsLoadingPast(false);
    }
  };

  const handleDeletePast = async (compId) => {
    try {
      setDeletingId(compId);
      await comparisonService.deleteComparison(compId);
      setPastList((prev) => prev.filter((item) => item.comparison_id !== compId));
      showToast({ message: "Comparison report deleted.", type: "info" });
      if (comparison?.comparison_id === compId) {
        setSearchParams({}, { replace: true });
        window.location.reload();
      }
    } catch (err) {
      showToast({ message: err.message || "Failed to delete comparison", type: "error" });
    } finally {
      setDeletingId(null);
    }
  };

  // Filtered change items
  const filteredChanges = useMemo(() => {
    if (!comparison?.changes) return [];
    return comparison.changes.filter((c) => {
      if (materialOnly && !c.is_material) return false;
      if (selectedCategory !== "all" && c.category !== selectedCategory) return false;
      if (selectedImportance !== "all" && c.importance !== selectedImportance) return false;
      if (selectedType !== "all" && c.change_type !== selectedType) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const sumMatch = (c.plain_summary || "").toLowerCase().includes(q);
        const impMatch = (c.practical_impact || "").toLowerCase().includes(q);
        const oldMatch = (c.old?.full_text || "").toLowerCase().includes(q);
        const newMatch = (c.new?.full_text || "").toLowerCase().includes(q);
        return sumMatch || impMatch || oldMatch || newMatch;
      }
      return true;
    });
  }, [
    comparison,
    materialOnly,
    selectedCategory,
    selectedImportance,
    selectedType,
    searchQuery,
  ]);

  // Jump to Document Viewer
  const handleJumpToDocument = (docId, page) => {
    navigate(`/documents?id=${docId}&page=${page}`);
  };

  // Render Word Diff
  const renderWordDiff = useCallback((wordDiff) => {
    if (!wordDiff || wordDiff.length === 0) return null;
    return (
      <div className="text-xs leading-relaxed font-mono bg-white p-2.5 rounded-lg border border-slate-200">
        {wordDiff.map((op, idx) => {
          if (op.op === "equal") {
            return <span key={idx} className="text-slate-700">{op.new_text || op.old_text}</span>;
          }
          if (op.op === "delete") {
            return (
              <span
                key={idx}
                className="bg-rose-100 text-rose-800 line-through px-1 py-0.5 rounded mx-0.5"
                title="Removed from old version"
              >
                {op.old_text}
              </span>
            );
          }
          if (op.op === "insert") {
            return (
              <span
                key={idx}
                className="bg-emerald-100 text-emerald-900 font-semibold underline decoration-emerald-500 px-1 py-0.5 rounded mx-0.5"
                title="Added in new version"
              >
                {op.new_text}
              </span>
            );
          }
          if (op.op === "replace") {
            return (
              <span key={idx} className="inline-flex flex-wrap items-center gap-1 mx-0.5">
                <span className="bg-rose-100 text-rose-800 line-through px-1 py-0.5 rounded" title="Removed">
                  {op.old_text}
                </span>
                <span className="bg-emerald-100 text-emerald-900 font-semibold underline decoration-emerald-500 px-1 py-0.5 rounded" title="Added">
                  {op.new_text}
                </span>
              </span>
            );
          }
          return null;
        })}
      </div>
    );
  }, []);

  const counts = comparison?.counts || {
    modified: 0,
    added: 0,
    removed: 0,
    formatting_only: 0,
    moved: 0,
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title={t("compare.title")}
          description={t("compare.subtitle")}
          badge={<Badge variant="primary">Module 2</Badge>}
        />
        <Button
          variant="secondary"
          size="sm"
          onClick={handleOpenPastModal}
          className="self-start sm:self-center flex items-center gap-2"
        >
          <History className="w-4 h-4 text-slate-600" />
          {t("compare.pastComparisons.button")}
        </Button>
      </div>

      {/* Document Selection Card */}
      <div className="bg-white rounded-xl border border-slate-200/80 shadow-xs p-5 space-y-4">
        <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <Layers className="w-4 h-4 text-blue-600" />
          {t("compare.selectDocuments")}
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-[1fr,auto,1fr] items-center gap-4">
          {/* Slot 1: Older Version */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-slate-600">
              {t("compare.olderVersion")}
            </label>
            <div className="relative">
              <select
                value={oldDocId}
                onChange={(e) => setOldDocId(e.target.value)}
                disabled={isDocsLoading || isCompareLoading}
                className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-300 rounded-lg py-2.5 px-3 pr-8 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all disabled:opacity-60"
              >
                <option value="">{t("compare.selectOldPlaceholder")}</option>
                {readyDocs.map((doc) => (
                  <option key={doc.document_id} value={doc.document_id}>
                    {doc.filename} ({doc.page_count} p. • {doc.language?.toUpperCase() || "EN"})
                  </option>
                ))}
              </select>
            </div>
            {selectedOldDoc && (
              <div className="flex items-center gap-2 text-[11px] text-slate-500 pt-0.5">
                <FileCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span className="truncate">{selectedOldDoc.filename}</span>
                <span className="font-mono bg-slate-100 px-1 rounded">
                  {selectedOldDoc.page_count} pages
                </span>
                {selectedOldDoc.ocr_performed && (
                  <Badge variant="warning" className="text-[10px] py-0">OCR</Badge>
                )}
              </div>
            )}
          </div>

          {/* Swap Button */}
          <div className="flex justify-center md:pt-4">
            <button
              type="button"
              onClick={handleSwap}
              disabled={isCompareLoading || (!oldDocId && !newDocId)}
              title={t("compare.swap")}
              className="p-2.5 rounded-full border border-slate-300 bg-white hover:bg-slate-100 active:scale-95 text-slate-600 transition-all shadow-xs disabled:opacity-40"
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
          </div>

          {/* Slot 2: Newer Version */}
          <div className="space-y-1.5">
            <label className="block text-xs font-medium text-slate-600">
              {t("compare.newerVersion")}
            </label>
            <div className="relative">
              <select
                value={newDocId}
                onChange={(e) => setNewDocId(e.target.value)}
                disabled={isDocsLoading || isCompareLoading}
                className="w-full text-xs sm:text-sm bg-slate-50 border border-slate-300 rounded-lg py-2.5 px-3 pr-8 text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all disabled:opacity-60"
              >
                <option value="">{t("compare.selectNewPlaceholder")}</option>
                {readyDocs.map((doc) => (
                  <option key={doc.document_id} value={doc.document_id}>
                    {doc.filename} ({doc.page_count} p. • {doc.language?.toUpperCase() || "EN"})
                  </option>
                ))}
              </select>
            </div>
            {selectedNewDoc && (
              <div className="flex items-center gap-2 text-[11px] text-slate-500 pt-0.5">
                <FileCheck className="w-3.5 h-3.5 text-blue-600" />
                <span className="truncate">{selectedNewDoc.filename}</span>
                <span className="font-mono bg-slate-100 px-1 rounded">
                  {selectedNewDoc.page_count} pages
                </span>
                {selectedNewDoc.ocr_performed && (
                  <Badge variant="warning" className="text-[10px] py-0">OCR</Badge>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Validation Warnings */}
        {oldDocId && newDocId && oldDocId === newDocId && (
          <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-lg text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span>Cannot compare a document with itself. Please select two different policy circulars.</span>
          </div>
        )}

        {/* Action Controls Bar */}
        <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-t border-slate-100">
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <span>Language:</span>
              <select
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
                disabled={isCompareLoading}
                className="bg-slate-50 border border-slate-300 rounded px-2 py-1 text-xs text-slate-800"
              >
                <option value="auto">Auto-detect</option>
                <option value="en">English (EN)</option>
                <option value="ta">தமிழ் (Tamil)</option>
              </select>
            </label>

            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={forceRecompute}
                onChange={(e) => setForceRecompute(e.target.checked)}
                disabled={isCompareLoading}
                className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
              />
              <span>Force re-analyze</span>
            </label>
          </div>

          <Button
            variant="primary"
            size="md"
            onClick={handleStartCompare}
            disabled={!oldDocId || !newDocId || oldDocId === newDocId || isCompareLoading}
            className="flex items-center justify-center gap-2 min-w-[170px]"
          >
            {isCompareLoading ? (
              <>
                <Spinner size="sm" className="text-white" />
                <span>{t("compare.comparing")}</span>
              </>
            ) : (
              <>
                <GitCompare className="w-4 h-4" />
                <span>{t("compare.compareBtn")}</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Live Progress Banner */}
      {isCompareLoading && (
        <div className="bg-blue-50/90 border border-blue-200 rounded-xl p-5 shadow-xs space-y-3 animate-fade-in">
          <div className="flex items-center justify-between text-xs text-blue-900 font-medium">
            <div className="flex items-center gap-2">
              <Spinner size="sm" className="text-blue-600" />
              <span>{currentStep || t("compare.stages.aligning")}</span>
            </div>
            <span className="font-mono">{progress}%</span>
          </div>
          <div className="w-full bg-blue-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.max(5, progress)}%` }}
            />
          </div>
        </div>
      )}

      {/* Comparison Error Box */}
      {compareError && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-900 text-sm flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <h4 className="font-semibold text-rose-950">Comparison Error</h4>
            <p className="text-xs text-rose-800 leading-relaxed">{compareError}</p>
          </div>
        </div>
      )}

      {/* Completed Comparison Report View */}
      {comparison && status === "completed" && (
        <div className="space-y-6 animate-fade-in">
          {/* Executive Summary Card */}
          <div className="bg-linear-to-br from-white to-slate-50 rounded-xl border border-slate-200/90 shadow-xs p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200/70 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-500 flex-shrink-0" />
                <h3 className="text-base font-bold text-slate-900">
                  {t("compare.executiveSummary")}
                </h3>
                <Badge variant="primary" className="text-xs">
                  {comparison.analysis_status === "completed_with_warnings" ? "Completed with Notices" : "Verified Analysis"}
                </Badge>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="xs"
                  onClick={handleCopySummary}
                  className="flex items-center gap-1.5 text-xs text-slate-700"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copied ? t("compare.copied") : t("compare.copySummary")}</span>
                </Button>

                {/* View Mode Toggle */}
                <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs">
                  <button
                    type="button"
                    onClick={() => setViewMode("cards")}
                    className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                      viewMode === "cards" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {t("compare.viewDetailedCards")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("table")}
                    className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                      viewMode === "table" ? "bg-white text-slate-900 shadow-xs" : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    {t("compare.viewSummaryTable")}
                  </button>
                </div>
              </div>
            </div>

            {/* Plain Summary Content */}
            <p className="text-sm leading-relaxed text-slate-800 whitespace-pre-line font-serif">
              {comparison.overall_summary || "Comparison completed successfully."}
            </p>

            {/* System Warnings (if any) */}
            {comparison.warnings && comparison.warnings.length > 0 && (
              <div className="p-3 bg-amber-50/90 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1">
                {comparison.warnings.map((w, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                    <span>{w}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Quantitative Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
              <span className="text-[11px] font-medium text-slate-500 block truncate">
                {t("compare.summaryMetrics.total")}
              </span>
              <span className="text-xl font-bold text-slate-900 mt-1 block">
                {comparison.changes?.length || 0}
              </span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-blue-200/80 shadow-2xs bg-blue-50/30">
              <span className="text-[11px] font-medium text-blue-700 block truncate">
                {t("compare.summaryMetrics.modified")}
              </span>
              <span className="text-xl font-bold text-blue-900 mt-1 block">
                {counts.modified}
              </span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-emerald-200/80 shadow-2xs bg-emerald-50/30">
              <span className="text-[11px] font-medium text-emerald-700 block truncate">
                {t("compare.summaryMetrics.added")}
              </span>
              <span className="text-xl font-bold text-emerald-900 mt-1 block">
                {counts.added}
              </span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-rose-200/80 shadow-2xs bg-rose-50/30">
              <span className="text-[11px] font-medium text-rose-700 block truncate">
                {t("compare.summaryMetrics.removed")}
              </span>
              <span className="text-xl font-bold text-rose-900 mt-1 block">
                {counts.removed}
              </span>
            </div>

            <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs col-span-2 sm:col-span-1">
              <span className="text-[11px] font-medium text-slate-500 block truncate">
                {t("compare.summaryMetrics.minor")}
              </span>
              <span className="text-xl font-bold text-slate-700 mt-1 block">
                {comparison.minor_differences_count || 0}
              </span>
            </div>
          </div>

          {/* Filter Controls Bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-2xs flex flex-wrap items-center justify-between gap-3 text-xs">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[200px] max-w-xs">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search changes..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-800 focus:outline-hidden focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Category Filter */}
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700"
              >
                <option value="all">{t("compare.allCategories")}</option>
                <option value="eligibility">{t("compare.categories.eligibility")}</option>
                <option value="deadline">{t("compare.categories.deadline")}</option>
                <option value="amount_benefit">{t("compare.categories.amount_benefit")}</option>
                <option value="required_documents">{t("compare.categories.required_documents")}</option>
                <option value="conditions_rules">{t("compare.categories.conditions_rules")}</option>
                <option value="procedure">{t("compare.categories.procedure")}</option>
                <option value="definitions_scope">{t("compare.categories.definitions_scope")}</option>
                <option value="other">{t("compare.categories.other")}</option>
              </select>

              {/* Impact Level Filter */}
              <select
                value={selectedImportance}
                onChange={(e) => setSelectedImportance(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700"
              >
                <option value="all">{t("compare.allImportances")}</option>
                <option value="high">{t("compare.importance.high")}</option>
                <option value="medium">{t("compare.importance.medium")}</option>
                <option value="low">{t("compare.importance.low")}</option>
              </select>

              {/* Type Filter */}
              <select
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                className="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700"
              >
                <option value="all">{t("compare.allTypes")}</option>
                <option value="modified">{t("compare.types.modified")}</option>
                <option value="added">{t("compare.types.added")}</option>
                <option value="removed">{t("compare.types.removed")}</option>
              </select>

              {/* Material Only Toggle */}
              <label className="flex items-center gap-1.5 cursor-pointer text-slate-700 ml-1">
                <input
                  type="checkbox"
                  checked={materialOnly}
                  onChange={(e) => setMaterialOnly(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                />
                <span>{t("compare.materialOnly")}</span>
              </label>
            </div>
          </div>

          {/* Detailed Cards View */}
          {viewMode === "cards" && (
            <div className="space-y-4">
              {filteredChanges.length === 0 ? (
                <div className="text-center py-10 bg-white rounded-xl border border-slate-200 text-slate-500 text-sm space-y-1">
                  <p className="font-semibold text-slate-700">{t("compare.empty.noFilteredResults")}</p>
                  <p className="text-xs">Try resetting your filter parameters or search query.</p>
                </div>
              ) : (
                filteredChanges.map((change) => {
                  const isModified = change.change_type === "modified";
                  const isAdded = change.change_type === "added";
                  const isRemoved = change.change_type === "removed";

                  return (
                    <div
                      key={change.change_id}
                      className="bg-white rounded-xl border border-slate-200 shadow-2xs p-5 space-y-4 hover:border-slate-300 transition-all"
                    >
                      {/* Card Header */}
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                        <div className="flex flex-wrap items-center gap-2">
                          {/* Type Badge */}
                          {isAdded && (
                            <Badge variant="success" className="flex items-center gap-1 text-xs">
                              <PlusCircle className="w-3.5 h-3.5" />
                              <span>{t("compare.types.added")}</span>
                            </Badge>
                          )}
                          {isRemoved && (
                            <Badge variant="danger" className="flex items-center gap-1 text-xs">
                              <MinusCircle className="w-3.5 h-3.5" />
                              <span>{t("compare.types.removed")}</span>
                            </Badge>
                          )}
                          {isModified && (
                            <Badge variant="primary" className="flex items-center gap-1 text-xs">
                              <Edit3 className="w-3.5 h-3.5" />
                              <span>{t("compare.types.modified")}</span>
                            </Badge>
                          )}

                          {/* Importance Badge */}
                          <Badge
                            variant={
                              change.importance === "high"
                                ? "danger"
                                : change.importance === "medium"
                                ? "warning"
                                : "neutral"
                            }
                            className="text-[11px]"
                          >
                            {t(`compare.importance.${change.importance}`)}
                          </Badge>

                          {/* Category Badge */}
                          <span className="text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md font-medium">
                            {t(`compare.categories.${change.category}`) || change.category}
                          </span>
                        </div>

                        {/* Page Coordinates */}
                        <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
                          {change.old?.page && (
                            <button
                              type="button"
                              onClick={() => handleJumpToDocument(comparison.old_document_id, change.old.page)}
                              className="hover:text-blue-600 hover:underline flex items-center gap-1"
                              title="Inspect old document page"
                            >
                              <span>Old p.{change.old.page}</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                          {change.old?.page && change.new?.page && <span>→</span>}
                          {change.new?.page && (
                            <button
                              type="button"
                              onClick={() => handleJumpToDocument(comparison.new_document_id, change.new.page)}
                              className="hover:text-blue-600 hover:underline flex items-center gap-1 text-blue-700 font-semibold"
                              title="Inspect new document page"
                            >
                              <span>New p.{change.new.page}</span>
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Plain Summary */}
                      <div className="space-y-1">
                        <h4 className="text-sm font-bold text-slate-900 leading-snug">
                          {change.plain_summary}
                        </h4>
                        {change.practical_impact && (
                          <div className="text-xs text-slate-700 bg-blue-50/50 p-2.5 rounded-lg border border-blue-100/80">
                            <span className="font-semibold text-blue-900 block mb-0.5">
                              {t("compare.changeCard.practicalImpact")}:
                            </span>
                            <span>{change.practical_impact}</span>
                          </div>
                        )}
                      </div>

                      {/* Authoritative Value Shifts Chips */}
                      {change.fact_changes && change.fact_changes.length > 0 && (
                        <div className="space-y-1.5 pt-1">
                          <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                            {t("compare.changeCard.factDelta")}
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {change.fact_changes.map((fc, fIdx) => (
                              <div
                                key={fIdx}
                                className="inline-flex items-center gap-1.5 bg-slate-100 border border-slate-200 text-slate-800 px-2.5 py-1 rounded-md text-xs font-mono"
                              >
                                <span className="font-semibold text-slate-600 capitalize">{fc.fact_type}:</span>
                                <span className="text-rose-700 line-through">{fc.old_value || "[none]"}</span>
                                <span className="text-slate-400">→</span>
                                <span className="text-emerald-700 font-bold">{fc.new_value || "[none]"}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Side-by-Side Clause Diff or Word Diff */}
                      <div className="space-y-1.5">
                        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                          Word-Level Verbatim Comparison
                        </span>
                        {change.word_diff && change.word_diff.length > 0 ? (
                          renderWordDiff(change.word_diff)
                        ) : (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                            <div className="bg-rose-50/40 p-2.5 rounded-lg border border-rose-100 text-slate-700">
                              <span className="font-semibold text-rose-900 block mb-1">
                                {t("compare.changeCard.before")} (p.{change.old?.page || "?"})
                              </span>
                              <p className="font-serif text-[11px]">{change.old?.full_text || "[Clause not present in old version]"}</p>
                            </div>
                            <div className="bg-emerald-50/40 p-2.5 rounded-lg border border-emerald-100 text-slate-700">
                              <span className="font-semibold text-emerald-900 block mb-1">
                                {t("compare.changeCard.after")} (p.{change.new?.page || "?"})
                              </span>
                              <p className="font-serif text-[11px]">{change.new?.full_text || "[Clause removed in new version]"}</p>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Override Caution Notice */}
                      {change.ai_flagged_minor_but_facts_changed && (
                        <div className="p-2 bg-amber-50 border border-amber-200 rounded text-[11px] text-amber-900 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" />
                          <span>{t("compare.changeCard.flaggedMinorButFact")}</span>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Summary Table View */}
          {viewMode === "table" && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-700 font-semibold">
                      <th className="py-3 px-3">Type</th>
                      <th className="py-3 px-3">Category</th>
                      <th className="py-3 px-4">What Changed</th>
                      <th className="py-3 px-3">Practical Impact</th>
                      <th className="py-3 px-2">Old p.</th>
                      <th className="py-3 px-2">New p.</th>
                      <th className="py-3 px-3">Impact</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {filteredChanges.map((change) => (
                      <tr key={change.change_id} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-3 px-3 font-semibold">
                          <span
                            className={
                              change.change_type === "added"
                                ? "text-emerald-700"
                                : change.change_type === "removed"
                                ? "text-rose-700"
                                : "text-blue-700"
                            }
                          >
                            {change.change_type.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-slate-600 capitalize">
                          {change.category.replace("_", " ")}
                        </td>
                        <td className="py-3 px-4 font-medium text-slate-900 max-w-xs">
                          {change.plain_summary}
                        </td>
                        <td className="py-3 px-3 text-slate-700 max-w-xs">
                          {change.practical_impact || "—"}
                        </td>
                        <td className="py-3 px-2 font-mono text-slate-500">
                          {change.old?.page ? `p.${change.old.page}` : "—"}
                        </td>
                        <td className="py-3 px-2 font-mono text-slate-500">
                          {change.new?.page ? `p.${change.new.page}` : "—"}
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant={
                              change.importance === "high"
                                ? "danger"
                                : change.importance === "medium"
                                ? "warning"
                                : "neutral"
                            }
                          >
                            {change.importance}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Minor Differences Collapsible Section */}
          {comparison.minor_differences && comparison.minor_differences.length > 0 && (
            <div className="bg-slate-50 rounded-xl border border-slate-200/90 overflow-hidden">
              <button
                type="button"
                onClick={() => setShowMinorDiffs((prev) => !prev)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-100/70 transition-colors"
              >
                <div className="space-y-0.5">
                  <h4 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                    <span>
                      {t("compare.minorDiffs.title", {
                        count: comparison.minor_differences.length,
                      })}
                    </span>
                  </h4>
                  <p className="text-xs text-slate-500">
                    {t("compare.minorDiffs.description")}
                  </p>
                </div>
                {showMinorDiffs ? (
                  <ChevronUp className="w-4 h-4 text-slate-500" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-slate-500" />
                )}
              </button>

              {showMinorDiffs && (
                <div className="p-4 pt-0 space-y-2 border-t border-slate-200/80 divide-y divide-slate-200/60 text-xs">
                  {comparison.minor_differences.map((m) => (
                    <div key={m.item_id} className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="space-y-0.5 max-w-xl">
                        <span className="font-semibold text-slate-700 capitalize">
                          [{m.diff_type.replace("_", " ")}] {m.reason}
                        </span>
                        <p className="text-slate-500 font-serif text-[11px] truncate">
                          "{m.new_text || m.old_text}"
                        </p>
                      </div>
                      <span className="text-[11px] font-mono text-slate-400 self-start sm:self-auto">
                        {m.old_page ? `Old p.${m.old_page}` : ""} {m.new_page ? `New p.${m.new_page}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Empty State before any comparison */}
      {!comparison && status === "idle" && (
        <div className="bg-white rounded-xl border border-slate-200/80 p-12 text-center space-y-3">
          <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-full flex items-center justify-center mx-auto">
            <GitCompare className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-slate-900">
            {t("compare.title")}
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
            {t("compare.empty.selectBothToStart")}
          </p>
        </div>
      )}

      {/* Past Comparisons Modal */}
      <Modal
        isOpen={isPastModalOpen}
        onClose={() => setIsPastModalOpen(false)}
        title={t("compare.pastComparisons.title")}
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
          {isLoadingPast ? (
            <div className="py-12 flex justify-center">
              <Spinner size="md" className="text-blue-600" />
            </div>
          ) : pastList.length === 0 ? (
            <p className="text-center py-8 text-xs text-slate-500">
              {t("compare.empty.noPastComparisons")}
            </p>
          ) : (
            pastList.map((item) => (
              <div
                key={item.comparison_id}
                className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                    <span className="truncate max-w-[140px]">{item.old_document_name}</span>
                    <span className="text-slate-400">vs</span>
                    <span className="truncate max-w-[140px]">{item.new_document_name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500">
                    <span>{new Date(item.created_at).toLocaleDateString()}</span>
                    <span>•</span>
                    <Badge variant="primary" className="text-[10px] py-0">
                      {item.changes_count} changes
                    </Badge>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-auto">
                  <Button
                    variant="primary"
                    size="xs"
                    onClick={() => {
                      setIsPastModalOpen(false);
                      setSearchParams({ id: item.comparison_id });
                      fetchComparison(item.comparison_id);
                    }}
                  >
                    {t("compare.pastComparisons.view")}
                  </Button>
                  <Button
                    variant="danger"
                    size="xs"
                    disabled={deletingId === item.comparison_id}
                    onClick={() => handleDeletePast(item.comparison_id)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </div>
      </Modal>
    </div>
  );
}
