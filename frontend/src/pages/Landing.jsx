import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Bot,
  FileText,
  GitCompare,
  ShieldCheck,
  Compass,
  LifeBuoy,
  FileCode2,
  FileWarning,
  HelpCircle,
  Clock,
  Sparkles,
  Layers,
  Wrench,
  Database,
  CheckCircle2,
  Lock,
  UserCheck,
  AlertTriangle,
  Languages,
} from "lucide-react";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Card, CardHeader, CardTitle, CardDescription, CardFooter } from "../components/ui/Card";
import { useLanguage } from "../hooks/useLanguage";

export function Landing() {
  const { t, language } = useLanguage();

  useEffect(() => {
    document.title = language === "ta" 
      ? "சிவிக்லென்ஸ் – புரிந்து கொள்ளுங்கள். சரிபாருங்கள். செயல்படுங்கள்."
      : "CivicLens – Understand. Verify. Act.";
  }, [language]);

  const capabilities = [
    {
      to: "/documents",
      title: t("landing.capabilities.policyIntelTitle"),
      desc: t("landing.capabilities.policyIntelDesc"),
      icon: FileText,
      badgeColor: "primary",
    },
    {
      to: "/compare",
      title: t("landing.capabilities.changeDetectionTitle"),
      desc: t("landing.capabilities.changeDetectionDesc"),
      icon: GitCompare,
      badgeColor: "primary",
    },
    {
      to: "/verify",
      title: t("landing.capabilities.factCheckTitle"),
      desc: t("landing.capabilities.factCheckDesc"),
      icon: ShieldCheck,
      badgeColor: "success",
    },
    {
      to: "/services",
      title: t("landing.capabilities.publicServiceTitle"),
      desc: t("landing.capabilities.publicServiceDesc"),
      icon: Compass,
      badgeColor: "primary",
    },
    {
      to: "/grievance",
      title: t("landing.capabilities.grievanceTitle"),
      desc: t("landing.capabilities.grievanceDesc"),
      icon: LifeBuoy,
      badgeColor: "primary",
    },
  ];

  const problemPoints = [
    {
      title: t("landing.problem.p1Title"),
      desc: t("landing.problem.p1Desc"),
      icon: FileCode2,
      color: "text-blue-700 bg-blue-50 border-blue-200",
    },
    {
      title: t("landing.problem.p2Title"),
      desc: t("landing.problem.p2Desc"),
      icon: Clock,
      color: "text-amber-700 bg-amber-50 border-amber-200",
    },
    {
      title: t("landing.problem.p3Title"),
      desc: t("landing.problem.p3Desc"),
      icon: FileWarning,
      color: "text-rose-700 bg-rose-50 border-rose-200",
    },
    {
      title: t("landing.problem.p4Title"),
      desc: t("landing.problem.p4Desc"),
      icon: HelpCircle,
      color: "text-purple-700 bg-purple-50 border-purple-200",
    },
  ];

  const agentSteps = [
    {
      step: "01",
      title: t("landing.howItWorks.step1Title"),
      desc: t("landing.howItWorks.step1Desc"),
      icon: Sparkles,
    },
    {
      step: "02",
      title: t("landing.howItWorks.step2Title"),
      desc: t("landing.howItWorks.step2Desc"),
      icon: Layers,
    },
    {
      step: "03",
      title: t("landing.howItWorks.step3Title"),
      desc: t("landing.howItWorks.step3Desc"),
      icon: Wrench,
    },
    {
      step: "04",
      title: t("landing.howItWorks.step4Title"),
      desc: t("landing.howItWorks.step4Desc"),
      icon: Database,
    },
    {
      step: "05",
      title: t("landing.howItWorks.step5Title"),
      desc: t("landing.howItWorks.step5Desc"),
      icon: CheckCircle2,
    },
  ];

  const trustPrinciples = [
    {
      title: t("landing.trust.t1Title"),
      desc: t("landing.trust.t1Desc"),
      icon: CheckCircle2,
    },
    {
      title: t("landing.trust.t2Title"),
      desc: t("landing.trust.t2Desc"),
      icon: HelpCircle,
    },
    {
      title: t("landing.trust.t3Title"),
      desc: t("landing.trust.t3Desc"),
      icon: Lock,
    },
    {
      title: t("landing.trust.t4Title"),
      desc: t("landing.trust.t4Desc"),
      icon: UserCheck,
    },
  ];

  return (
    <div className="space-y-20 sm:space-y-28 py-10 sm:py-16">
      {/* SECTION 1: HERO */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
          {/* Left Column: Heading, Subtitle & CTAs */}
          <div className="lg:col-span-7 space-y-6 text-left">
            <div className="inline-flex items-center gap-2">
              <Badge variant="primary" size="md">
                <Sparkles className="w-3.5 h-3.5 text-blue-700" />
                <span>{t("landing.hero.badge")}</span>
              </Badge>
            </div>

            <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-slate-900 leading-[1.15]">
              {t("landing.hero.title")}{" "}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-700 via-blue-800 to-teal-700">
                {t("landing.hero.titleHighlight")}
              </span>
            </h1>

            <p className="text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl">
              {t("landing.hero.subheading")}
            </p>

            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
              <Link to="/dashboard">
                <Button variant="primary" size="lg" className="w-full sm:w-auto" icon={ArrowRight} iconPosition="right">
                  {t("landing.hero.getStarted")}
                </Button>
              </Link>
              <Link to="/assistant">
                <Button variant="outline" size="lg" className="w-full sm:w-auto" icon={Bot}>
                  {t("landing.hero.tryAssistant")}
                </Button>
              </Link>
            </div>
          </div>

          {/* Right Column: Stylized Inline SVG Civic Art */}
          <div className="lg:col-span-5 flex justify-center">
            <div className="relative w-full max-w-md p-6 bg-gradient-to-br from-blue-50/80 via-white to-teal-50/40 rounded-3xl border border-slate-200/80 shadow-md">
              <svg
                viewBox="0 0 360 280"
                className="w-full h-auto drop-shadow-xs"
                role="img"
                aria-label={t("landing.hero.visualAria")}
              >
                {/* Background Card */}
                <rect x="20" y="20" width="320" height="240" rx="16" fill="#ffffff" stroke="#e2e8f0" strokeWidth="2" />
                
                {/* Document Top Bar */}
                <rect x="20" y="20" width="320" height="40" rx="16" fill="#f8fafc" />
                <circle cx="45" cy="40" r="5" fill="#cbd5e1" />
                <circle cx="62" cy="40" r="5" fill="#cbd5e1" />
                <circle cx="79" cy="40" r="5" fill="#cbd5e1" />
                <rect x="110" y="34" width="120" height="12" rx="4" fill="#e2e8f0" />
                
                {/* Official Gazette Header */}
                <rect x="45" y="80" width="160" height="14" rx="4" fill="#1e3a8a" />
                <rect x="45" y="102" width="220" height="8" rx="3" fill="#cbd5e1" />
                <rect x="45" y="116" width="190" height="8" rx="3" fill="#e2e8f0" />
                <rect x="45" y="130" width="210" height="8" rx="3" fill="#e2e8f0" />

                {/* Evidence Citation Tag */}
                <rect x="45" y="152" width="130" height="22" rx="6" fill="#f0fdf4" stroke="#86efac" strokeWidth="1.5" />
                <circle cx="58" cy="163" r="4" fill="#16a34a" />
                <rect x="68" y="159" width="90" height="8" rx="3" fill="#15803d" />

                {/* Magnifying Glass with Teal Accent */}
                <g transform="translate(190, 110)">
                  <circle cx="55" cy="55" r="42" fill="#ffffff" stroke="#0d9488" strokeWidth="6" />
                  <circle cx="55" cy="55" r="32" fill="#f0fdfa" opacity="0.8" />
                  {/* Checkmark inside Lens */}
                  <path d="M43 55 L52 64 L68 47" fill="none" stroke="#0d9488" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
                  {/* Lens Handle */}
                  <line x1="85" y1="85" x2="115" y2="115" stroke="#0f766e" strokeWidth="8" strokeLinecap="round" />
                </g>

                {/* Verification Badge */}
                <g transform="translate(240, 48)">
                  <rect width="84" height="26" rx="8" fill="#1e3a8a" />
                  <text x="42" y="17" fill="#ffffff" fontSize="10" fontWeight="bold" textAnchor="middle" fontFamily="sans-serif">
                    VERIFIED
                  </text>
                </g>
              </svg>
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 2: THE PROBLEM */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <Badge variant="outline" size="sm" className="mb-2">
            {t("landing.problem.tag")}
          </Badge>
          <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-slate-900 mb-3">
            {t("landing.problem.title")}
          </h2>
          <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
            {t("landing.problem.description")}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {problemPoints.map((point) => {
            const Icon = point.icon;
            return (
              <Card key={point.title} className="p-6 h-full flex flex-col justify-between">
                <div>
                  <div className={`w-11 h-11 rounded-xl flex items-center justify-center mb-4 border ${point.color}`}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 mb-2">
                    {point.title}
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                    {point.desc}
                  </p>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* SECTION 3: FIVE CORE CAPABILITIES */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <Badge variant="primary" size="sm" className="mb-2">
            {t("landing.capabilities.tag")}
          </Badge>
          <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-slate-900 mb-3">
            {t("landing.capabilities.title")}
          </h2>
          <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
            {t("landing.capabilities.description")}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {capabilities.map((cap) => {
            const Icon = cap.icon;
            return (
              <Card key={cap.to} className="flex flex-col justify-between hover:border-blue-300 transition-all">
                <CardHeader>
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center">
                      <Icon className="w-5 h-5" />
                    </div>
                    <Badge variant={cap.badgeColor} size="sm">
                      {cap.badgeColor === "success" ? "Verification" : "Active Tool"}
                    </Badge>
                  </div>
                  <CardTitle>{cap.title}</CardTitle>
                  <CardDescription>{cap.desc}</CardDescription>
                </CardHeader>
                <CardFooter>
                  <Link to={cap.to} className="w-full">
                    <Button variant="outline" size="sm" className="w-full" icon={ArrowRight} iconPosition="right">
                      {t("landing.capabilities.openModule")}
                    </Button>
                  </Link>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      </section>

      {/* SECTION 4: HOW IT WORKS (THE CENTRAL AGENT) */}
      <section className="bg-slate-100/70 border-y border-slate-200 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <Badge variant="outline" size="sm" className="mb-2">
              {t("landing.howItWorks.tag")}
            </Badge>
            <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-slate-900 mb-3">
              {t("landing.howItWorks.title")}
            </h2>
            <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
              {t("landing.howItWorks.description")}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {agentSteps.map((s) => {
              const Icon = s.icon;
              return (
                <div
                  key={s.step}
                  className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-2xs flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold text-blue-700 tracking-wider">
                        {s.step}
                      </span>
                      <Icon className="w-4 h-4 text-slate-400" />
                    </div>
                    <h3 className="text-sm font-semibold text-slate-900 mb-1.5 leading-snug">
                      {s.title}
                    </h3>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      {s.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* SECTION 5: EVIDENCE, TRUST & INTEGRITY */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-12">
          <Badge variant="primary" size="sm" className="mb-2">
            {t("landing.trust.tag")}
          </Badge>
          <h2 className="text-2xl sm:text-4xl font-bold tracking-tight text-slate-900 mb-3">
            {t("landing.trust.title")}
          </h2>
          <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
            {t("landing.trust.description")}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {trustPrinciples.map((tp) => {
            const Icon = tp.icon;
            return (
              <Card key={tp.title} className="p-5">
                <div className="w-9 h-9 rounded-lg bg-teal-50 text-teal-700 flex items-center justify-center mb-3">
                  <Icon className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-semibold text-slate-900 mb-1.5">
                  {tp.title}
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  {tp.desc}
                </p>
              </Card>
            );
          })}
        </div>

        {/* Prototype safety disclaimer banner */}
        <div className="p-4 rounded-xl bg-amber-50/80 border border-amber-200/90 flex items-start gap-3 max-w-4xl mx-auto">
          <AlertTriangle className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
          <p className="text-xs sm:text-sm text-amber-900 leading-relaxed">
            {t("landing.trust.demoDisclaimer")}
          </p>
        </div>
      </section>

      {/* SECTION 6: BILINGUAL LANGUAGE SUPPORT */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-gradient-to-br from-blue-900 via-blue-950 to-slate-900 text-white rounded-3xl p-8 sm:p-12 shadow-xl">
          <div className="max-w-3xl mx-auto text-center mb-10">
            <div className="inline-flex items-center gap-2 mb-3">
              <span className="px-3 py-1 rounded-full bg-blue-800/80 text-blue-200 text-xs font-semibold border border-blue-700">
                <Languages className="w-3.5 h-3.5 inline mr-1" />
                {t("landing.language.tag")}
              </span>
            </div>
            <h2 className="text-2xl sm:text-4xl font-bold tracking-tight mb-3">
              {t("landing.language.title")}
            </h2>
            <p className="text-sm sm:text-base text-blue-200 leading-relaxed">
              {t("landing.language.description")}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
            {/* English Sample */}
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/15">
              <span className="text-xs uppercase font-bold text-blue-300 tracking-wider block mb-2">
                {t("landing.language.sampleEnTitle")}
              </span>
              <p className="text-sm sm:text-base text-white font-medium italic leading-relaxed">
                {t("landing.language.sampleEnQuote")}
              </p>
            </div>

            {/* Tamil Sample */}
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/15" lang="ta">
              <span className="text-xs uppercase font-bold text-teal-300 tracking-wider block mb-2 font-tamil">
                {t("landing.language.sampleTaTitle")}
              </span>
              <p className="text-sm sm:text-base text-white font-medium italic leading-relaxed font-tamil">
                {t("landing.language.sampleTaQuote")}
              </p>
            </div>
          </div>

          <div className="text-center mt-8 text-xs text-blue-300">
            {t("landing.language.bilingualNote")}
          </div>
        </div>
      </section>

      {/* SECTION 7: FINAL CALL TO ACTION */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center pb-8">
        <div className="bg-white border border-slate-200 rounded-3xl p-8 sm:p-14 shadow-xs max-w-4xl mx-auto">
          <h2 className="text-2xl sm:text-4xl font-extrabold text-slate-900 mb-3">
            {t("landing.cta.title")}
          </h2>
          <p className="text-sm sm:text-base text-slate-600 mb-8 max-w-xl mx-auto leading-relaxed">
            {t("landing.cta.description")}
          </p>
          <Link to="/dashboard">
            <Button variant="primary" size="lg" icon={ArrowRight} iconPosition="right">
              {t("landing.cta.button")}
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
