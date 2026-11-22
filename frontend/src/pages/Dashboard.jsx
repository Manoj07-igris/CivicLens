import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Bot,
  ArrowRight,
  FileText,
  GitCompare,
  ShieldCheck,
  Compass,
  LifeBuoy,
  UploadCloud,
  Sparkles,
  Search,
  FileEdit,
} from "lucide-react";
import { PageHeader } from "../components/ui/PageHeader";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../components/ui/Card";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { RecentActivity } from "../components/dashboard/RecentActivity";
import { RecentDocuments } from "../components/dashboard/RecentDocuments";
import { SystemStatusCard } from "../components/dashboard/SystemStatusCard";
import { StorageManagementCard } from "../components/dashboard/StorageManagementCard";
import { useLanguage } from "../hooks/useLanguage";
import { useBackendStatus } from "../hooks/useBackendStatus";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { documentService } from "../services/documentService";

export function Dashboard() {
  const { t, language } = useLanguage();
  const { status, info, lastChecked, error, retry } = useBackendStatus();
  const {
    status: sysStatus,
    stats: sysStats,
    refetch: refetchSystem,
    triggerBackup,
    triggerMaintenance,
  } = useSystemStatus(false);
  const [recentDocs, setRecentDocs] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    documentService
      .getDocuments()
      .then((docs) => setRecentDocs(docs || []))
      .catch(() => setRecentDocs([]));
  }, []);

  useEffect(() => {
    document.title = language === "ta"
      ? "டாஷ்போர்டு – சிவிக்லென்ஸ்"
      : "Dashboard – CivicLens";
  }, [language]);

  const promptSuggestions = [
    t("dashboard.assistantCard.prompt1"),
    t("dashboard.assistantCard.prompt2"),
    t("dashboard.assistantCard.prompt3"),
    t("dashboard.assistantCard.prompt4"),
  ];

  const handleSuggestionClick = (promptText) => {
    navigate(`/assistant?q=${encodeURIComponent(promptText)}`, {
      state: { prompt: promptText },
    });
  };

  const modules = [
    {
      to: "/documents",
      title: t("landing.capabilities.policyIntelTitle"),
      desc: t("landing.capabilities.policyIntelDesc"),
      icon: FileText,
      badge: "PDF Analysis",
    },
    {
      to: "/compare",
      title: t("landing.capabilities.changeDetectionTitle"),
      desc: t("landing.capabilities.changeDetectionDesc"),
      icon: GitCompare,
      badge: "Diff Engine",
    },
    {
      to: "/verify",
      title: t("landing.capabilities.factCheckTitle"),
      desc: t("landing.capabilities.factCheckDesc"),
      icon: ShieldCheck,
      badge: "Verdicts",
    },
    {
      to: "/services",
      title: t("landing.capabilities.publicServiceTitle"),
      desc: t("landing.capabilities.publicServiceDesc"),
      icon: Compass,
      badge: "Procedures",
    },
    {
      to: "/grievance",
      title: t("landing.capabilities.grievanceTitle"),
      desc: t("landing.capabilities.grievanceDesc"),
      icon: LifeBuoy,
      badge: "Petitions",
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* 1. Welcome Header */}
      <PageHeader
        title={t("dashboard.welcome")}
        description={t("dashboard.welcomeSubtitle")}
        actions={<LanguageSwitcher />}
      />

      {/* 2. System Status & Backend Connectivity */}
      <SystemStatusCard
        status={status}
        info={info}
        lastChecked={lastChecked}
        error={error}
        onRetry={retry}
      />

      {/* 2.5 System Statistics Overview */}
      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {t("dashboard.stats.title", "System Overview & Records")}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-4 bg-slate-50/50 hover:bg-white transition-colors border-slate-200">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500">
                  {t("dashboard.stats.documents", "Documents & Index")}
                </p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {sysStats?.documents_count ?? 0}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {sysStats?.indexed_documents_count ?? 0} indexed • {sysStats?.official_sources_count ?? 0} official
                </p>
              </div>
              <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center">
                <FileText className="w-4 h-4" />
              </div>
            </div>
          </Card>

          <Card className="p-4 bg-slate-50/50 hover:bg-white transition-colors border-slate-200">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500">
                  {t("dashboard.stats.verifications", "Comparisons & Checks")}
                </p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {sysStats?.verifications_count ?? 0}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {sysStats?.comparisons_count ?? 0} diffs • {sysStats?.verifications_count ?? 0} verified
                </p>
              </div>
              <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
                <ShieldCheck className="w-4 h-4" />
              </div>
            </div>
          </Card>

          <Card className="p-4 bg-slate-50/50 hover:bg-white transition-colors border-slate-200">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500">
                  {t("dashboard.stats.services", "Public Services")}
                </p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {sysStats?.service_guides_count ?? 0}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {sysStats?.service_guides_count ?? 0} guides • {sysStats?.portals_count ?? 0} portals
                </p>
              </div>
              <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center">
                <Compass className="w-4 h-4" />
              </div>
            </div>
          </Card>

          <Card className="p-4 bg-slate-50/50 hover:bg-white transition-colors border-slate-200">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500">
                  {t("dashboard.stats.grievances", "Civic Grievances")}
                </p>
                <p className="text-2xl font-bold text-slate-900 mt-1">
                  {sysStats?.grievances_count ?? 0}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {sysStats?.grievances_count ?? 0} petitions • {sysStats?.browser_sessions_count ?? 0} demo sessions
                </p>
              </div>
              <div className="w-8 h-8 rounded-lg bg-rose-100 text-rose-700 flex items-center justify-center">
                <LifeBuoy className="w-4 h-4" />
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* 3. AI Assistant Shortcut Banner Card */}
      <Card className="bg-gradient-to-br from-blue-900 via-blue-950 to-slate-900 text-white border-blue-800 shadow-md overflow-hidden">
        <CardContent className="p-6 sm:p-8 space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
            <div className="space-y-2 max-w-2xl">
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-800/80 text-blue-200 text-xs font-semibold border border-blue-700">
                <Sparkles className="w-3.5 h-3.5" />
                <span>{t("dashboard.assistantCard.badge")}</span>
              </div>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
                {t("dashboard.assistantCard.title")}
              </h2>
              <p className="text-sm text-blue-200 leading-relaxed">
                {t("dashboard.assistantCard.description")}
              </p>
            </div>

            <Link to="/assistant" className="flex-shrink-0">
              <Button
                variant="primary"
                size="md"
                className="bg-white hover:bg-slate-100 text-blue-950 font-semibold shadow-md active:bg-slate-200"
                icon={ArrowRight}
                iconPosition="right"
              >
                {t("dashboard.assistantCard.openAssistant")}
              </Button>
            </Link>
          </div>

          {/* Suggestion Chips */}
          <div className="pt-4 border-t border-white/10 space-y-3">
            <span className="text-xs font-semibold text-blue-300 uppercase tracking-wider block">
              {t("dashboard.assistantCard.suggestionsTitle")}
            </span>
            <div className="flex flex-wrap gap-2">
              {promptSuggestions.map((prompt, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSuggestionClick(prompt)}
                  className="text-left text-xs bg-white/10 hover:bg-white/20 text-white px-3 py-2 rounded-lg border border-white/15 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white flex items-center gap-2 group cursor-pointer"
                >
                  <Bot className="w-3.5 h-3.5 text-blue-300 group-hover:text-white flex-shrink-0" />
                  <span className="truncate max-w-xs sm:max-w-md">{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 4. Quick Actions */}
      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
          {t("dashboard.quickActions.title")}
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <Link to="/documents">
            <Button variant="outline" className="w-full justify-start h-auto py-3 px-4" icon={UploadCloud}>
              {t("dashboard.quickActions.uploadPdf")}
            </Button>
          </Link>
          <Link to="/compare">
            <Button variant="outline" className="w-full justify-start h-auto py-3 px-4" icon={GitCompare}>
              {t("dashboard.quickActions.compareDocs")}
            </Button>
          </Link>
          <Link to="/verify">
            <Button variant="outline" className="w-full justify-start h-auto py-3 px-4" icon={Search}>
              {t("dashboard.quickActions.verifyClaim")}
            </Button>
          </Link>
          <Link to="/grievance">
            <Button variant="outline" className="w-full justify-start h-auto py-3 px-4" icon={FileEdit}>
              {t("dashboard.quickActions.draftComplaint")}
            </Button>
          </Link>
        </div>
      </section>

      {/* 5. Five Module Cards */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">
            {t("dashboard.modules.title")}
          </h2>
          <p className="text-xs text-slate-500">
            {t("dashboard.modules.subtitle")}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {modules.map((m) => {
            const Icon = m.icon;
            return (
              <Card key={m.to} className="flex flex-col justify-between hover:border-blue-300 transition-all">
                <CardHeader>
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center">
                      <Icon className="w-5 h-5" />
                    </div>
                    <Badge variant="outline" size="sm">
                      {m.badge}
                    </Badge>
                  </div>
                  <CardTitle>{m.title}</CardTitle>
                  <CardDescription>{m.desc}</CardDescription>
                </CardHeader>
                <CardFooter>
                  <Link to={m.to} className="w-full">
                    <Button variant="outline" size="sm" className="w-full" icon={ArrowRight} iconPosition="right">
                      {t("dashboard.modules.open")}
                    </Button>
                  </Link>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      </section>

      {/* 6. Recent Activity and Recent Documents */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RecentActivity />
        <RecentDocuments documents={recentDocs} />
      </section>

      {/* 7. Storage Management & Local Database */}
      <section>
        <StorageManagementCard
          status={sysStatus}
          stats={sysStats}
          onTriggerBackup={triggerBackup}
          onTriggerMaintenance={triggerMaintenance}
          onDataDeleted={() => {
            refetchSystem();
            documentService
              .getDocuments()
              .then((docs) => setRecentDocs(docs || []))
              .catch(() => setRecentDocs([]));
          }}
        />
      </section>
    </div>
  );
}
