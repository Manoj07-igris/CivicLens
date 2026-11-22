import React from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { useLanguage } from "../hooks/useLanguage";

export function Terms() {
  const { t } = useLanguage();

  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-950 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <Logo size="md" to="/" />
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <Link
              to="/login"
              className="text-sm font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400"
            >
              {t("auth.signInButton") || "Sign In"}
            </Link>
          </div>
        </div>

        <Card className="p-8 sm:p-10 shadow-sm space-y-6">
          <div className="border-b border-surface-200 dark:border-surface-800 pb-4">
            <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
              {t("terms.title") || "Terms of Service"}
            </h1>
            <p className="text-sm text-surface-500 mt-1">
              {t("terms.version") || "Version 1.0 (Hackathon Release) • Effective November 2026"}
            </p>
          </div>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              1. Prototype & Civic Intelligence Scope
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              CivicLens is an agentic AI civic intelligence assistant engineered to help citizens
              understand public policies, verify government orders, prepare verified grievance
              drafts, and navigate public services. It is provided for personal civic literacy and
              informational demonstration purposes.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              2. Independent Civic Tool — Not a Government Agency
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              CivicLens is an independent open-source intelligence platform. It is not affiliated
              with, endorsed by, or operated by any government department or ministry. All civic
              summaries and guidance must be independently verified with primary gazettes and
              official government portals before initiating legal or financial proceedings.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              3. Local Execution and Safe Automation Boundaries
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              CivicLens operates entirely on your local machine using SQLite storage and local FAISS
              embeddings. All automated form demonstration workflows operate strictly inside a
              sandboxed demo portal shipped with CivicLens and running on loopback (`localhost`).
              CivicLens never opens, automates, submits forms to, or navigates real government or
              third-party websites.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              4. Citizen Ownership & Data Deletion
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              You own all documents, chat conversations, grievance drafts, and comparison reports
              associated with your account. You have the absolute right to export your data or
              permanently erase your account and all associated records at any time from your
              account settings.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              5. Account Security Responsibilities
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              You are responsible for maintaining the confidentiality of your account credentials.
              CivicLens hashes all passwords using memory-hard Argon2id and delivers session tokens
              via encrypted HttpOnly cookies to protect your civic activity from local browser
              script theft.
            </p>
          </section>

          <div className="pt-6 border-t border-surface-200 dark:border-surface-800 flex justify-between items-center text-xs text-surface-500">
            <Link to="/privacy" className="text-primary-600 hover:underline">
              {t("auth.privacyPolicy") || "View Privacy Policy"}
            </Link>
            <Link to="/login" className="text-primary-600 hover:underline">
              {t("auth.returnToLogin") || "Back to Sign In"}
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default Terms;
