import React, { useState } from "react";
import {
  ArrowRight,
  Mail,
  User,
  CheckCircle2,
  Trash2,
  ShieldAlert,
  Wrench,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Textarea } from "../components/ui/Textarea";
import { Select } from "../components/ui/Select";
import { Alert } from "../components/ui/Alert";
import { Spinner } from "../components/ui/Spinner";
import { Skeleton } from "../components/ui/Skeleton";
import { Modal } from "../components/ui/Modal";
import { FileDropzone } from "../components/ui/FileDropzone";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { useToast } from "../hooks/useToast";
import { useLanguage } from "../hooks/useLanguage";

export function DesignSystem() {
  const { t } = useLanguage();
  const { showToast } = useToast();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [modalConfirmed, setModalConfirmed] = useState(false);
  const [testInput, setTestInput] = useState("");
  const [testSelect, setTestSelect] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);

  const triggerToast = (type) => {
    const messages = {
      info: "Policy document uploaded successfully for indexing.",
      success: "Verified! Official Gazette #481 matches the claim.",
      warning: "Note: This government order was superseded in 2024.",
      error: "Unable to verify claim: Source document unreadable.",
    };
    showToast({
      message: messages[type],
      type,
    });
  };

  return (
    <div className="space-y-12 pb-16">
      {/* Page Header */}
      <PageHeader
        title={t("pages.designSystem.title")}
        description={t("pages.designSystem.description")}
        badge={<Badge variant="primary">Internal Dev Catalog</Badge>}
        actions={<LanguageSwitcher />}
      />

      {/* 1. Brand & Typography Showcase */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2 flex items-center gap-2">
          <span>1. Brand Tokens & Bilingual Typography</span>
          <Badge variant="outline" size="sm">Inter & Noto Sans Tamil</Badge>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>English Typography (Inter)</CardTitle>
              <CardDescription>Latin font family for high legibility in dense civic texts.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <h1 className="text-2xl font-bold text-slate-900">H1: Civic Intelligence for Citizens</h1>
              <h2 className="text-xl font-semibold text-slate-800">H2: Policy Intelligence & Fact Check</h2>
              <h3 className="text-base font-semibold text-slate-800">H3: Official Gazette Verification</h3>
              <p className="text-sm text-slate-600 leading-relaxed">
                CivicLens bridges the divide between complex administrative circulars and public comprehension.
                Every piece of information is backed by direct paragraph-level citations.
              </p>
            </CardContent>
            <CardFooter>
              <span className="text-xs text-slate-400">Caption / Metadata: Verified on Nov 19, 2026 • 25 MB PDF</span>
            </CardFooter>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tamil Typography (Noto Sans Tamil)</CardTitle>
              <CardDescription>Offline Noto Sans Tamil with comfortable line-height.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2" lang="ta">
              <h1 className="text-2xl font-bold text-slate-900">H1: குடிமக்களுக்கான நுண்ணறிவு தளம்</h1>
              <h2 className="text-xl font-semibold text-slate-800">H2: அரசாணைகள் & உண்மை சரிபார்ப்பு</h2>
              <h3 className="text-base font-semibold text-slate-800">H3: அதிகாரப்பூர்வ ஆவண சான்றுகள்</h3>
              <p className="text-sm text-slate-600 leading-relaxed font-tamil">
                சிக்கலான அரசு ஆவணங்கள் மற்றும் அறிவிப்புகளை மக்கள் எளிதில் புரிந்துகொள்ளவும், 
                சரிபார்க்கவும் மற்றும் அதற்கேற்ப செயல்படவும் சிவிக்லென்ஸ் உதவுகிறது.
              </p>
            </CardContent>
            <CardFooter>
              <span className="text-xs text-slate-400 font-tamil">குறிப்பு: நவம்பர் 19, 2026 அன்று சரிபார்க்கப்பட்டது</span>
            </CardFooter>
          </Card>
        </div>

        {/* Logos & Switchers */}
        <div className="flex flex-wrap items-center gap-6 p-4 bg-white rounded-xl border border-slate-200">
          <Logo size="sm" to="" />
          <Logo size="md" to="" showTagline={true} />
          <Logo size="lg" to="" />
          <div className="ml-auto flex items-center gap-4">
            <LanguageSwitcher />
            <LanguageSwitcher variant="compact" />
          </div>
        </div>
      </section>

      {/* 2. Fact Verification Badges & General Badges */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2 flex items-center gap-2">
          <span>2. Fact Verification Categories & Badges</span>
          <Badge variant="primary" size="sm">Core Verification Schema</Badge>
        </h2>

        <div className="p-6 bg-white rounded-2xl border border-slate-200 space-y-6">
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Official Fact Verification Verdicts (English & Tamil)
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl border border-emerald-200 bg-emerald-50/50 flex flex-col gap-2">
                <Badge variant="supported" size="md">Supported</Badge>
                <Badge variant="supported" size="sm">ஆதரிக்கப்பட்டது</Badge>
                <p className="text-xs text-emerald-900 mt-1">{t("verification.supportedDesc")}</p>
              </div>

              <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/50 flex flex-col gap-2">
                <Badge variant="contradicted" size="md">Contradicted</Badge>
                <Badge variant="contradicted" size="sm">முரண்பட்டது</Badge>
                <p className="text-xs text-rose-900 mt-1">{t("verification.contradictedDesc")}</p>
              </div>

              <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/50 flex flex-col gap-2">
                <Badge variant="unverified" size="md">Unverified</Badge>
                <Badge variant="unverified" size="sm">சரிபார்க்கப்படவில்லை</Badge>
                <p className="text-xs text-amber-900 mt-1">{t("verification.unverifiedDesc")}</p>
              </div>

              <div className="p-4 rounded-xl border border-purple-200 bg-purple-50/50 flex flex-col gap-2">
                <Badge variant="outdated" size="md">Outdated</Badge>
                <Badge variant="outdated" size="sm">காலாவதியானது</Badge>
                <p className="text-xs text-purple-900 mt-1">{t("verification.outdatedDesc")}</p>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Standard Badges
            </h3>
            <div className="flex flex-wrap items-center gap-2.5">
              <Badge variant="default">Default / Neutral</Badge>
              <Badge variant="primary">Primary Blue</Badge>
              <Badge variant="success">Success</Badge>
              <Badge variant="warning">Warning</Badge>
              <Badge variant="danger">Danger</Badge>
              <Badge variant="outline">Outline</Badge>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Buttons Showcase */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2">
          3. Button Variants, Sizes & States
        </h2>

        <div className="p-6 bg-white rounded-2xl border border-slate-200 space-y-6">
          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Variants (Size MD)
            </h3>
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary" icon={ArrowRight} iconPosition="right">Primary Action</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="ghost">Ghost Button</Button>
              <Button variant="danger" icon={Trash2}>Danger Action</Button>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Sizes
            </h3>
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" variant="primary">Small (sm)</Button>
              <Button size="md" variant="primary">Medium (md)</Button>
              <Button size="lg" variant="primary">Large (lg)</Button>
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
              Loading & Disabled States
            </h3>
            <div className="flex flex-wrap items-center gap-3">
              <Button isLoading={true}>Processing</Button>
              <Button variant="secondary" isLoading={true}>Loading</Button>
              <Button disabled={true}>Disabled State</Button>
              <Button variant="danger" disabled={true}>Disabled Danger</Button>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Form Controls */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2">
          4. Form Inputs, Textarea & Select
        </h2>

        <Card>
          <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Input
              label="Citizen Full Name"
              placeholder="e.g. Anandha Kumar"
              leftIcon={User}
              helperText="As printed on government photo identity"
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              required={true}
            />

            <Input
              label="Email Address (Validation Error Demo)"
              placeholder="citizen@domain.com"
              leftIcon={Mail}
              error="Please enter a valid official email address"
              defaultValue="invalid-email"
              required={true}
            />

            <Select
              label="Select Government Department"
              placeholder="Choose target department"
              options={[
                { value: "revenue", label: "Revenue & Disaster Management" },
                { value: "municipal", label: "Municipal Administration & Water" },
                { value: "civil_supplies", label: "Civil Supplies & Consumer Protection" },
                { value: "transport", label: "Transport & Road Safety" },
              ]}
              value={testSelect}
              onChange={(e) => setTestSelect(e.target.value)}
              helperText="Select which authority handles this inquiry"
            />

            <Select
              label="Select State (Disabled State)"
              disabled={true}
              options={[{ value: "tn", label: "Tamil Nadu" }]}
              value="tn"
              helperText="Locked to Tamil Nadu in prototype demo"
            />

            <div className="md:col-span-2">
              <Textarea
                label="Public Grievance or Policy Question"
                placeholder="Describe your inquiry in detail. Include specific notification numbers, dates, or locality..."
                rows={3}
                helperText="Tamil or English input supported"
              />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 5. Alerts & Notifications */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2">
          5. Alerts & System Messages
        </h2>

        <div className="space-y-3">
          <Alert variant="info" title="Evidence-Based Grounding Active">
            Every answer provided by the AI Agent is directly cited from uploaded official gazettes.
          </Alert>

          <Alert variant="success" title="Verification Passed">
            Gazette notification G.O. Ms. No. 112 matches the uploaded claim without discrepancies.
          </Alert>

          <Alert variant="warning" title="Outdated Notification Warning">
            A newer circular issued on March 2025 amends the eligibility criteria of this scheme.
          </Alert>

          <Alert
            variant="error"
            title="Untrusted PDF Sanitization Alert"
            dismissible={true}
            onDismiss={() => alert("Alert dismissed")}
          >
            A security check sanitized unrecognized macro elements from the uploaded PDF.
          </Alert>
        </div>
      </section>

      {/* 6. Spinners, Skeletons & Loaders */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2">
          6. Spinners & Skeleton Loaders
        </h2>

        <Card>
          <CardContent className="space-y-6">
            <div className="flex items-center gap-6">
              <Spinner size="sm" />
              <Spinner size="md" color="#2563eb" />
              <Spinner size="lg" color="#0d9488" />
            </div>

            <div className="space-y-2.5 max-w-md">
              <Skeleton height="1.25rem" width="60%" />
              <Skeleton height="0.875rem" width="90%" />
              <Skeleton height="0.875rem" width="75%" />
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 7. Interactive Modals & Toast Triggers */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2 flex items-center justify-between">
          <span>7. Interactive Modals & Toast Triggers</span>
          <Badge variant="primary" size="sm">Accessible Keyboard (Esc)</Badge>
        </h2>

        <Card>
          <CardContent className="space-y-6">
            {/* Modal demonstration */}
            <div>
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Modal / User Approval Dialog
              </h3>
              <p className="text-sm text-slate-600 mb-3">
                Used in later phases when the Central AI Agent requires citizen consent before executing actions.
              </p>
              <Button
                variant="primary"
                onClick={() => {
                  setModalConfirmed(false);
                  setIsModalOpen(true);
                }}
              >
                Open Confirmation Dialog
              </Button>

              {modalConfirmed && (
                <div className="mt-3 inline-flex items-center gap-2 text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-lg border border-emerald-200">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Action confirmed in dialog!</span>
                </div>
              )}
            </div>

            {/* Toast demonstration */}
            <div className="pt-4 border-t border-slate-100">
              <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Toast Notifications (Provider + Hook)
              </h3>
              <div className="flex flex-wrap gap-2.5">
                <Button variant="outline" size="sm" onClick={() => triggerToast("info")}>
                  Trigger Info Toast
                </Button>
                <Button variant="outline" size="sm" onClick={() => triggerToast("success")}>
                  Trigger Success Toast
                </Button>
                <Button variant="outline" size="sm" onClick={() => triggerToast("warning")}>
                  Trigger Warning Toast
                </Button>
                <Button variant="outline" size="sm" onClick={() => triggerToast("error")}>
                  Trigger Error Toast
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* 8. File Dropzone */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2">
          8. File Dropzone (PDF Acceptance UI)
        </h2>

        <Card>
          <CardContent className="space-y-3">
            <FileDropzone
              onFileSelect={(file) => setSelectedFile(file)}
            />
            {selectedFile && (
              <p className="text-xs text-emerald-700 font-medium">
                Dropzone callback received: {selectedFile.name} ({selectedFile.size} bytes)
              </p>
            )}
          </CardContent>
        </Card>
      </section>

      {/* 9. Empty & Error States */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2">
          9. Empty & Error States
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <EmptyState
            title="No Documents Uploaded"
            description="Upload government circulars or policy notifications to begin automatic question-answering."
            action={<Button size="sm">Upload Document</Button>}
          />

          <ErrorState
            title="Verification Service Unreachable"
            description="The local indexing service did not respond. Check your connection or retry."
            onRetry={() => alert("Retrying verification...")}
          />
        </div>
      </section>

      {/* 10. Central AI Agent & Function Calling Components */}
      <section className="space-y-4">
        <h2 className="text-xl font-bold text-slate-900 border-b pb-2 flex items-center justify-between">
          <span>10. Central AI Agent: Function Calling, Execution Timeline & Citizen Approval</span>
          <Badge variant="primary" size="sm">Phase 9</Badge>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Action Authorization Card Demo */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-600" />
                <span>Citizen Authorization Card</span>
              </CardTitle>
              <CardDescription>
                Presented when Gemini function calling requests an action requiring human authorization.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="p-3.5 rounded-xl border border-amber-300 bg-amber-50/90 text-amber-950 shadow-2xs space-y-2.5">
                <div className="flex items-start gap-2.5">
                  <ShieldAlert className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 space-y-2">
                    <div>
                      <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wide">
                        Citizen Authorization Required
                      </h4>
                      <p className="text-xs text-amber-800 mt-0.5 leading-relaxed">
                        The agent requests authorization to draft a formal grievance complaint for municipal review.
                      </p>
                    </div>
                    <div className="p-2 rounded-lg bg-white/80 border border-amber-200 text-[11px] font-mono text-amber-900 space-y-1">
                      <div>
                        <span className="font-semibold text-slate-600">Action:</span> draft_complaint
                      </div>
                      <div>
                        <span className="font-semibold text-slate-600">Parameters:</span> department="Revenue", ward=14
                      </div>
                    </div>
                    <div className="flex items-center gap-2 pt-1">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => showToast({ message: "Action authorized and simulated successfully.", type: "success" })}
                        className="h-7 text-xs bg-emerald-700 hover:bg-emerald-800 border-emerald-800"
                      >
                        Approve & Execute
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => showToast({ message: "Action declined by citizen.", type: "warning" })}
                        className="h-7 text-xs text-rose-700 hover:bg-rose-50 border-rose-300"
                      >
                        Deny & Cancel
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Tool Execution Pipeline & Citations Demo */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Wrench className="w-4 h-4 text-blue-600" />
                <span>Tool Activity Timeline & Verified Citations</span>
              </CardTitle>
              <CardDescription>
                Bounded multi-step execution pipeline with backend-verified excerpt chips.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 space-y-2.5">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    Intent:
                  </span>
                  <Badge variant="outline" size="sm" className="text-[10px] font-medium">
                    Policy Document Analysis
                  </Badge>
                  <span className="text-[10px] text-slate-400 font-mono">2 steps • 57.3ms</span>
                </div>

                {/* Simulated Steps */}
                <div className="space-y-1.5">
                  <div className="flex items-start gap-2 p-2 rounded-lg bg-white border border-slate-200 text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800 text-[11px]">Scan Policy Documents</span>
                        <span className="text-[10px] font-mono text-slate-400">15.2ms</span>
                      </div>
                      <p className="text-[11px] text-slate-600 mt-0.5">Discovered 2 ready document(s).</p>
                    </div>
                  </div>

                  <div className="flex items-start gap-2 p-2 rounded-lg bg-white border border-slate-200 text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800 text-[11px]">Retrieve Document Evidence</span>
                        <span className="text-[10px] font-mono text-slate-400">42.1ms</span>
                      </div>
                      <p className="text-[11px] text-slate-600 mt-0.5">Searched 'subsidy criteria' in tn_ev_policy.pdf: 3 passages (strong evidence).</p>
                    </div>
                  </div>
                </div>

                {/* Verified Citation Chips */}
                <div className="pt-1">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                    Verified Citations:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-900 border border-blue-200">
                      <span className="font-bold text-blue-700 font-mono">[E1]</span>
                      <span>Tamil Nadu EV Policy 2023</span>
                      <span className="text-[10px] bg-blue-200/80 text-blue-950 px-1 rounded font-semibold">p. 4</span>
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-50 text-blue-900 border border-blue-200">
                      <span className="font-bold text-blue-700 font-mono">[E2]</span>
                      <span>Tamil Nadu EV Policy 2023</span>
                      <span className="text-[10px] bg-blue-200/80 text-blue-950 px-1 rounded font-semibold">p. 9</span>
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Modal Dialog Component Instance */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Approve Grievance Submission"
        confirmText="Approve Draft"
        cancelText="Cancel"
        onConfirm={() => {
          setModalConfirmed(true);
          setIsModalOpen(false);
          showToast({
            message: "Citizen approved grievance draft successfully.",
            type: "success",
          });
        }}
      >
        <p className="mb-3">
          The Central AI Agent has drafted a formal grievance letter to the <strong>Municipal Administration Department</strong>.
        </p>
        <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs font-mono text-slate-700 space-y-1">
          <div><strong>Subject:</strong> Urgent repair of street drainage in Ward 14</div>
          <div><strong>Action:</strong> Controlled Demo Form Autofill simulation</div>
        </div>
        <p className="text-xs text-slate-500 mt-3">
          Press <strong>Escape</strong> or click Cancel to dismiss without changes.
        </p>
      </Modal>
    </div>
  );
}
