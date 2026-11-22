import React, { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  LifeBuoy,
  ShieldAlert,
  CheckCircle2,
  Clock,
  MapPin,
  Camera,
  Copy,
  Printer,
  Trash2,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  FileText,
  HelpCircle,
  Check,
  ChevronRight,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { Modal } from "../components/ui/Modal";
import { Spinner } from "../components/ui/Spinner";
import { EmptyState } from "../components/ui/EmptyState";
import { Card } from "../components/ui/Card";
import { FileDropzone } from "../components/ui/FileDropzone";
import { useLanguage } from "../hooks/useLanguage";
import { useGrievance } from "../hooks/useGrievance";
import { useGrievances } from "../hooks/useGrievances";
import { grievanceService } from "../services/grievanceService";

const CATEGORIES = [
  { id: "roads", icon: "🚧" },
  { id: "streetlights", icon: "💡" },
  { id: "water_supply", icon: "🚰" },
  { id: "waste_management", icon: "🗑️" },
  { id: "drainage_sewage", icon: "🕳️" },
  { id: "public_transport", icon: "🚌" },
  { id: "parks_playgrounds", icon: "🌳" },
  { id: "other", icon: "📋" },
];

const SEVERITIES = ["low", "medium", "high", "urgent"];

const EXAMPLE_ISSUES = [
  {
    en: "Deep pothole on 4th Cross Street near the bus stop causing two-wheelers to skid and water to accumulate.",
    ta: "4வது குறுக்கு தெரு பேருந்து நிறுத்தம் அருகில் ஆழமான குழி உள்ளதால் இருசக்கர வாகனங்கள் சறுக்கி விழுகின்றன, மழைநீர் தேங்குகிறது.",
    loc: "4th Cross Street, Gandhinagar",
    dur: "2 weeks",
    cat: "roads",
  },
  {
    en: "Streetlight lamp is burnt out for the past 3 weeks, creating pitch dark unsafe conditions for pedestrians at night.",
    ta: "கடந்த 3 வாரங்களாக தெருவிளக்கு எரியாததால் இரவில் பாதசாரிகள் நடமாட முடியாத அளவிற்கு இருட்டாக உள்ளது.",
    loc: "Anna Salai, Ward 14",
    dur: "3 weeks",
    cat: "streetlights",
  },
  {
    en: "Underground drainage line is blocked and sewage is overflowing into the street with foul smell and health hazard.",
    ta: "பாதாள சாக்கடை அடைப்பு ஏற்பட்டு கழிவுநீர் தெருவில் பெருக்கெடுத்து துர்நாற்றம் வீசுகிறது, சுகாதார சீர்கேடு ஏற்பட்டுள்ளது.",
    loc: "Bazaar Street Junction",
    dur: "4 days",
    cat: "drainage_sewage",
  },
  {
    en: "Drinking water supply has been contaminated with yellowish color and foul odor for several days.",
    ta: "குடிநீர் விநியோகத்தில் மஞ்சள் நிறத்துடன் துர்நாற்றம் வீசுகிறது, குடிப்பதற்கு உகந்ததாக இல்லை.",
    loc: "Kamarajar Colony",
    dur: "5 days",
    cat: "water_supply",
  },
];

export function Grievance() {
  const { t, language: uiLang } = useLanguage();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tab state: "new" or "history"
  const [activeTab, setActiveTab] = useState("new");
  // Wizard step: 1 (Describe), 2 (Review & Edit), 3 (Authorize Demo), 4 (Tracking)
  const [step, setStep] = useState(1);

  // Hook for single active grievance
  const {
    grievance,
    loading: grievanceLoading,
    error: grievanceError,
    loadGrievance,
    startAnalysis,
    patchDraft,
    toggleObservation,
    registerDemo,
    advanceDemoStatus,
    retryAnalysis,
    deleteActiveGrievance,
    reset: resetActiveGrievance,
  } = useGrievance();

  // Hook for list of past grievances
  const {
    grievances: pastList,
    loading: listLoading,
    refresh: refreshList,
    deleteGrievance: deletePastRecord,
  } = useGrievances();

  // Form State (Step 1)
  const [description, setDescription] = useState("");
  const [locationText, setLocationText] = useState("");
  const [durationText, setDurationText] = useState("");
  const [draftLang, setDraftLang] = useState(uiLang === "ta" ? "ta" : "en");
  const [categoryHint, setCategoryHint] = useState("");
  const [uploadedImageId, setUploadedImageId] = useState(null);
  const [uploadedImageMeta, setUploadedImageMeta] = useState(null);
  const [imageConsent, setImageConsent] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [formError, setFormError] = useState(null);

  // Review & Edit State (Step 2)
  const [editedCategory, setEditedCategory] = useState("");
  const [editedSeverity, setEditedSeverity] = useState("");
  const [editedSubject, setEditedSubject] = useState("");
  const [editedBody, setEditedBody] = useState("");
  const [editedLocation, setEditedLocation] = useState("");
  const [copiedToast, setCopiedToast] = useState(false);
  const [savingDraft, setSavingDraft] = useState(false);

  // Retry modal state
  const [showRetryModal, setShowRetryModal] = useState(false);
  const [retryAdditionalDetails, setRetryAdditionalDetails] = useState("");

  // Approval state (Step 3)
  const [approving, setApproving] = useState(false);

  // Tracking state (Step 4)
  const [simulatedNote, setSimulatedNote] = useState("");
  const [advancingStatus, setAdvancingStatus] = useState(false);

  // Delete confirmation
  const [deletingId, setDeletingId] = useState(null);

  // Filter in My Complaints tab
  const [historyFilter, setHistoryFilter] = useState("all"); // all | drafts | demo

  // Sync draftLang when UI language changes initially
  useEffect(() => {
    if (!grievance) {
      setDraftLang(uiLang === "ta" ? "ta" : "en");
    }
  }, [uiLang, grievance]);

  // Deep linking: read ?id= or ?draft_id=
  useEffect(() => {
    const qId = searchParams.get("id") || searchParams.get("draft_id");
    if (qId && (!grievance || grievance.id !== qId)) {
      loadGrievance(qId);
    }
  }, [searchParams, grievance, loadGrievance]);

  // When grievance loads or updates, update local editing states and advance wizard
  useEffect(() => {
    if (grievance) {
      setEditedCategory(grievance.category || "");
      setEditedSeverity(grievance.severity || "medium");
      if (grievance.draft) {
        setEditedSubject(grievance.draft.subject_line || "");
        setEditedBody(grievance.draft.body || "");
        setEditedLocation(grievance.draft.location_line || "");
      }
      if (grievance.state === "demo_registered" || grievance.demo) {
        setStep(4);
      } else if (step === 1) {
        setStep(2);
      }
    }
  }, [grievance, step]);

  // Handle Photo Drop/Selection
  const handlePhotoUpload = async (file) => {
    setUploadError(null);
    setUploadingImage(true);
    try {
      const res = await grievanceService.uploadImage(file);
      setUploadedImageId(res.image_id);
      setUploadedImageMeta(res);
      setImageConsent(false); // require fresh consent
    } catch (err) {
      setUploadError(err.message || "Failed to process photo.");
    } finally {
      setUploadingImage(false);
    }
  };

  const handleRemovePhoto = () => {
    setUploadedImageId(null);
    setUploadedImageMeta(null);
    setImageConsent(false);
    setUploadError(null);
  };

  // Submit Step 1
  const handleAnalyze = async (e) => {
    e?.preventDefault();
    setFormError(null);

    const descClean = description.trim();
    if (descClean.length < 20) {
      setFormError("Please provide a clearer problem description (minimum 20 characters).");
      return;
    }
    if (uploadedImageId && !imageConsent) {
      setFormError(t("grievanceHub.step1.consentRequired", "Photo consent is required to analyze attached photos."));
      return;
    }

    try {
      const payload = {
        description: descClean,
        location_text: locationText.trim() || undefined,
        duration_text: durationText.trim() || undefined,
        language_of_draft: draftLang,
        category_hint: categoryHint || undefined,
        image_id: uploadedImageId || undefined,
        image_consent: Boolean(uploadedImageId && imageConsent),
      };

      const res = await startAnalysis(payload);
      setSearchParams({ id: res.id });
      setStep(2);
    } catch (err) {
      setFormError(err.message || "Failed to structure grievance draft.");
    }
  };

  // Save / Patch Draft (Step 2)
  const handleSaveDraft = async () => {
    if (!grievance?.id) return;
    setSavingDraft(true);
    try {
      await patchDraft({
        category: editedCategory !== grievance.category ? editedCategory : undefined,
        severity: editedSeverity !== grievance.severity ? editedSeverity : undefined,
        subject_line: editedSubject.trim(),
        body: editedBody.trim(),
        location_line: editedLocation.trim(),
      });
      refreshList();
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setSavingDraft(false);
    }
  };

  // Copy Draft to Clipboard
  const handleCopyDraft = () => {
    if (!grievance?.draft) return;
    const textToCopy = grievance.draft.final_text || `${editedSubject}\n\n${editedBody}\n\n${editedLocation}`;
    navigator.clipboard.writeText(textToCopy);
    setCopiedToast(true);
    setTimeout(() => setCopiedToast(false), 2500);
  };

  // Print Representation
  const handlePrint = () => {
    window.print();
  };

  // Authorize & Register Demo Record (Step 3)
  const handleConfirmRegistration = async () => {
    if (!grievance?.draft_hash) return;
    setApproving(true);
    try {
      await registerDemo(grievance.draft_hash);
      setShowApprovalModal(false);
      setStep(4);
      refreshList();
    } catch (err) {
      alert(`Demo registration failed: ${err.message}`);
    } finally {
      setApproving(false);
    }
  };

  // Advance Simulated Status (Step 4)
  const handleAdvanceStatus = async () => {
    if (!grievance?.id) return;
    setAdvancingStatus(true);
    try {
      await advanceDemoStatus(simulatedNote.trim());
      setSimulatedNote("");
      refreshList();
    } catch (err) {
      alert(`Status advance failed: ${err.message}`);
    } finally {
      setAdvancingStatus(false);
    }
  };

  // Handle Retry Analysis with Additional Info
  const handleRetrySubmit = async () => {
    if (!grievance?.id) return;
    try {
      await retryAnalysis({
        category_hint: editedCategory || undefined,
        additional_details: retryAdditionalDetails.trim() || undefined,
      });
      setShowRetryModal(false);
      setRetryAdditionalDetails("");
    } catch (err) {
      alert(`Retry failed: ${err.message}`);
    }
  };

  // Start fresh
  const handleStartFresh = () => {
    resetActiveGrievance();
    setDescription("");
    setLocationText("");
    setDurationText("");
    setCategoryHint("");
    setUploadedImageId(null);
    setUploadedImageMeta(null);
    setImageConsent(false);
    setStep(1);
    setSearchParams({});
  };

  // Open existing complaint from History tab
  const handleOpenFromHistory = (rec) => {
    loadGrievance(rec.id);
    setSearchParams({ id: rec.id });
    setActiveTab("new");
    if (rec.state === "demo_registered" || rec.demo) {
      setStep(4);
    } else {
      setStep(2);
    }
  };

  // Filtered History
  const filteredHistory = useMemo(() => {
    if (historyFilter === "drafts") {
      return pastList.filter((g) => g.state === "draft" && !g.demo);
    }
    if (historyFilter === "demo") {
      return pastList.filter((g) => g.state === "demo_registered" || g.demo);
    }
    return pastList;
  }, [pastList, historyFilter]);

  // Baseline severity floor helper
  const isSeverityBelowFloor = (sev) => {
    if (!grievance?.severity) return false;
    // Check if safety risk exists
    if (grievance.safety_risk && (sev === "low" || sev === "medium")) {
      return true;
    }
    return false;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16 print:p-0 print:m-0">
      {/* Top Header */}
      <PageHeader
        title={t("grievanceHub.title", "Civic Grievance Assistant")}
        description={t(
          "grievanceHub.subtitle",
          "Structure civic issues into formal, respectful, and factual complaint drafts, discover verified government channels, and track simulated progress in a safe demo environment."
        )}
        badge={
          <Badge variant="primary" size="sm">
            Module 5 • Civic Intelligence
          </Badge>
        }
      />

      {/* Persistent DEMO Environment Notice Banner */}
      <div className="rounded-xl border border-amber-300 bg-amber-50/90 p-4 text-xs text-amber-950 flex items-start gap-3 shadow-2xs print:hidden">
        <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-bold tracking-wide uppercase text-[10px] bg-amber-200 text-amber-900 px-2 py-0.5 rounded">
              {t("grievanceHub.demoNotice.badge", "SIMULATED DEMO")}
            </span>
            <span className="font-semibold">CivicLens Demonstration Environment</span>
          </div>
          <p className="leading-relaxed text-amber-900/90">
            {t(
              "grievanceHub.demoNotice.banner",
              "Demonstration Environment Only: Complaints prepared here are tracked inside CivicLens to help you review, verify, and copy or print your representation before official submission. Nothing is sent to any government authority or third party."
            )}
          </p>
        </div>
      </div>

      {/* Global Grievance Error Alert */}
      {grievanceError && (
        <Alert variant="danger" title="Grievance Notice">
          <p className="text-xs text-rose-800">{grievanceError}</p>
        </Alert>
      )}

      {/* Main Tabs */}
      <div className="flex border-b border-slate-200 gap-6 print:hidden">
        <button
          type="button"
          onClick={() => setActiveTab("new")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeTab === "new"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <LifeBuoy className="w-4 h-4" />
          {t("grievanceHub.tabs.newComplaint", "New Complaint")}
          {step > 1 && grievance && (
            <span className="text-[11px] bg-blue-100 text-blue-800 font-mono px-2 py-0.2 rounded-full">
              Step {step}/4
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab("history");
            refreshList();
          }}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeTab === "history"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Clock className="w-4 h-4" />
          {t("grievanceHub.tabs.myComplaints", "My Complaints")}
          <span className="ml-1 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 font-mono">
            {pastList.length}
          </span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: NEW COMPLAINT WIZARD                                               */}
      {/* ========================================================================= */}
      {activeTab === "new" && (
        <div className="space-y-6">
          {/* Stepper Header */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-2xs print:hidden">
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              {[
                { s: 1, label: t("grievanceHub.steps.step1", "1. Describe") },
                { s: 2, label: t("grievanceHub.steps.step2", "2. Review & Edit") },
                { s: 3, label: t("grievanceHub.steps.step3", "3. Authorize Demo") },
                { s: 4, label: t("grievanceHub.steps.step4", "4. Tracking") },
              ].map(({ s, label }) => {
                const isActive = step === s;
                const isPassed = step > s;
                return (
                  <div
                    key={s}
                    className={`py-2 px-1 rounded-lg font-medium transition-colors flex items-center justify-center gap-1.5 ${
                      isActive
                        ? "bg-blue-50 text-blue-700 font-bold border border-blue-200"
                        : isPassed
                        ? "text-emerald-700 bg-emerald-50/50"
                        : "text-slate-400"
                    }`}
                  >
                    {isPassed && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />}
                    <span>{label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* --------------------------------------------------------------------- */}
          {/* STEP 1: DESCRIBE PROBLEM                                             */}
          {/* --------------------------------------------------------------------- */}
          {step === 1 && (
            <div className="space-y-6">
              <Card className="p-6 space-y-6 bg-white border-slate-200">
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-slate-900">
                    {t("grievanceHub.step1.title", "Describe the Civic Issue")}
                  </h3>
                  <p className="text-xs text-slate-500">
                    {t(
                      "grievanceHub.step1.subtitle",
                      "Provide details about the municipal or civic problem you are facing. We will classify the issue, check for safety hazards, and structure a formal complaint."
                    )}
                  </p>
                </div>

                {/* Example Chips */}
                <div className="space-y-2">
                  <span className="text-xs font-semibold text-slate-600">
                    {t("grievanceHub.step1.examplesTitle", "Common Civic Issues:")}
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLE_ISSUES.map((ex, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          setDescription(uiLang === "ta" ? ex.ta : ex.en);
                          setLocationText(ex.loc);
                          setDurationText(ex.dur);
                          setCategoryHint(ex.cat);
                        }}
                        className="text-[11px] px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700 transition-colors border border-slate-200 text-left cursor-pointer"
                      >
                        {uiLang === "ta" ? ex.ta.slice(0, 48) : ex.en.slice(0, 48)}...
                      </button>
                    ))}
                  </div>
                </div>

                <form onSubmit={handleAnalyze} className="space-y-5">
                  {/* Category Hint Chips */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-slate-700">
                      {t("grievanceHub.step1.categoryHintLabel", "Category (Optional)")}
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {CATEGORIES.map((cat) => (
                        <button
                          key={cat.id}
                          type="button"
                          onClick={() => setCategoryHint(categoryHint === cat.id ? "" : cat.id)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5 cursor-pointer ${
                            categoryHint === cat.id
                              ? "bg-blue-600 text-white border-blue-600 shadow-2xs"
                              : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                          }`}
                        >
                          <span>{cat.icon}</span>
                          <span>{t(`grievanceHub.categories.${cat.id}`, cat.id)}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Description Textarea */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <label className="font-semibold text-slate-800">
                        {t("grievanceHub.step1.descriptionLabel", "Describe the Problem *")}
                      </label>
                      <span
                        className={`font-mono text-[11px] ${
                          description.length > 2800 ? "text-rose-600 font-bold" : "text-slate-400"
                        }`}
                      >
                        {description.length} / 3000
                      </span>
                    </div>
                    <textarea
                      rows={5}
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder={t(
                        "grievanceHub.step1.descriptionPlaceholder",
                        "Describe the civic issue clearly (e.g. Deep pothole on Kamarajar Street near the bus stop causing two-wheelers to slip, water stagnant for 4 days)..."
                      )}
                      maxLength={3000}
                      className="w-full px-4 py-3 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-normal leading-relaxed"
                    />
                  </div>

                  {/* Privacy / Zero Personal Data notice */}
                  <div className="p-3 rounded-lg bg-blue-50/70 border border-blue-200 text-xs text-blue-900 flex items-start gap-2">
                    <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
                    <p className="leading-relaxed">
                      {t(
                        "grievanceHub.step1.privacyNotice",
                        "Zero Personal Data: Please do NOT include your phone number, Aadhaar number, email, or personal names in the description."
                      )}
                    </p>
                  </div>

                  {/* Location & Duration Row */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="block text-xs font-semibold text-slate-700">
                        <MapPin className="w-3.5 h-3.5 inline mr-1 text-slate-400" />
                        {t("grievanceHub.step1.locationLabel", "Location / Landmark (Optional)")}
                      </label>
                      <input
                        type="text"
                        value={locationText}
                        onChange={(e) => setLocationText(e.target.value)}
                        placeholder={t("grievanceHub.step1.locationPlaceholder", "e.g., 4th Cross Street, Gandhinagar, Salem")}
                        maxLength={200}
                        className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="block text-xs font-semibold text-slate-700">
                        <Clock className="w-3.5 h-3.5 inline mr-1 text-slate-400" />
                        {t("grievanceHub.step1.durationLabel", "How long has this persisted? (Optional)")}
                      </label>
                      <input
                        type="text"
                        value={durationText}
                        onChange={(e) => setDurationText(e.target.value)}
                        placeholder={t("grievanceHub.step1.durationPlaceholder", "e.g., 2 weeks, since last Monday's rain...")}
                        maxLength={100}
                        className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                    </div>
                  </div>

                  {/* Language Selection */}
                  <div className="space-y-1">
                    <label className="block text-xs font-semibold text-slate-700">
                      {t("grievanceHub.step1.draftLangLabel", "Target Draft Language")}
                    </label>
                    <div className="flex gap-4">
                      <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="draftLang"
                          value="en"
                          checked={draftLang === "en"}
                          onChange={() => setDraftLang("en")}
                          className="text-blue-600 focus:ring-blue-500"
                        />
                        <span>English (Formal Municipal Letter)</span>
                      </label>
                      <label className="flex items-center gap-2 text-xs font-medium text-slate-700 cursor-pointer">
                        <input
                          type="radio"
                          name="draftLang"
                          value="ta"
                          checked={draftLang === "ta"}
                          onChange={() => setDraftLang("ta")}
                          className="text-blue-600 focus:ring-blue-500"
                        />
                        <span>தமிழ் (முறைப்படியான நகராட்சி மனு)</span>
                      </label>
                    </div>
                  </div>

                  {/* Photo Upload Section */}
                  <div className="space-y-2 pt-2 border-t border-slate-100">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-800 flex items-center gap-1.5">
                        <Camera className="w-4 h-4 text-slate-500" />
                        <span>{t("grievanceHub.step1.photoLabel", "Attach Problem Photo (Optional)")}</span>
                      </label>
                      {uploadedImageId && (
                        <button
                          type="button"
                          onClick={handleRemovePhoto}
                          className="text-xs text-rose-600 hover:text-rose-800 cursor-pointer font-medium"
                        >
                          Remove Photo
                        </button>
                      )}
                    </div>

                    {!uploadedImageId ? (
                      <div className="space-y-2">
                        <FileDropzone
                          accept=".jpg,.jpeg,.png,.webp"
                          maxSize={5 * 1024 * 1024}
                          onDrop={(acceptedFiles) => {
                            if (acceptedFiles?.[0]) {
                              handlePhotoUpload(acceptedFiles[0]);
                            }
                          }}
                          disabled={uploadingImage}
                        />
                        {uploadingImage && (
                          <div className="flex items-center gap-2 text-xs text-slate-500">
                            <Spinner size="sm" />
                            <span>Processing and stripping metadata...</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg border border-slate-200 bg-slate-50 flex items-center gap-4">
                        <img
                          src={grievanceService.getImageUrl(uploadedImageId)}
                          alt="Grievance upload preview"
                          className="w-16 h-16 object-cover rounded-md border border-slate-200 bg-white"
                        />
                        <div className="space-y-1 text-xs">
                          <p className="font-semibold text-slate-800">Photo Attached & Metadata Stripped</p>
                          <p className="text-slate-500 font-mono text-[11px]">
                            {uploadedImageMeta?.width} × {uploadedImageMeta?.height} px • Clean JPEG
                          </p>
                          <span className="inline-block text-[10px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">
                            100% EXIF/GPS Removed
                          </span>
                        </div>
                      </div>
                    )}

                    {uploadError && (
                      <Alert variant="danger">
                        <p className="text-xs text-rose-800">{uploadError}</p>
                      </Alert>
                    )}

                    {/* Photo Consent Checkbox */}
                    {uploadedImageId && (
                      <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 space-y-1">
                        <label className="flex items-start gap-2.5 text-xs text-amber-950 font-medium cursor-pointer">
                          <input
                            type="checkbox"
                            checked={imageConsent}
                            onChange={(e) => setImageConsent(e.target.checked)}
                            className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                          />
                          <span className="leading-snug">
                            {t(
                              "grievanceHub.step1.consentLabel",
                              "I confirm this photo shows a real civic problem and consent to automated AI analysis to identify observable defects."
                            )}
                          </span>
                        </label>
                      </div>
                    )}
                  </div>

                  {/* Form Error */}
                  {formError && (
                    <Alert variant="danger" title="Validation Notice">
                      <p className="text-xs text-rose-800">{formError}</p>
                    </Alert>
                  )}

                  {/* Submit Button */}
                  <div className="pt-3">
                    <Button
                      type="submit"
                      variant="primary"
                      isLoading={grievanceLoading}
                      disabled={description.trim().length < 20 || (uploadedImageId && !imageConsent)}
                      className="w-full sm:w-auto flex items-center justify-center gap-2"
                    >
                      <ArrowRight className="w-4 h-4" />
                      <span>
                        {grievanceLoading
                          ? t("grievanceHub.step1.submitting", "Analyzing problem, checking hazards & matching channels...")
                          : t("grievanceHub.step1.submitBtn", "Structure Complaint Draft")}
                      </span>
                    </Button>
                  </div>
                </form>
              </Card>
            </div>
          )}

          {/* --------------------------------------------------------------------- */}
          {/* STEP 2: REVIEW & EDIT DRAFT                                          */}
          {/* --------------------------------------------------------------------- */}
          {step === 2 && grievance && (
            <div className="space-y-6">
              {/* Emergency Hazard Notice (Prominent & Non-dismissable if safety_risk) */}
              {grievance.safety_risk && (
                <div className="rounded-xl border-2 border-rose-500 bg-rose-50 p-5 text-rose-950 shadow-sm space-y-2">
                  <div className="flex items-center gap-2 text-rose-700 font-bold text-sm uppercase tracking-wide">
                    <ShieldAlert className="w-5 h-5 animate-pulse text-rose-600" />
                    <span>{t("grievanceHub.emergencyAlert.title", "Immediate Safety Hazard Detected")}</span>
                  </div>
                  <p className="text-xs font-semibold leading-relaxed text-rose-900">
                    {grievance.emergency_notice ||
                      t(
                        "grievanceHub.emergencyAlert.text",
                        "If anyone is in immediate danger, contact local emergency services (112 / 100) first. CivicLens is not an emergency response service."
                      )}
                  </p>
                  {grievance.matched_safety_rules?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {grievance.matched_safety_rules.map((rule, idx) => (
                        <span key={idx} className="text-[10px] px-2 py-0.5 rounded bg-rose-200 text-rose-900 font-mono">
                          Safety Signal: {rule.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Analysis Mode & Warnings Banner */}
              {grievance.warnings?.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 space-y-1">
                  <span className="font-semibold text-slate-800">Pipeline Integrity Notices:</span>
                  <ul className="list-disc list-inside space-y-0.5 text-slate-600">
                    {grievance.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Draft Review Card */}
              <Card className="p-6 space-y-6 bg-white border-slate-200">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
                  <div className="space-y-0.5">
                    <h3 className="text-base font-bold text-slate-900">
                      {t("grievanceHub.step2.title", "Review & Refine Complaint Draft")}
                    </h3>
                    <p className="text-xs text-slate-500">
                      {t(
                        "grievanceHub.step2.subtitle",
                        "Inspect the structured draft below. All observations from photos require your explicit confirmation before inclusion."
                      )}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[11px] px-2 py-1 rounded bg-slate-100 text-slate-700 font-mono">
                      Mode: {grievance.analysis_mode === "ai" ? "Gemini AI" : "Rule-Based"}
                    </span>
                    <Badge variant={grievance.safety_risk ? "danger" : "primary"}>
                      Severity: {grievance.severity?.toUpperCase()}
                    </Badge>
                  </div>
                </div>

                {/* Category Confirmation / Override */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-800">
                      {t("grievanceHub.step2.categoryTitle", "Identified Category")}
                    </span>
                    {grievance.category_confidence === "needs_confirmation" && (
                      <span className="text-amber-700 font-semibold bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                        Confirmation Recommended
                      </span>
                    )}
                  </div>

                  {grievance.category_confidence === "needs_confirmation" && (
                    <p className="text-xs text-amber-800 bg-amber-50 p-2.5 rounded-lg border border-amber-200">
                      {t(
                        "grievanceHub.step2.categoryConfidenceConfirm",
                        "AI classification differs from keyword rules. Please verify the category above."
                      )}
                    </p>
                  )}

                  <div className="flex flex-wrap gap-2">
                    {CATEGORIES.map((cat) => (
                      <button
                        key={cat.id}
                        type="button"
                        onClick={() => setEditedCategory(cat.id)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5 cursor-pointer ${
                          editedCategory === cat.id
                            ? "bg-blue-600 text-white border-blue-600 font-bold"
                            : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                        }`}
                      >
                        <span>{cat.icon}</span>
                        <span>{t(`grievanceHub.categories.${cat.id}`, cat.id)}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Severity Selector & Floor Notice */}
                <div className="space-y-2 pt-2 border-t border-slate-100">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-slate-800">
                      {t("grievanceHub.step2.severityTitle", "Assessed Severity")}
                    </span>
                    {grievance.safety_risk && (
                      <span className="text-rose-700 font-semibold text-[11px]">
                        Floor Enforced: Hazard present
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {SEVERITIES.map((sev) => {
                      const disabled = isSeverityBelowFloor(sev);
                      return (
                        <button
                          key={sev}
                          type="button"
                          disabled={disabled}
                          onClick={() => setEditedSeverity(sev)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors capitalize cursor-pointer ${
                            editedSeverity === sev
                              ? "bg-slate-900 text-white border-slate-900 font-bold"
                              : disabled
                              ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed opacity-60"
                              : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                          }`}
                        >
                          {t(`grievanceHub.severities.${sev}`, sev)}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Editable Subject */}
                <div className="space-y-1 pt-2 border-t border-slate-100">
                  <label className="block text-xs font-semibold text-slate-800">
                    {t("grievanceHub.step2.subjectLabel", "Subject Line")}
                  </label>
                  <input
                    type="text"
                    value={editedSubject}
                    onChange={(e) => setEditedSubject(e.target.value)}
                    maxLength={200}
                    className="w-full px-3.5 py-2 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 font-semibold text-slate-900"
                  />
                </div>

                {/* Editable Body */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <label className="font-semibold text-slate-800">
                      {t("grievanceHub.step2.bodyLabel", "Complaint Representation Body")}
                    </label>
                    <span className="font-mono text-slate-400 text-[11px]">
                      {editedBody.length} characters
                    </span>
                  </div>
                  <textarea
                    rows={8}
                    value={editedBody}
                    onChange={(e) => setEditedBody(e.target.value)}
                    maxLength={5000}
                    className="w-full px-4 py-3 text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed font-normal"
                  />
                </div>

                {/* Verbatim Location Line */}
                {editedLocation && (
                  <div className="space-y-1">
                    <label className="block text-xs font-semibold text-slate-700">
                      {t("grievanceHub.step2.locationLine", "Declared Location")}
                    </label>
                    <input
                      type="text"
                      value={editedLocation}
                      onChange={(e) => setEditedLocation(e.target.value)}
                      maxLength={250}
                      className="w-full px-3.5 py-1.5 text-xs rounded-lg border border-slate-200 bg-slate-50 text-slate-700"
                    />
                  </div>
                )}

                {/* Photo Observations Checklist (explicit citizen opt-in) */}
                {grievance.draft?.observations?.length > 0 && (
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-3">
                    <div className="space-y-0.5">
                      <span className="text-xs font-bold text-slate-900">
                        {t("grievanceHub.step2.photoObservationsTitle", "AI Photo Observations (Review & Confirm)")}
                      </span>
                      <p className="text-[11px] text-slate-500">
                        {t(
                          "grievanceHub.step2.photoObservationsDesc",
                          "Check the observations you wish to add into the complaint text:"
                        )}
                      </p>
                    </div>

                    <div className="space-y-2">
                      {grievance.draft.observations.map((obs) => (
                        <label
                          key={obs.item_id}
                          className="flex items-start gap-2.5 text-xs text-slate-800 bg-white p-2.5 rounded-lg border border-slate-200 cursor-pointer hover:border-slate-300 transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={obs.confirmed}
                            onChange={(e) => toggleObservation(obs.item_id, e.target.checked)}
                            className="mt-0.5 rounded text-blue-600 focus:ring-blue-500"
                          />
                          <span className="leading-snug">{obs.text}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}

                {/* Missing Details Hints */}
                {grievance.missing_details?.length > 0 && (
                  <div className="p-4 rounded-xl bg-amber-50/60 border border-amber-200 space-y-2">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-amber-950">
                      <HelpCircle className="w-4 h-4 text-amber-600" />
                      <span>{t("grievanceHub.step2.missingDetailsTitle", "Missing Details for a Stronger Complaint")}</span>
                    </div>
                    <ul className="list-disc list-inside space-y-1 text-xs text-amber-900">
                      {grievance.missing_details.map((q, idx) => (
                        <li key={idx}>{q}</li>
                      ))}
                    </ul>
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() => setShowRetryModal(true)}
                        className="text-xs font-semibold text-blue-700 hover:text-blue-900 cursor-pointer flex items-center gap-1"
                      >
                        <RefreshCw className="w-3 h-3" />
                        <span>{t("grievanceHub.step2.retryPrompt", "Re-analyze with New Details")}</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Curated Official Reporting Channels */}
                <div className="space-y-3 pt-2 border-t border-slate-100">
                  <div className="space-y-0.5">
                    <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      {t("grievanceHub.step2.channelsTitle", "Official Reporting Channels (Curated Directory)")}
                    </h4>
                    <p className="text-[11px] text-slate-500">
                      {t(
                        "grievanceHub.step2.channelsDesc",
                        "Verified government departments and portals handling this category in your area:"
                      )}
                    </p>
                  </div>

                  {grievance.channels?.channels?.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {grievance.channels.channels.map((ch) => (
                        <div
                          key={ch.portal_id}
                          className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-2 flex flex-col justify-between"
                        >
                          <div className="space-y-1">
                            <div className="flex items-start justify-between gap-2">
                              <h5 className="text-xs font-bold text-slate-900 leading-snug">{ch.name}</h5>
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 font-mono font-semibold">
                                Vetted
                              </span>
                            </div>
                            <p className="text-[11px] text-blue-900 font-medium">{ch.department}</p>
                            <p className="text-[11px] text-slate-500">{ch.coverage_area}</p>
                            {ch.caution_notes && (
                              <p className="text-[11px] text-amber-900 bg-amber-50 p-1.5 rounded border border-amber-200">
                                {ch.caution_notes}
                              </p>
                            )}
                          </div>

                          <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                            <span className="text-[10px] text-slate-400 font-mono">{ch.domain_hint}</span>
                            <a
                              href={ch.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800"
                            >
                              <span>Official Portal</span>
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-xs">
                      <span className="font-semibold text-slate-800">
                        {t("grievanceHub.step2.genericGuidanceTitle", "General Redressal Guidance:")}
                      </span>
                      <ul className="list-disc list-inside space-y-1 text-slate-600">
                        {(grievance.channels?.generic_guidance || []).map((guide, idx) => (
                          <li key={idx}>{guide}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Draft Hash & Actions Footer */}
                <div className="pt-4 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="text-[11px] text-slate-400 font-mono truncate max-w-xs">
                    Draft Hash: {grievance.draft_hash?.slice(0, 16)}...
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="secondary" size="sm" onClick={handleSaveDraft} isLoading={savingDraft}>
                      {t("grievanceHub.step2.saveDraftBtn", "Update Draft")}
                    </Button>

                    <Button variant="secondary" size="sm" onClick={handleCopyDraft}>
                      <Copy className="w-3.5 h-3.5 mr-1" />
                      <span>{copiedToast ? t("grievanceHub.step2.copiedToast", "Copied!") : t("grievanceHub.step2.copyBtn", "Copy")}</span>
                    </Button>

                    <Button variant="secondary" size="sm" onClick={handlePrint}>
                      <Printer className="w-3.5 h-3.5 mr-1" />
                      <span>{t("grievanceHub.step2.printBtn", "Print")}</span>
                    </Button>

                    <Button variant="primary" size="sm" onClick={() => setStep(3)}>
                      <span>{t("grievanceHub.step2.proceedToApproveBtn", "Proceed to Demo Tracking")}</span>
                      <ArrowRight className="w-3.5 h-3.5 ml-1" />
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* --------------------------------------------------------------------- */}
          {/* STEP 3: AUTHORIZE DEMO REGISTRATION                                  */}
          {/* --------------------------------------------------------------------- */}
          {step === 3 && grievance && (
            <div className="max-w-2xl mx-auto space-y-6">
              <Card className="p-6 space-y-5 bg-white border-slate-200">
                <div className="space-y-1">
                  <h3 className="text-base font-bold text-slate-900">
                    {t("grievanceHub.step3.title", "Citizen Authorization & Review Binding")}
                  </h3>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    {t(
                      "grievanceHub.step3.desc",
                      "To register this complaint in your CivicLens demonstration dashboard, verify that you have reviewed the text and authorize creating a simulated tracking record."
                    )}
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="font-semibold text-slate-500">Subject:</span>
                    <span className="font-bold text-slate-900">{grievance.draft?.subject_line}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-semibold text-slate-500">Category:</span>
                    <span className="capitalize">{grievance.category?.replace(/_/g, " ")}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="font-semibold text-slate-500">Assessed Severity:</span>
                    <span className="capitalize font-semibold">{grievance.severity}</span>
                  </div>
                  {grievance.location_text && (
                    <div className="flex justify-between">
                      <span className="font-semibold text-slate-500">Location:</span>
                      <span>{grievance.location_text}</span>
                    </div>
                  )}
                </div>

                {/* Cryptographic SHA-256 Hash Binding Display */}
                <div className="p-3.5 rounded-lg border border-blue-200 bg-blue-50/70 space-y-1.5 text-xs text-blue-950">
                  <span className="font-bold block">
                    {t("grievanceHub.step3.hashLabel", "Draft Integrity SHA-256 Hash:")}
                  </span>
                  <p className="font-mono text-[11px] bg-white p-2 rounded border border-blue-200 break-all text-slate-800">
                    {grievance.draft_hash}
                  </p>
                  <p className="text-[11px] text-blue-800">
                    {t(
                      "grievanceHub.step3.hashDesc",
                      "Cryptographically binds this demonstration record to your exact approved text."
                    )}
                  </p>
                </div>

                <div className="pt-3 flex items-center justify-between gap-3">
                  <Button variant="secondary" onClick={() => setStep(2)}>
                    <ArrowLeft className="w-4 h-4 mr-1" />
                    <span>{t("grievanceHub.step3.cancelBtn", "Return to Review")}</span>
                  </Button>

                  <Button variant="primary" onClick={handleConfirmRegistration} isLoading={approving}>
                    <Check className="w-4 h-4 mr-1" />
                    <span>{t("grievanceHub.step3.confirmBtn", "Authorize & Register Demo Record")}</span>
                  </Button>
                </div>
              </Card>
            </div>
          )}

          {/* --------------------------------------------------------------------- */}
          {/* STEP 4: SIMULATED TRACKING DASHBOARD                                  */}
          {/* --------------------------------------------------------------------- */}
          {step === 4 && grievance && (
            <div className="space-y-6">
              {/* Demo Badge Banner */}
              <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-[10px] px-2 py-0.5 rounded bg-blue-200 text-blue-950 tracking-wide uppercase">
                      SIMULATED DEMO
                    </span>
                    <span className="font-mono text-sm font-bold text-slate-900">
                      {grievance.demo?.demo_id || "DEMO-REGISTERED"}
                    </span>
                  </div>
                  <p className="text-xs text-blue-900 font-medium">{grievance.draft?.subject_line}</p>
                </div>

                <div className="flex items-center gap-2">
                  <Badge variant={grievance.demo?.status === "resolved" ? "success" : "primary"}>
                    {grievance.demo?.status?.replace(/_/g, " ").toUpperCase() || "REGISTERED"}
                  </Badge>
                </div>
              </div>

              {/* Status Stepper */}
              <Card className="p-6 space-y-6 bg-white border-slate-200">
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  {t("grievanceHub.step4.subtitle", "Track simulated progress through standard municipal resolution stages.")}
                </h4>

                {/* Progress bar */}
                <div className="space-y-2">
                  <div className="grid grid-cols-4 gap-2 text-center text-xs">
                    {[
                      { st: "registered", label: "1. Registered" },
                      { st: "under_review", label: "2. Under Review" },
                      { st: "in_progress", label: "3. In Progress" },
                      { st: "resolved", label: "4. Resolved" },
                    ].map(({ st, label }, idx) => {
                      const stages = ["registered", "under_review", "in_progress", "resolved"];
                      const currentIdx = stages.indexOf(grievance.demo?.status || "registered");
                      const isCurrent = currentIdx === idx;
                      const isDone = currentIdx > idx;

                      return (
                        <div
                          key={st}
                          className={`p-2.5 rounded-lg font-medium transition-colors ${
                            isCurrent
                              ? "bg-blue-600 text-white font-bold shadow-xs"
                              : isDone
                              ? "bg-emerald-50 text-emerald-800 font-semibold border border-emerald-200"
                              : "bg-slate-100 text-slate-400"
                          }`}
                        >
                          {label}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Advance Simulated Status Control */}
                {grievance.demo?.status !== "resolved" && (
                  <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
                    <span className="text-xs font-bold text-slate-800 block">
                      {t("grievanceHub.step4.advanceBtn", "Simulate Next Status Step")}
                    </span>
                    <div className="flex flex-col sm:flex-row gap-2">
                      <input
                        type="text"
                        value={simulatedNote}
                        onChange={(e) => setSimulatedNote(e.target.value)}
                        placeholder={t(
                          "grievanceHub.step4.advanceNotePlaceholder",
                          "Optional simulated note (e.g. Municipal inspector visited the site)..."
                        )}
                        maxLength={200}
                        className="flex-1 px-3.5 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                      />
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={handleAdvanceStatus}
                        isLoading={advancingStatus}
                        className="shrink-0"
                      >
                        <RefreshCw className="w-3.5 h-3.5 mr-1" />
                        <span>Advance Status</span>
                      </Button>
                    </div>
                  </div>
                )}

                {/* Status Timeline History */}
                <div className="space-y-3 pt-2 border-t border-slate-100">
                  <h5 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                    {t("grievanceHub.step4.timelineTitle", "Simulated Status Timeline")}
                  </h5>

                  <div className="divide-y divide-slate-100">
                    {(grievance.demo?.events || []).map((ev, idx) => (
                      <div key={idx} className="py-2.5 flex items-start justify-between gap-4 text-xs">
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900 capitalize">
                              {ev.new_state?.replace(/_/g, " ")}
                            </span>
                            <span className="text-[10px] text-slate-400">by {ev.actor}</span>
                          </div>
                          {ev.note && <p className="text-slate-600 text-[11px]">{ev.note}</p>}
                        </div>
                        <span className="text-[10px] text-slate-400 font-mono shrink-0">
                          {new Date(ev.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="pt-4 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex gap-2">
                    <Button variant="secondary" size="sm" onClick={handleCopyDraft}>
                      <Copy className="w-3.5 h-3.5 mr-1" />
                      <span>{copiedToast ? "Copied!" : "Copy Representation"}</span>
                    </Button>
                    <Button variant="secondary" size="sm" onClick={handlePrint}>
                      <Printer className="w-3.5 h-3.5 mr-1" />
                      <span>Print</span>
                    </Button>
                  </div>

                  <div className="flex gap-2">
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => setDeletingId(grievance.id)}
                    >
                      <Trash2 className="w-3.5 h-3.5 mr-1" />
                      <span>Delete</span>
                    </Button>
                    <Button variant="primary" size="sm" onClick={handleStartFresh}>
                      <span>{t("grievanceHub.step4.newComplaintBtn", "Start Another Complaint")}</span>
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: MY COMPLAINTS LIST                                                 */}
      {/* ========================================================================= */}
      {activeTab === "history" && (
        <div className="space-y-4">
          {/* Filter Chips */}
          <div className="flex items-center justify-between gap-3">
            <div className="flex gap-2 text-xs">
              {[
                { id: "all", label: t("grievanceHub.myComplaints.filterAll", "All States") },
                { id: "drafts", label: t("grievanceHub.myComplaints.filterDrafts", "Drafts Only") },
                { id: "demo", label: t("grievanceHub.myComplaints.filterDemo", "Demo Registered") },
              ].map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setHistoryFilter(f.id)}
                  className={`px-3 py-1.5 rounded-lg border font-medium cursor-pointer transition-colors ${
                    historyFilter === f.id
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <Button variant="primary" size="sm" onClick={handleStartFresh}>
              <span>+ New Complaint</span>
            </Button>
          </div>

          {/* List Content */}
          {listLoading ? (
            <div className="py-12 flex justify-center">
              <Spinner size="lg" />
            </div>
          ) : filteredHistory.length === 0 ? (
            <EmptyState
              icon={FileText}
              title={t("grievanceHub.myComplaints.emptyTitle", "No Complaints Prepared Yet")}
              description={t(
                "grievanceHub.myComplaints.emptyDesc",
                "You haven't prepared any civic complaints yet. Click 'New Complaint' to get started."
              )}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredHistory.map((rec) => (
                <Card
                  key={rec.id}
                  className="p-5 space-y-3 bg-white border-slate-200 hover:border-slate-300 transition-colors flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        {rec.demo?.demo_id ? (
                          <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                            {rec.demo.demo_id}
                          </span>
                        ) : (
                          <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                            Draft
                          </span>
                        )}
                        <Badge variant={rec.severity === "urgent" ? "danger" : "primary"} size="sm">
                          {rec.severity?.toUpperCase()}
                        </Badge>
                      </div>

                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(rec.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <h4 className="text-sm font-bold text-slate-900 leading-snug line-clamp-1">
                      {rec.draft?.subject_line || rec.description.slice(0, 50)}
                    </h4>

                    <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed">
                      {rec.draft?.body || rec.description}
                    </p>

                    {rec.location_text && (
                      <div className="text-[11px] text-slate-500 flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-slate-400" />
                        <span className="truncate">{rec.location_text}</span>
                      </div>
                    )}
                  </div>

                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                    <span className="text-[11px] text-slate-500 capitalize">
                      {rec.category?.replace(/_/g, " ")}
                    </span>

                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => setDeletingId(rec.id)}
                      >
                        <Trash2 className="w-3.5 h-3.5 text-rose-500" />
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleOpenFromHistory(rec)}
                      >
                        <span>Open</span>
                        <ChevronRight className="w-3.5 h-3.5 ml-1" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingId && (
        <Modal
          isOpen={Boolean(deletingId)}
          onClose={() => setDeletingId(null)}
          title="Delete Complaint Record"
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-600 leading-relaxed">
              {t(
                "grievanceHub.step4.deleteConfirm",
                "Are you sure you want to permanently delete this complaint draft and all associated files?"
              )}
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setDeletingId(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={async () => {
                  if (deletingId === grievance?.id) {
                    await deleteActiveGrievance();
                  } else {
                    await deletePastRecord(deletingId);
                  }
                  setDeletingId(null);
                  refreshList();
                }}
              >
                Delete Permanently
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Retry Modal with Additional Details */}
      {showRetryModal && (
        <Modal
          isOpen={showRetryModal}
          onClose={() => setShowRetryModal(false)}
          title="Provide Additional Details for Re-Analysis"
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-600">
              Add specific landmarks, duration, or department hints to help the AI structure an even more precise complaint:
            </p>
            <textarea
              rows={4}
              value={retryAdditionalDetails}
              onChange={(e) => setRetryAdditionalDetails(e.target.value)}
              placeholder="e.g., Near water tank on Ward 12, problem started after underground pipeline leak..."
              maxLength={500}
              className="w-full px-3 py-2 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" size="sm" onClick={() => setShowRetryModal(false)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" onClick={handleRetrySubmit}>
                Re-Analyze Draft
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

export default Grievance;
