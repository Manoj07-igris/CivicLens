import React, { useState } from "react";
import { Link } from "react-router-dom";
import authService from "../services/authService";
import { useLanguage } from "../hooks/useLanguage";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { resolveAuthError } from "../utils/authErrors";

export function ForgotPassword() {
  const { t } = useLanguage();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;

    setError(null);
    setLoading(true);

    try {
      await authService.forgotPassword(email.trim());
      setSubmitted(true);
    } catch (err) {
      if (err.status === 429) {
        const resolved = resolveAuthError(err, t);
        setError(resolved.topLevel);
      } else {
        // We still display success or standard message to avoid leaking user presence
        setSubmitted(true);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-50 dark:bg-surface-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md flex flex-col items-center">
        <div className="flex items-center justify-between w-full px-4 mb-4 sm:mb-6">
          <Logo size="lg" to="/" />
          <LanguageSwitcher />
        </div>

        <h2 className="text-center text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
          {t("auth.forgotPasswordTitle") || "Reset Your Password"}
        </h2>
        <p className="mt-2 text-center text-sm text-surface-600 dark:text-surface-400">
          {t("auth.forgotPasswordSubtitle") ||
            "Enter your email to receive recovery instructions"}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card className="p-6 sm:p-8 shadow-md">
          {error && (
            <div className="mb-6">
              <Alert variant="error">{error}</Alert>
            </div>
          )}

          {submitted ? (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-success-100 dark:bg-success-900/30 text-success-600">
                <svg
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth="2"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              </div>

              <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">
                {t("auth.resetDispatchedTitle") || "Instructions Dispatched"}
              </h3>

              <p className="text-sm text-surface-600 dark:text-surface-400">
                {t("auth.resetDispatchedMessage") ||
                  "If an account exists with that email address, password reset instructions have been sent. In local development mode without SMTP, the reset link is output directly in the backend terminal console."}
              </p>

              <div className="pt-4">
                <Link to="/login">
                  <Button variant="secondary" className="w-full justify-center">
                    {t("auth.returnToLogin") || "Return to Sign In"}
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label
                  htmlFor="forgotEmail"
                  className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
                >
                  {t("auth.emailLabel") || "Email address"}
                </label>
                <Input
                  id="forgotEmail"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="citizen@example.com"
                  disabled={loading}
                  className="w-full"
                />
              </div>

              <div>
                <Button
                  type="submit"
                  variant="primary"
                  loading={loading}
                  disabled={loading || !email.trim()}
                  className="w-full justify-center py-2.5"
                >
                  {loading
                    ? (t("auth.sending") || "Sending...")
                    : (t("auth.sendResetInstructions") || "Send Reset Link")}
                </Button>
              </div>

              <div className="text-center pt-2">
                <Link
                  to="/login"
                  className="text-sm font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400"
                >
                  {t("auth.backToLogin") || "Back to Sign In"}
                </Link>
              </div>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}

export default ForgotPassword;
