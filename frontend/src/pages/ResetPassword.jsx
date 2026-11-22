import React, { useState, useEffect, useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import authService from "../services/authService";
import { useLanguage } from "../hooks/useLanguage";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { resolveAuthError } from "../utils/authErrors";

export function ResetPassword() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);

  // Extract reset token from fragment #token=... or fallback ?token=...
  useEffect(() => {
    let extracted = "";
    if (window.location.hash) {
      const hash = window.location.hash.substring(1);
      const params = new URLSearchParams(hash);
      extracted = params.get("token") || "";
    }

    if (!extracted) {
      extracted = searchParams.get("token") || "";
    }

    if (extracted) {
      setToken(extracted);
      // Strip token immediately from browser history and address bar
      const cleanUrl = window.location.pathname;
      window.history.replaceState(null, "", cleanUrl);
    } else {
      setError(
        t("auth.missingTokenError") ||
          "Password reset token is missing or invalid. Please request a new link."
      );
    }
  }, [searchParams, t]);

  // Live password validation checks matching server policy:
  // 12-128 chars, not repetitive/sequential, not common, matching
  const checks = useMemo(() => {
    const lenValid = newPassword.length >= 12 && newPassword.length <= 128;

    const normalized = newPassword.toLowerCase();
    // Repetition check: 4+ identical chars or any 2-4 char chunk repeated 3+ times
    const hasRepeatedChunk = /(.)\1{3,}/.test(normalized) || /(.{2,4})\1{2,}/.test(normalized);
    const sequences = [
      "012345", "123456", "234567", "345678", "456789", "567890",
      "abcdef", "bcdefg", "cdefgh", "defghi", "efghij", "fghijk",
      "ghijkl", "hijklm", "ijklmn", "jklmno", "klmnop", "lmnopq",
      "mnopqr", "nopqrs", "opqrst", "pqrstu", "qrstuv", "rstuvw",
      "stuvwx", "tuvwxy", "uvwxyz"
    ];
    const hasSequence = sequences.some((seq) => normalized.includes(seq));
    const notRepetitive = !hasRepeatedChunk && !hasSequence;

    const commonPasswords = [
      "password12345", "admin12345678", "qwertyuiopas", "123456789012",
      "welcome12345", "administrator", "iloveyou12345", "changeme12345"
    ];
    const notCommon = !commonPasswords.includes(normalized);

    const matches = newPassword.length > 0 && newPassword === confirmPassword;

    return {
      length: lenValid,
      notRepetitive,
      notCommon,
      match: matches,
      allValid: lenValid && notRepetitive && notCommon && matches,
    };
  }, [newPassword, confirmPassword]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading || !token) return;

    if (!checks.allValid) {
      setError(
        t("auth.passwordPolicyError") ||
          "Please ensure password satisfies all security requirements and matches."
      );
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await authService.resetPassword(token, newPassword);
      setSuccess(true);
    } catch (err) {
      const resolved = resolveAuthError(err, t);
      setError(resolved.topLevel);
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
          {t("auth.setNewPasswordTitle") || "Set New Password"}
        </h2>
        <p className="mt-2 text-center text-sm text-surface-600 dark:text-surface-400">
          {t("auth.setNewPasswordSubtitle") ||
            "Choose a strong, unique password to secure your account"}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card className="p-6 sm:p-8 shadow-md">
          {error && (
            <div className="mb-6">
              <Alert variant="error">{error}</Alert>
            </div>
          )}

          {success ? (
            <div className="space-y-4 text-center">
              <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-success-100 dark:bg-success-900/30 text-success-600">
                <svg
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth="2"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>

              <h3 className="text-lg font-medium text-surface-900 dark:text-surface-100">
                {t("auth.passwordResetSuccessTitle") || "Password Successfully Updated"}
              </h3>

              <p className="text-sm text-surface-600 dark:text-surface-400">
                {t("auth.passwordResetSuccessMessage") ||
                  "Your password has been changed. You can now sign in using your new credentials."}
              </p>

              <div className="pt-4">
                <Button
                  variant="primary"
                  onClick={() => navigate("/login")}
                  className="w-full justify-center"
                >
                  {t("auth.signInButton") || "Sign In Now"}
                </Button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label
                  htmlFor="newPassword"
                  className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
                >
                  {t("auth.newPasswordLabel") || "New Password"}
                </label>
                <Input
                  id="newPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="••••••••••••"
                  disabled={loading || !token}
                  className="w-full"
                />
              </div>

              <div>
                <label
                  htmlFor="confirmResetPassword"
                  className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
                >
                  {t("auth.confirmPasswordLabel") || "Confirm New Password"}
                </label>
                <Input
                  id="confirmResetPassword"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••••••"
                  disabled={loading || !token}
                  className="w-full"
                />
              </div>

              {/* Password Requirements */}
              <div className="p-3 bg-surface-100 dark:bg-surface-800/60 rounded-md border border-surface-200 dark:border-surface-700/60 text-xs space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className={checks.length ? "text-success-600 font-bold" : "text-surface-400"}>
                    {checks.length ? "✓" : "○"}
                  </span>
                  <span className={checks.length ? "text-surface-800 dark:text-surface-200" : "text-surface-500"}>
                    {t("auth.checkMinLength") || "12 to 128 characters"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={checks.notRepetitive ? "text-success-600 font-bold" : "text-surface-400"}>
                    {checks.notRepetitive ? "✓" : "○"}
                  </span>
                  <span className={checks.notRepetitive ? "text-surface-800 dark:text-surface-200" : "text-surface-500"}>
                    {t("auth.checkNotRepetitive") || "Not repetitive or a simple sequence"}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={checks.match ? "text-success-600 font-bold" : "text-surface-400"}>
                    {checks.match ? "✓" : "○"}
                  </span>
                  <span className={checks.match ? "text-surface-800 dark:text-surface-200" : "text-surface-500"}>
                    {t("auth.checkMatch") || "Passwords match"}
                  </span>
                </div>
                <div className="pt-1 text-[11px] text-surface-500 dark:text-surface-400 italic">
                  {t("auth.spacesAndUnicodeAllowed") || "Spaces and all languages/scripts supported"}
                </div>
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  loading={loading}
                  disabled={loading || !token || !checks.allValid}
                  className="w-full justify-center py-2.5"
                >
                  {loading
                    ? (t("auth.saving") || "Saving...")
                    : (t("auth.resetPasswordButton") || "Reset Password")}
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

export default ResetPassword;
