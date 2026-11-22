import React from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/ui/Card";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { useLanguage } from "../hooks/useLanguage";

export function Privacy() {
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
              {t("privacy.title") || "Privacy Policy & Data Ethics"}
            </h1>
            <p className="text-sm text-surface-500 mt-1">
              {t("privacy.version") || "Zero Cloud Telemetry • Local First • Effective November 2026"}
            </p>
          </div>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              1. Local-First Data Sovereignty
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              All documents you upload, chats you conduct, and grievances you draft are stored
              strictly on your local device in an encrypted/isolated SQLite database (`civiclens.db`)
              and local filesystem. CivicLens does not run external telemetry, usage tracking, or
              third-party analytics scripts.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              2. Universal PII Guardrail
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              To defend citizen privacy, CivicLens enforces an automated PII detector across all
              endpoints. Any input containing sensitive Indian personal identifiers (including
              12-digit Aadhaar numbers, 10-character PAN identifiers, Indian mobile phone numbers,
              or credit card sequences) is immediately blocked with HTTP 422 before reaching LLMs or
              persisting to disk.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              3. AI Processing via Gemini
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              Synthesized answers and grounded reasoning are processed through Google Gemini using
              your configured backend API key. Only relevant document passages and anonymized
              queries are transmitted to the API endpoint over TLS. Passwords, session tokens, and
              private keys are never sent to external LLMs.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              4. Cookies and Session Architecture
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              CivicLens uses a single session cookie (`civiclens_session`) marked `HttpOnly`,
              `SameSite=Lax`, and `Path=/api`. It is cryptographically opaque and stores only a
              SHA-256 hash reference on the backend. No authentication tokens are stored in browser
              `localStorage` or `sessionStorage`.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-lg font-semibold text-surface-800 dark:text-surface-200">
              5. Irreversible Deletion
            </h2>
            <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed">
              When you delete your account, your user record, all active sessions, stored
              documents, OCR text chunks, FAISS vector indexes, grievances, and chat histories are
              permanently purged using SQLite cascading deletes and filesystem cleanup.
            </p>
          </section>

          <div className="pt-6 border-t border-surface-200 dark:border-surface-800 flex justify-between items-center text-xs text-surface-500">
            <Link to="/terms" className="text-primary-600 hover:underline">
              {t("auth.termsOfService") || "View Terms of Service"}
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

export default Privacy;
