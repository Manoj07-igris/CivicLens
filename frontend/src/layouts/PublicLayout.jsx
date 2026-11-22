import React, { useState } from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { Menu, X, ArrowRight } from "lucide-react";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { BackendStatus } from "../components/ui/BackendStatus";
import { Button } from "../components/ui/Button";
import { useLanguage } from "../hooks/useLanguage";
import { useBackendStatus } from "../hooks/useBackendStatus";

export function PublicLayout() {
  const { t } = useLanguage();
  const { status, info, retry } = useBackendStatus();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    { to: "/", label: t("nav.home") },
    { to: "/dashboard", label: t("nav.dashboard") },
    { to: "/assistant", label: t("nav.assistant") },
    { to: "/documents", label: t("nav.documents") },
    { to: "/verify", label: t("nav.verify") },
  ];

  const moduleLinks = [
    { to: "/documents", label: t("pages.documents.title") },
    { to: "/compare", label: t("pages.compare.title") },
    { to: "/verify", label: t("pages.verify.title") },
    { to: "/services", label: t("pages.services.title") },
    { to: "/grievance", label: t("pages.grievance.title") },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-900 overflow-x-hidden">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-8">
            <Logo showTagline={false} size="md" to="/" />
            <nav className="hidden md:flex items-center gap-6" aria-label="Main Navigation">
              {navLinks.map((link) => {
                const isActive = location.pathname === link.to;
                return (
                  <Link
                    key={link.to}
                    to={link.to}
                    className={`text-sm font-medium transition-colors hover:text-blue-700 focus-visible:ring-2 focus-visible:ring-blue-600 rounded-md px-1.5 py-1 ${
                      isActive ? "text-blue-700 font-semibold" : "text-slate-600"
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="hidden md:flex items-center gap-4">
            <BackendStatus
              status={status}
              version={info?.version}
              onRetry={retry}
              showRetry={true}
            />
            <LanguageSwitcher />
            <Link
              to="/login"
              className="text-sm font-semibold text-slate-700 hover:text-blue-700 transition-colors px-2"
            >
              {t("auth.signInButton") || "Sign In"}
            </Link>
            <Link to="/signup">
              <Button variant="primary" size="sm" icon={ArrowRight} iconPosition="right">
                {t("nav.getStarted")}
              </Button>
            </Link>
          </div>

          {/* Mobile menu trigger */}
          <div className="flex items-center gap-2 md:hidden">
            <BackendStatus
              status={status}
              version={info?.version}
              onRetry={retry}
            />
            <LanguageSwitcher variant="compact" />
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-blue-600"
              aria-label={mobileMenuOpen ? t("nav.closeMenu") : t("nav.openMenu")}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden border-b border-slate-200 bg-white px-4 pt-2 pb-5 shadow-lg">
            <nav className="flex flex-col gap-2">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className="px-3 py-2 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-100 hover:text-blue-700"
                >
                  {link.label}
                </Link>
              ))}
              <div className="pt-3 border-t border-slate-100 flex flex-col gap-3">
                <Link to="/dashboard" onClick={() => setMobileMenuOpen(false)}>
                  <Button variant="primary" className="w-full" icon={ArrowRight} iconPosition="right">
                    {t("nav.getStarted")}
                  </Button>
                </Link>
              </div>
            </nav>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="flex-1">
        <Outlet />
      </main>

      {/* Footer with Working Navigation Links */}
      <footer className="bg-white border-t border-slate-200 mt-auto py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 pb-8 border-b border-slate-100">
            {/* Column 1: Brand & Disclaimer */}
            <div className="md:col-span-2 space-y-3">
              <Logo size="md" to="/" showTagline={true} />
              <p className="text-sm text-slate-600 max-w-sm leading-relaxed">
                {t("footer.tagline")}
              </p>
              <p className="text-xs text-slate-400 max-w-md leading-relaxed">
                {t("footer.disclaimer")}
              </p>
            </div>

            {/* Column 2: Navigation Links */}
            <div>
              <h4 className="text-xs font-semibold text-slate-900 tracking-wider uppercase mb-3">
                {t("footer.navigation")}
              </h4>
              <ul className="space-y-2 text-sm text-slate-600">
                <li>
                  <Link to="/" className="hover:text-blue-700 transition-colors">
                    {t("nav.home")}
                  </Link>
                </li>
                <li>
                  <Link to="/dashboard" className="hover:text-blue-700 transition-colors">
                    {t("nav.dashboard")}
                  </Link>
                </li>
                <li>
                  <Link to="/assistant" className="hover:text-blue-700 transition-colors">
                    {t("nav.assistant")}
                  </Link>
                </li>
                <li>
                  <Link to="/design-system" className="hover:text-blue-700 transition-colors">
                    {t("nav.designSystem")}
                  </Link>
                </li>
                <li>
                  <Link to="/terms" className="hover:text-blue-700 transition-colors">
                    {t("auth.termsOfService") || "Terms of Service"}
                  </Link>
                </li>
                <li>
                  <Link to="/privacy" className="hover:text-blue-700 transition-colors">
                    {t("auth.privacyPolicy") || "Privacy Policy"}
                  </Link>
                </li>
              </ul>
            </div>

            {/* Column 3: Intelligence Modules */}
            <div>
              <h4 className="text-xs font-semibold text-slate-900 tracking-wider uppercase mb-3">
                {t("footer.modules")}
              </h4>
              <ul className="space-y-2 text-sm text-slate-600">
                {moduleLinks.map((mod) => (
                  <li key={mod.to}>
                    <Link to={mod.to} className="hover:text-blue-700 transition-colors truncate block">
                      {mod.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="pt-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-400">
            <span>{t("footer.rights")}</span>
            <span className="font-semibold text-slate-600">CivicLens • Understand. Verify. Act.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
