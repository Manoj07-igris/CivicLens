import React, { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import {
  FileText,
  UploadCloud,
  Eye,
  Trash2,
  ExternalLink,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  Search,
  BookOpen,
  Send,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Info,
} from "lucide-react";

import { PageHeader } from "../components/ui/PageHeader";
import { EmptyState } from "../components/ui/EmptyState";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/Card";
import { Alert } from "../components/ui/Alert";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { Skeleton } from "../components/ui/Skeleton";
import { FileDropzone } from "../components/ui/FileDropzone";
import { useLanguage } from "../hooks/useLanguage";
import { useDocuments } from "../hooks/useDocuments";
import { documentService } from "../services/documentService";

export function Documents() {
  const { t, language } = useLanguage();
  const {
    documents,
    capabilities,
    isLoading,
    isUploading,
    error,
    uploadFile,
    deleteDoc,
  } = useDocuments();

  // Detail Modal State
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(null);

  // Page Viewer State
  const [currentPageNumber, setCurrentPageNumber] = useState(1);
  const [currentPageData, setCurrentPageData] = useState(null);
  const [pageLoading, setPageLoading] = useState(false);

  // AI Summary State
  const [summaryData, setSummaryData] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState(null);
  const [summaryLanguage, setSummaryLanguage] = useState("auto");
  const [isCopied, setIsCopied] = useState(false);

  // RAG Q&A State (Phase 8)
  const [ragQuestion, setRagQuestion] = useState("");
  const [ragLoading, setRagLoading] = useState(false);
  const [ragStep, setRagStep] = useState("");
  const [ragError, setRagError] = useState(null);
  const [ragResult, setRagResult] = useState(null);
  const [ragLanguage, setRagLanguage] = useState("auto");
  const [showPassages, setShowPassages] = useState(false);
  const [isBuildingIndex, setIsBuildingIndex] = useState(false);

  // Delete Confirmation State
  const [docToDelete, setDocToDelete] = useState(null);

  useEffect(() => {
    document.title =
      language === "ta"
        ? "கொள்கை ஆவண நுண்ணறிவு – சிவிக்லென்ஸ்"
        : "Policy Document Intelligence – CivicLens";
  }, [language]);

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const formatDate = (isoString) => {
    if (!isoString) return "—";
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(language === "ta" ? "ta-IN" : "en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  // Open Document Detail Modal
  const handleInspectDocument = useCallback(async (docId) => {
    setSelectedDocId(docId);
    setDetailLoading(true);
    setDetailError(null);
    setCurrentPageNumber(1);
    setCurrentPageData(null);
    setSummaryData(null);
    setSummaryError(null);
    setRagQuestion("");
    setRagLoading(false);
    setRagStep("");
    setRagError(null);
    setRagResult(null);
    setShowPassages(false);

    try {
      const data = await documentService.getDocument(docId);
      setDetailData(data);

      // Load page 1 text
      setPageLoading(true);
      try {
        const page1 = await documentService.getDocumentPage(docId, 1);
        setCurrentPageData(page1);
      } catch (err) {
        console.warn("Could not load initial page 1:", err);
      } finally {
        setPageLoading(false);
      }
    } catch (err) {
      setDetailError(err.message || "Failed to load document details.");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Handle cross-page navigation from Assistant citations
  const location = useLocation();
  useEffect(() => {
    if (location.state?.documentId) {
      const targetDocId = location.state.documentId;
      const targetPage = location.state.pageNumber || 1;
      // oxlint-disable-next-line react/set-state-in-effect
      handleInspectDocument(targetDocId);
      if (targetPage > 1) {
        documentService
          .getDocumentPage(targetDocId, targetPage)
          .then((pageRec) => {
            setCurrentPageNumber(targetPage);
            setCurrentPageData(pageRec);
          })
          .catch((e) => console.warn("Failed to jump to page:", e));
      }
    }
  }, [location.state, handleInspectDocument]);

  // Fetch page text when page number changes
  const handlePageChange = useCallback(
    async (newPageNumber) => {
      if (!selectedDocId || !detailData) return;
      if (newPageNumber < 1 || newPageNumber > (detailData.page_count || 1)) return;

      setCurrentPageNumber(newPageNumber);
      setPageLoading(true);
      try {
        const pageRecord = await documentService.getDocumentPage(
          selectedDocId,
          newPageNumber
        );
        setCurrentPageData(pageRecord);
      } catch (err) {
        console.error("Failed to load page:", err);
      } finally {
        setPageLoading(false);
      }
    },
    [selectedDocId, detailData]
  );

  // Jump to specific page and scroll viewer into view
  const handleJumpToPage = useCallback(
    (pageNumber) => {
      handlePageChange(pageNumber);
      const viewerElem = document.getElementById("document-page-viewer");
      if (viewerElem) {
        viewerElem.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
    [handlePageChange]
  );

  // Ask RAG Question about Policy
  const handleAskQuestion = useCallback(
    async (overrideQuestion = null) => {
      const q = (overrideQuestion || ragQuestion).trim();
      if (!selectedDocId || !q) return;

      if (overrideQuestion) {
        setRagQuestion(overrideQuestion);
      }

      setRagLoading(true);
      setRagError(null);
      setRagStep(
        detailData?.index_status !== "indexed"
          ? t("documents.indexingNotice")
          : t("documents.searchingNotice")
      );

      const stepTimer = setTimeout(() => {
        setRagStep(t("documents.generatingNotice"));
      }, 1200);

      try {
        const response = await documentService.askDocument(
          selectedDocId,
          q,
          ragLanguage
        );
        setRagResult(response);
        if (detailData?.index_status !== "indexed") {
          const freshData = await documentService.getDocument(selectedDocId);
          setDetailData(freshData);
        }
      } catch (err) {
        setRagError(err.message || "Failed to generate answer for this policy.");
      } finally {
        clearTimeout(stepTimer);
        setRagLoading(false);
        setRagStep("");
      }
    },
    [selectedDocId, ragQuestion, ragLanguage, detailData, t]
  );

  // Explicit Vector Index Building
  const handleBuildIndex = useCallback(async () => {
    if (!selectedDocId) return;
    setIsBuildingIndex(true);
    setRagError(null);
    try {
      await documentService.buildIndex(selectedDocId, true);
      const freshData = await documentService.getDocument(selectedDocId);
      setDetailData(freshData);
    } catch (err) {
      setRagError(err.message || "Failed to build vector index.");
    } finally {
      setIsBuildingIndex(false);
    }
  }, [selectedDocId]);

  // Generate AI Summary
  const handleGenerateSummary = useCallback(async () => {
    if (!selectedDocId) return;
    setSummaryLoading(true);
    setSummaryError(null);

    try {
      const res = await documentService.generateSummary(
        selectedDocId,
        summaryLanguage
      );
      setSummaryData(res);
    } catch (err) {
      setSummaryError(err.message || "Failed to generate document summary.");
    } finally {
      setSummaryLoading(false);
    }
  }, [selectedDocId, summaryLanguage]);

  // Copy Summary to clipboard
  const handleCopySummary = () => {
    if (!summaryData?.summary) return;
    navigator.clipboard.writeText(summaryData.summary);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const suggestedQuestions = [
    t("documents.suggestedQ1"),
    t("documents.suggestedQ2"),
    t("documents.suggestedQ3"),
    t("documents.suggestedQ4"),
    t("documents.suggestedQ5"),
    t("documents.suggestedQ6"),
  ];

  // Render Status Badge
  const renderStatusBadge = (doc) => {
    const status = doc.status;
    const progress = doc.progress;
    const indexStatus = doc.index_status;

    let mainBadge = null;
    if (status === "uploaded" || status === "processing") {
      const progressText = progress?.total_pages
        ? ` (${progress.current_page || 0}/${progress.total_pages})`
        : "";
      mainBadge = (
        <Badge variant="primary" size="sm" className="flex items-center gap-1.5">
          <Spinner size="xs" color="text-blue-600" />
          <span>
            {t("documents.statusProcessing")}
            {progressText}
          </span>
        </Badge>
      );
    } else if (status === "ready") {
      mainBadge = (
        <Badge variant="success" size="sm" className="flex items-center gap-1">
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>{t("documents.statusReady")}</span>
        </Badge>
      );
    } else if (status === "ready_with_warnings") {
      mainBadge = (
        <Badge variant="warning" size="sm" className="flex items-center gap-1">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>{t("documents.statusWarnings")}</span>
        </Badge>
      );
    } else {
      mainBadge = (
        <Badge variant="danger" size="sm">
          {t("documents.statusFailed")}
        </Badge>
      );
    }

    if (status === "ready" || status === "ready_with_warnings") {
      let indexBadge = null;
      if (indexStatus === "indexed") {
        indexBadge = (
          <Badge variant="outline" size="xs" className="text-emerald-700 border-emerald-300 bg-emerald-50/70">
            {t("documents.indexIndexed")}
          </Badge>
        );
      } else if (indexStatus === "indexing") {
        indexBadge = (
          <Badge variant="primary" size="xs" className="flex items-center gap-1">
            <Spinner size="xs" color="text-blue-600" />
            <span>{t("documents.indexIndexing")}</span>
          </Badge>
        );
      } else if (indexStatus === "index_failed") {
        indexBadge = (
          <Badge variant="danger" size="xs">
            {t("documents.indexFailed")}
          </Badge>
        );
      } else {
        indexBadge = (
          <Badge variant="outline" size="xs" className="text-slate-500 border-slate-200">
            {t("documents.indexNotIndexed")}
          </Badge>
        );
      }

      return (
        <div className="flex flex-col gap-1 items-start">
          {mainBadge}
          {indexBadge}
        </div>
      );
    }

    return mainBadge;
  };

  return (
    <div className="space-y-6">
      {/* 1. Header */}
      <PageHeader
        title={t("pages.documents.title")}
        description={t("pages.documents.description")}
        badge={<Badge variant="primary">Module 1 • Active</Badge>}
      />

      {/* 2. Civic Privacy Notice */}
      <Alert
        variant="info"
        title={t("documents.privacyNoticeTitle")}
        icon={ShieldAlert}
      >
        {t("documents.privacyNoticeDesc")}
      </Alert>

      {error && (
        <Alert variant="danger" title="Document Error">
          {error}
        </Alert>
      )}

      {/* 3. Upload Dropzone Card */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <UploadCloud className="w-5 h-5 text-blue-600" />
                <span>{t("documents.uploadTitle")}</span>
              </CardTitle>
              <p className="text-xs text-slate-500 mt-1">
                {t("documents.uploadSubtitle")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="outline" size="sm">
                Max {capabilities?.max_upload_mb || 20} MB
              </Badge>
              <Badge
                variant={capabilities?.ocr_available ? "success" : "neutral"}
                size="sm"
              >
                {capabilities?.ocr_available
                  ? t("documents.ocrStatusEnabled")
                  : t("documents.ocrStatusDisabled")}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <FileDropzone
            onFileSelect={(file) => {
              if (file) uploadFile(file);
            }}
            maxSizeMB={capabilities?.max_upload_mb || 20}
          />
          {isUploading && (
            <div className="mt-3 flex items-center justify-center gap-2 text-sm text-blue-600 font-medium">
              <Spinner size="sm" color="text-blue-600" />
              <span>{t("documents.uploading")}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 4. Uploaded Documents List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold text-slate-800 flex items-center gap-2">
              <FileText className="w-4 h-4 text-slate-500" />
              <span>
                {language === "ta"
                  ? `பதிவேற்றப்பட்ட ஆவணங்கள் (${documents.length})`
                  : `Uploaded Documents (${documents.length})`}
              </span>
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="p-0 sm:p-6">
          {isLoading ? (
            <div className="p-6 space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : documents.length === 0 ? (
            <div className="py-8">
              <EmptyState
                icon={FileText}
                title={t("documents.noDocumentsTitle")}
                description={t("documents.noDocumentsDesc")}
              />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-600 font-semibold text-xs">
                    <th className="py-3 px-4">{t("documents.tableFilename")}</th>
                    <th className="py-3 px-4">{t("documents.tablePages")}</th>
                    <th className="py-3 px-4">{t("documents.tableSize")}</th>
                    <th className="py-3 px-4">{t("documents.tableLanguage")}</th>
                    <th className="py-3 px-4">{t("documents.tableStatus")}</th>
                    <th className="py-3 px-4 hidden md:table-cell">
                      {t("documents.tableUploadedAt")}
                    </th>
                    <th className="py-3 px-4 text-right">
                      {t("documents.tableActions")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.map((doc) => (
                    <tr
                      key={doc.document_id}
                      className="hover:bg-slate-50/60 transition-colors"
                    >
                      <td className="py-3.5 px-4 font-medium text-slate-900 max-w-xs truncate">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center shrink-0">
                            <FileText className="w-4 h-4" />
                          </div>
                          <span
                            className="truncate cursor-pointer hover:text-blue-600"
                            onClick={() => handleInspectDocument(doc.document_id)}
                            title={doc.filename}
                          >
                            {doc.filename}
                          </span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-600">
                        {doc.page_count}
                      </td>
                      <td className="py-3.5 px-4 text-slate-500 text-xs">
                        {formatFileSize(doc.file_size_bytes)}
                      </td>
                      <td className="py-3.5 px-4">
                        <Badge variant="outline" size="sm" className="uppercase text-[10px]">
                          {doc.language || "unknown"}
                        </Badge>
                      </td>
                      <td className="py-3.5 px-4">{renderStatusBadge(doc)}</td>
                      <td className="py-3.5 px-4 text-slate-400 text-xs hidden md:table-cell">
                        {formatDate(doc.uploaded_at)}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            variant="secondary"
                            size="sm"
                            icon={Eye}
                            onClick={() => handleInspectDocument(doc.document_id)}
                          >
                            <span className="hidden sm:inline">
                              {t("documents.viewDetails")}
                            </span>
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-500 hover:text-red-700 hover:bg-red-50"
                            icon={Trash2}
                            onClick={() => setDocToDelete(doc)}
                            aria-label={t("documents.deleteDoc")}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 5. Document Inspector Modal */}
      <Modal
        isOpen={Boolean(selectedDocId)}
        onClose={() => {
          setSelectedDocId(null);
          setDetailData(null);
        }}
        title={t("documents.inspectTitle")}
        maxWidth="max-w-4xl"
        footer={
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-2">
              <a
                href={
                  selectedDocId
                    ? documentService.getOriginalFileUrl(selectedDocId)
                    : "#"
                }
                target="_blank"
                rel="noopener noreferrer"
              >
                <Button variant="outline" size="sm" icon={ExternalLink}>
                  {t("documents.originalPdf")}
                </Button>
              </a>
              {detailData && (
                <span className="text-xs text-slate-500 hidden sm:inline-flex items-center gap-1.5">
                  {detailData.index_status === "indexed" ? (
                    <span className="text-emerald-700 font-medium flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {detailData.indexed_chunks_count || detailData.chunks_count || 0} chunks indexed
                    </span>
                  ) : (
                    <span className="text-slate-400">{t("documents.indexNotIndexed")}</span>
                  )}
                </span>
              )}
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setSelectedDocId(null);
                setDetailData(null);
              }}
            >
              {language === "ta" ? "மூடு" : "Close"}
            </Button>
          </div>
        }
      >
        {detailLoading ? (
          <div className="p-8 text-center space-y-3">
            <Spinner size="md" color="text-blue-600" className="mx-auto" />
            <p className="text-sm text-slate-500">
              {language === "ta" ? "விவரங்கள் ஏற்றப்படுகின்றன..." : "Loading document details..."}
            </p>
          </div>
        ) : detailError ? (
          <Alert variant="danger" title="Error">
            {detailError}
          </Alert>
        ) : detailData ? (
          <div className="space-y-6 max-h-[72vh] overflow-y-auto pr-1">
            {/* Metadata Bar */}
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-slate-400 block">{t("documents.tableFilename")}</span>
                <span className="font-semibold text-slate-800 truncate block" title={detailData.filename}>
                  {detailData.filename}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">{t("documents.tablePages")} & {t("documents.tableSize")}</span>
                <span className="font-semibold text-slate-800">
                  {detailData.page_count} pages • {formatFileSize(detailData.file_size_bytes)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">{t("documents.tableLanguage")}</span>
                <span className="font-semibold text-slate-800 uppercase">
                  {detailData.language}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block">Vector Index</span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="font-semibold text-slate-800">
                    {detailData.index_status === "indexed"
                      ? `${t("documents.indexIndexed")} (${detailData.indexed_chunks_count || detailData.chunks_count || 0})`
                      : detailData.index_status === "indexing"
                      ? t("documents.indexIndexing")
                      : t("documents.indexNotIndexed")}
                  </span>
                  <Button
                    variant="ghost"
                    size="xs"
                    icon={RefreshCw}
                    className="p-0.5 h-4 w-4 text-slate-400 hover:text-slate-700"
                    title={detailData.index_status === "indexed" ? t("documents.rebuildIndexBtn") : t("documents.buildIndexBtn")}
                    isLoading={isBuildingIndex}
                    onClick={handleBuildIndex}
                  />
                </div>
              </div>
            </div>

            {/* Warnings Alert (if any) */}
            {detailData.warnings && detailData.warnings.length > 0 && (
              <Alert variant="warning" title={t("documents.warningsTitle")} icon={AlertTriangle}>
                <ul className="list-disc pl-5 space-y-1 text-xs">
                  {detailData.warnings.map((w, idx) => (
                    <li key={idx}>{w}</li>
                  ))}
                </ul>
              </Alert>
            )}

            {/* Ask Policy RAG Section (Phase 8) */}
            <div className="p-5 rounded-xl border border-blue-200 bg-blue-50/30 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shrink-0">
                    <Search className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900">
                      {t("documents.askSectionTitle")}
                    </h4>
                    <p className="text-xs text-slate-500">
                      {t("documents.askSectionSubtitle")}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={ragLanguage}
                    onChange={(e) => setRagLanguage(e.target.value)}
                    aria-label={t("assistant.language")}
                    className="text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-1.5 text-slate-700 focus:ring-2 focus:ring-blue-600"
                  >
                    <option value="auto">{t("assistant.langAuto")}</option>
                    <option value="en">English</option>
                    <option value="ta">தமிழ்</option>
                  </select>
                </div>
              </div>

              {/* Suggested Questions */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block">
                  {t("documents.suggestedTitle")}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {suggestedQuestions.map((sq, idx) => (
                    <button
                      key={idx}
                      type="button"
                      disabled={ragLoading}
                      onClick={() => handleAskQuestion(sq)}
                      className="text-xs text-left bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 hover:border-blue-300 px-2.5 py-1 rounded-full transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {sq}
                    </button>
                  ))}
                </div>
              </div>

              {/* Question Input Form */}
              <div className="space-y-2">
                <div className="relative">
                  <textarea
                    rows={2}
                    value={ragQuestion}
                    onChange={(e) => setRagQuestion(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        if (ragQuestion.trim() && !ragLoading) {
                          handleAskQuestion();
                        }
                      }
                    }}
                    placeholder={t("documents.questionPlaceholder")}
                    disabled={ragLoading}
                    className="w-full text-xs p-3 pr-24 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-600 text-slate-900 resize-none"
                  />
                  <div className="absolute right-2 bottom-2.5">
                    <Button
                      variant="primary"
                      size="sm"
                      icon={Send}
                      disabled={!ragQuestion.trim() || ragLoading}
                      isLoading={ragLoading}
                      onClick={() => handleAskQuestion()}
                    >
                      {t("documents.askButton")}
                    </Button>
                  </div>
                </div>

                {/* Progress / Step status indicator */}
                {ragLoading && (
                  <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-100/60 p-2.5 rounded-lg animate-pulse">
                    <Spinner size="xs" color="text-blue-600" />
                    <span>{ragStep || t("documents.searchingNotice")}</span>
                  </div>
                )}

                {ragError && (
                  <Alert variant="danger" size="sm">
                    {ragError}
                  </Alert>
                )}
              </div>

              {/* Grounded Answer Card */}
              {ragResult && (
                <div className="p-4 bg-white rounded-xl border border-blue-200 space-y-3.5 shadow-sm">
                  {/* Top metadata row */}
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
                    <div className="flex items-center gap-2">
                      {/* Evidence Badge */}
                      {ragResult.evidence_level === "strong" ? (
                        <Badge variant="success" size="sm" className="flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>{t("documents.evidenceStrong")}</span>
                        </Badge>
                      ) : ragResult.evidence_level === "weak" ? (
                        <Badge variant="warning" size="sm" className="flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>{t("documents.evidenceWeak")}</span>
                        </Badge>
                      ) : (
                        <Badge variant="outline" size="sm" className="text-slate-600 border-slate-300">
                          {t("documents.evidenceNone")}
                        </Badge>
                      )}

                      <Badge variant="outline" size="sm" className="uppercase text-[10px]">
                        {ragResult.language_used || "en"}
                      </Badge>

                      {ragResult.model && (
                        <span className="text-[11px] text-slate-400">
                          {ragResult.model} • {ragResult.latency_ms}ms
                        </span>
                      )}
                    </div>

                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => setRagResult(null)}
                      className="text-slate-400 hover:text-slate-700 text-xs"
                    >
                      {t("documents.clearAnswer")}
                    </Button>
                  </div>

                  {/* Warning if citations were unverified */}
                  {ragResult.unverified_citations && (
                    <Alert variant="warning" size="sm">
                      {t("documents.unverifiedWarning")}
                    </Alert>
                  )}

                  {/* Main Answer text */}
                  <div className="prose prose-slate max-w-none text-xs leading-relaxed text-slate-800">
                    <ReactMarkdown>{ragResult.answer}</ReactMarkdown>
                  </div>

                  {/* Missing information (if flagged by backend/LLM) */}
                  {ragResult.missing_information && (
                    <div className="p-2.5 rounded-lg bg-amber-50/70 border border-amber-200 text-xs text-amber-900 flex items-start gap-2">
                      <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                      <div>
                        <strong className="font-semibold block">{t("documents.missingInfoTitle")}:</strong>
                        <span>{ragResult.missing_information}</span>
                      </div>
                    </div>
                  )}

                  {/* Civic follow-up recommendation */}
                  {ragResult.follow_up_suggestion && (
                    <div className="p-2.5 rounded-lg bg-emerald-50/60 border border-emerald-200 text-xs text-emerald-900 flex items-start gap-2">
                      <Sparkles className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                      <div>
                        <strong className="font-semibold block">{t("documents.suggestionTitle")}:</strong>
                        <span>{ragResult.follow_up_suggestion}</span>
                      </div>
                    </div>
                  )}

                  {/* Verified Citations List */}
                  {ragResult.citations && ragResult.citations.length > 0 && (
                    <div className="pt-2 border-t border-slate-100 space-y-2">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
                        <BookOpen className="w-3.5 h-3.5 text-blue-600" />
                        <span>{t("documents.citationsTitle")} ({ragResult.citations.length})</span>
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {ragResult.citations.map((cit, idx) => (
                          <div
                            key={idx}
                            className="group flex items-center gap-1.5 bg-slate-50 hover:bg-blue-50 border border-slate-200 hover:border-blue-300 px-3 py-1.5 rounded-lg transition-colors text-xs text-slate-700 hover:text-blue-800"
                          >
                            <button
                              type="button"
                              onClick={() => handleJumpToPage(cit.page_number)}
                              title={`${t("documents.citationJumpTooltip")} ${cit.page_number}`}
                              className="font-medium underline decoration-blue-300 underline-offset-2 flex items-center gap-1"
                            >
                              <span>Page {cit.page_number}</span>
                            </button>

                            {cit.verified_quote && (
                              <span className="text-[11px] text-slate-500 italic max-w-xs truncate hidden sm:inline" title={cit.verified_quote}>
                                "{cit.verified_quote}"
                              </span>
                            )}

                            <a
                              href={`${documentService.getOriginalFileUrl(selectedDocId)}#page=${cit.page_number}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-slate-400 hover:text-blue-600 ml-1"
                              title={`${t("documents.openPdfAtPage")} ${cit.page_number}`}
                            >
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Toggle raw retrieved passages */}
                  {ragResult.retrieved_count > 0 && (
                    <div className="pt-2">
                      <button
                        type="button"
                        onClick={() => setShowPassages(!showPassages)}
                        className="text-[11px] text-slate-500 hover:text-slate-800 flex items-center gap-1"
                      >
                        {showPassages ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        <span>
                          {showPassages ? t("documents.hidePassagesBtn") : t("documents.showPassagesBtn")} ({ragResult.retrieved_count})
                        </span>
                      </button>

                      {showPassages && (
                        <div className="mt-2 space-y-2">
                          {ragResult.passages?.map((p, idx) => (
                            <div key={idx} className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
                              <div className="flex items-center justify-between text-[11px] text-slate-500">
                                <span className="font-semibold text-slate-700">
                                  Page {p.page_number} (Chunk #{p.chunk_index})
                                </span>
                                <span>
                                  Score: {p.score} (Vec: {p.vector_score}, Lex: {p.lexical_score})
                                </span>
                              </div>
                              <p className="text-slate-700 font-mono text-[11px] leading-relaxed">
                                {p.excerpt}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* AI Grounded Summary Section */}
            <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/40 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-blue-950">
                      {t("documents.summaryTitle")}
                    </h4>
                    <p className="text-[11px] text-blue-700">
                      {t("documents.summaryDesc")}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <select
                    value={summaryLanguage}
                    onChange={(e) => setSummaryLanguage(e.target.value)}
                    className="text-xs bg-white border border-slate-300 rounded-lg px-2.5 py-1 text-slate-700 focus:ring-2 focus:ring-blue-600"
                  >
                    <option value="auto">{t("assistant.langAuto")}</option>
                    <option value="en">English</option>
                    <option value="ta">தமிழ்</option>
                  </select>

                  <Button
                    variant="primary"
                    size="sm"
                    icon={Sparkles}
                    isLoading={summaryLoading}
                    onClick={handleGenerateSummary}
                  >
                    {t("documents.generateSummaryBtn")}
                  </Button>
                </div>
              </div>

              {summaryError && (
                <Alert variant="danger" size="sm">
                  {summaryError}
                </Alert>
              )}

              {summaryData && (
                <div className="mt-3 p-4 bg-white rounded-lg border border-blue-100 text-sm space-y-2 relative">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" size="sm">
                        Model: {summaryData.model}
                      </Badge>
                      {summaryData.cached && (
                        <Badge variant="secondary" size="sm">
                          {t("documents.summaryCachedBadge")}
                        </Badge>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={isCopied ? Check : Copy}
                      onClick={handleCopySummary}
                      className="text-slate-500 hover:text-slate-800"
                    >
                      {isCopied ? t("assistant.copied") : t("assistant.copy")}
                    </Button>
                  </div>

                  <div className="prose prose-slate max-w-none text-xs leading-relaxed text-slate-800">
                    <ReactMarkdown>{summaryData.summary}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>

            {/* Page-by-Page Text Viewer */}
            <div id="document-page-viewer" className="border border-slate-200 rounded-xl overflow-hidden bg-white scroll-mt-6">
              <div className="p-3 bg-slate-50 border-b border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-700">
                    {t("documents.pageViewerTitle")}
                  </span>
                  {currentPageData && (
                    <>
                      <Badge variant="outline" size="sm">
                        {currentPageData.extraction_method === "ocr"
                          ? t("documents.methodOcr")
                          : t("documents.methodPymupdf")}
                      </Badge>
                      <Badge
                        variant={
                          currentPageData.quality === "normal"
                            ? "neutral"
                            : currentPageData.quality === "blank"
                            ? "outline"
                            : "warning"
                        }
                        size="sm"
                      >
                        {currentPageData.quality === "normal"
                          ? t("documents.qualityNormal")
                          : currentPageData.quality === "blank"
                          ? t("documents.qualityBlank")
                          : currentPageData.quality === "needs_ocr"
                          ? t("documents.qualityNeedsOcr")
                          : t("documents.qualityLow")}
                      </Badge>
                    </>
                  )}
                </div>

                {/* Page Navigator */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    icon={ChevronLeft}
                    disabled={currentPageNumber <= 1 || pageLoading}
                    onClick={() => handlePageChange(currentPageNumber - 1)}
                  >
                    {t("documents.prevPage")}
                  </Button>
                  <span className="text-xs text-slate-600 font-medium">
                    {t("documents.pageNavigator")} {currentPageNumber} {t("documents.ofPages")}{" "}
                    {detailData.page_count || 1}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    icon={ChevronRight}
                    iconPosition="right"
                    disabled={
                      currentPageNumber >= (detailData.page_count || 1) || pageLoading
                    }
                    onClick={() => handlePageChange(currentPageNumber + 1)}
                  >
                    {t("documents.nextPage")}
                  </Button>
                </div>
              </div>

              {/* Text Area */}
              <div className="p-4 min-h-[160px] max-h-[300px] overflow-y-auto bg-slate-950 text-slate-100 font-mono text-xs leading-relaxed whitespace-pre-wrap select-text">
                {pageLoading ? (
                  <div className="flex items-center justify-center py-10 gap-2 text-slate-400">
                    <Spinner size="sm" color="text-slate-400" />
                    <span>Loading page {currentPageNumber}...</span>
                  </div>
                ) : currentPageData?.text ? (
                  currentPageData.text
                ) : (
                  <span className="text-slate-500 italic">
                    [Empty or blank page. No text detected.]
                  </span>
                )}
              </div>

              {currentPageData && (
                <div className="px-4 py-2 bg-slate-900 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
                  <span>
                    {currentPageData.char_count} {t("documents.charCount")}
                  </span>
                  {currentPageData.confidence && (
                    <span>OCR Confidence: {Math.round(currentPageData.confidence)}%</span>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Modal>

      {/* 6. Delete Confirmation Modal */}
      <Modal
        isOpen={Boolean(docToDelete)}
        onClose={() => setDocToDelete(null)}
        title={t("documents.deleteDoc")}
        maxWidth="max-w-md"
        confirmText={language === "ta" ? "நீக்கு" : "Delete"}
        cancelText={language === "ta" ? "ரத்து" : "Cancel"}
        confirmVariant="danger"
        onConfirm={async () => {
          if (docToDelete) {
            await deleteDoc(docToDelete.document_id, docToDelete.filename);
            setDocToDelete(null);
          }
        }}
      >
        <p className="text-sm text-slate-600">
          {t("documents.deleteConfirm")}
        </p>
        {docToDelete && (
          <p className="mt-2 text-xs font-semibold text-slate-800 bg-slate-100 p-2.5 rounded-lg truncate">
            {docToDelete.filename}
          </p>
        )}
      </Modal>
    </div>
  );
}
