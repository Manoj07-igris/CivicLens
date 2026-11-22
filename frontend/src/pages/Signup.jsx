import React, { useState, useMemo, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import { useLanguage } from "../hooks/useLanguage";
import { useToast } from "../hooks/useToast";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Alert } from "../components/ui/Alert";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { resolveAuthError } from "../utils/authErrors";

export function Signup() {
  const { register, capabilities } = useAuth();
  const { t, language, setLanguage } = useLanguage();
  const { addToast } = useToast();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [preferredLang, setPreferredLang] = useState(language || "en");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});

  const fullNameRef = useRef(null);
  const emailRef = useRef(null);
  const passwordRef = useRef(null);
  const confirmPasswordRef = useRef(null);
  const termsRef = useRef(null);

  const registrationDisabled = capabilities?.registration_enabled === false;

  // Authoritative password validation checks matching server policy:
  // 12-128 chars, not repetitive/sequential, not personal, not common, matching
  const checks = useMemo(() => {
    const lenValid = password.length >= 12 && password.length <= 128;

    const normalized = password.toLowerCase();
    // Repetition check: 4+ identical chars or any 2-4 char chunk repeated 3+ times
    const hasRepeatedChunk = /(.)\1{3,}/.test(normalized) || /(.{2,4})\1{2,}/.test(normalized);
    // Sequence check: 6+ ascending chars or digits
    const sequences = [
      "012345", "123456", "234567", "345678", "456789", "567890",
      "abcdef", "bcdefg", "cdefgh", "defghi", "efghij", "fghijk",
      "ghijkl", "hijklm", "ijklmn", "jklmno", "klmnop", "lmnopq",
      "mnopqr", "nopqrs", "opqrst", "pqrstu", "qrstuv", "rstuvw",
      "stuvwx", "tuvwxy", "uvwxyz"
    ];
    const hasSequence = sequences.some((seq) => normalized.includes(seq));
    const notRepetitive = !hasRepeatedChunk && !hasSequence;

    // Common passwords list check
    const commonPasswords = [
      "password12345", "admin12345678", "qwertyuiopas", "123456789012",
      "welcome12345", "administrator", "iloveyou12345", "changeme12345"
    ];
    const notCommon = !commonPasswords.includes(normalized);

    // Personal info check (name tokens or email local-part token >= 4 chars)
    const nameTokens = fullName
      .toLowerCase()
      .split(/[\s,._-]+/)
      .filter((w) => w.length >= 4);
    const emailToken = (email.split("@")[0] || "").toLowerCase();
    const hasPersonalToken =
      (emailToken.length >= 4 && normalized.includes(emailToken)) ||
      nameTokens.some((tok) => normalized.includes(tok));
    const notPersonal = !hasPersonalToken;

    const matches = password.length > 0 && password === confirmPassword;

    return {
      length: lenValid,
      notRepetitive,
      notPersonal,
      notCommon,
      match: matches,
      allValid: lenValid && notRepetitive && notPersonal && notCommon && matches,
    };
  }, [password, confirmPassword, fullName, email]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading || registrationDisabled) return;

    setError(null);
    setFieldErrors({});

    // Client-side validations
    if (!termsAccepted) {
      const msg =
        t("auth.errors.terms_not_accepted") ||
        t("auth.termsRequiredError") ||
        "You must review and accept the Terms of Service to create an account.";
      setError(msg);
      setFieldErrors({ terms: msg });
      termsRef.current?.focus();
      return;
    }

    if (!checks.length) {
      const msg =
        t("auth.errors.password_too_short") ||
        "Password must be at least 12 characters long.";
      setError(msg);
      setFieldErrors({ password: msg });
      passwordRef.current?.focus();
      return;
    }

    if (!checks.notPersonal) {
      const msg =
        t("auth.errors.password_contains_personal_info") ||
        "Password must not contain parts of your name or email address.";
      setError(msg);
      setFieldErrors({ password: msg });
      passwordRef.current?.focus();
      return;
    }

    if (!checks.notRepetitive) {
      const msg =
        t("auth.errors.password_repetitive") ||
        "Password contains repetitive repeating sequences or simple patterns.";
      setError(msg);
      setFieldErrors({ password: msg });
      passwordRef.current?.focus();
      return;
    }

    if (!checks.match) {
      const msg =
        t("auth.errors.password_mismatch") ||
        "Passwords do not match.";
      setError(msg);
      setFieldErrors({ confirmPassword: msg });
      confirmPasswordRef.current?.focus();
      return;
    }

    if (!checks.allValid) {
      setError(
        t("auth.passwordPolicyError") ||
          "Please satisfy all password security requirements before submitting."
      );
      return;
    }

    setLoading(true);

    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim(),
        password,
        accept_terms: termsAccepted,
        terms_accepted: termsAccepted,
        preferred_language: preferredLang,
      });

      // Update active UI language if user picked Tamil
      if (preferredLang !== language) {
        setLanguage(preferredLang);
      }

      addToast({
        type: "success",
        title: t("auth.accountCreated") || "Account Created!",
        message:
          t("auth.accountCreatedMessage") ||
          "Your citizen account has been established with secure session credentials.",
      });

      navigate("/dashboard", { replace: true });
    } catch (err) {
      console.error("[CivicLens Signup Error]", err);
      const resolved = resolveAuthError(err, t);
      setError(resolved.topLevel);
      setFieldErrors(resolved.fieldErrors || {});

      // Keep full name and email; clear passwords for security and retry
      setPassword("");
      setConfirmPassword("");

      // Focus the first invalid field for accessibility
      if (resolved.fieldErrors?.fullName) {
        fullNameRef.current?.focus();
      } else if (resolved.fieldErrors?.email) {
        emailRef.current?.focus();
      } else if (resolved.fieldErrors?.password) {
        passwordRef.current?.focus();
      } else if (resolved.fieldErrors?.confirmPassword) {
        confirmPasswordRef.current?.focus();
      } else if (resolved.fieldErrors?.terms) {
        termsRef.current?.focus();
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
          {t("auth.createAccountTitle") || "Create your CivicLens Account"}
        </h2>
        <p className="mt-2 text-center text-sm text-surface-600 dark:text-surface-400">
          {t("auth.createAccountSubtitle") ||
            "Private, isolated civic intelligence with local data ownership"}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card className="p-6 sm:p-8 shadow-md">
          {registrationDisabled && (
            <div className="mb-6">
              <Alert variant="warning">
                {t("auth.errors.registration_disabled") ||
                  "New account registration is currently disabled by system policy."}
              </Alert>
            </div>
          )}

          {error && (
            <div className="mb-6">
              <Alert variant="error">{error}</Alert>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="fullName"
                className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
              >
                {t("auth.fullNameLabel") || "Full Name"}
              </label>
              <Input
                ref={fullNameRef}
                id="fullName"
                type="text"
                autoComplete="name"
                required
                value={fullName}
                onChange={(e) => {
                  setFullName(e.target.value);
                  if (fieldErrors.fullName) {
                    setFieldErrors((prev) => ({ ...prev, fullName: undefined }));
                  }
                }}
                placeholder="Aarav Patel"
                disabled={loading || registrationDisabled}
                error={fieldErrors.fullName}
                className="w-full"
              />
            </div>

            <div>
              <label
                htmlFor="signupEmail"
                className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
              >
                {t("auth.emailLabel") || "Email address"}
              </label>
              <Input
                ref={emailRef}
                id="signupEmail"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (fieldErrors.email) {
                    setFieldErrors((prev) => ({ ...prev, email: undefined }));
                  }
                }}
                placeholder="citizen@example.com"
                disabled={loading || registrationDisabled}
                error={fieldErrors.email}
                className="w-full"
              />
            </div>

            <div>
              <label
                htmlFor="signupPassword"
                className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
              >
                {t("auth.passwordLabel") || "Password"}
              </label>
              <Input
                ref={passwordRef}
                id="signupPassword"
                type="password"
                autoComplete="new-password"
                required
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (fieldErrors.password) {
                    setFieldErrors((prev) => ({ ...prev, password: undefined }));
                  }
                }}
                placeholder="••••••••••••"
                disabled={loading || registrationDisabled}
                error={fieldErrors.password}
                className="w-full"
              />
            </div>

            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
              >
                {t("auth.confirmPasswordLabel") || "Confirm Password"}
              </label>
              <Input
                ref={confirmPasswordRef}
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  if (fieldErrors.confirmPassword) {
                    setFieldErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                  }
                }}
                placeholder="••••••••••••"
                disabled={loading || registrationDisabled}
                error={fieldErrors.confirmPassword}
                className="w-full"
              />
            </div>

            {/* Live Password Security Checklist */}
            <div className="p-3 bg-surface-100 dark:bg-surface-800/60 rounded-md border border-surface-200 dark:border-surface-700/60 text-xs space-y-1.5">
              <p className="font-semibold text-surface-700 dark:text-surface-300 mb-1">
                {t("auth.securityChecklistTitle") || "Security Requirements:"}
              </p>
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
                <span className={checks.notPersonal ? "text-success-600 font-bold" : "text-surface-400"}>
                  {checks.notPersonal ? "✓" : "○"}
                </span>
                <span className={checks.notPersonal ? "text-surface-800 dark:text-surface-200" : "text-surface-500"}>
                  {t("auth.checkNoPersonal") || "Does not contain your name or email"}
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

            <div>
              <label
                htmlFor="languageSelect"
                className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
              >
                {t("auth.preferredLanguageLabel") || "Preferred Interface Language"}
              </label>
              <Select
                id="languageSelect"
                value={preferredLang}
                onChange={(e) => setPreferredLang(e.target.value)}
                disabled={loading || registrationDisabled}
                options={[
                  { value: "en", label: "English" },
                  { value: "ta", label: "தமிழ் (Tamil)" },
                ]}
                className="w-full"
              />
            </div>

            <div className="pt-2">
              <div className="flex items-start">
                <input
                  ref={termsRef}
                  id="terms"
                  type="checkbox"
                  required
                  checked={termsAccepted}
                  onChange={(e) => {
                    setTermsAccepted(e.target.checked);
                    if (fieldErrors.terms) {
                      setFieldErrors((prev) => ({ ...prev, terms: undefined }));
                    }
                  }}
                  disabled={loading || registrationDisabled}
                  className="mt-1 h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500 dark:border-surface-700 dark:bg-surface-800"
                />
                <label
                  htmlFor="terms"
                  className="ml-2 block text-xs text-surface-600 dark:text-surface-400"
                >
                  {t("auth.agreePrompt") || "I agree to the"}{" "}
                  <Link to="/terms" target="_blank" className="text-primary-600 hover:underline">
                    {t("auth.termsOfService") || "Terms of Service"}
                  </Link>{" "}
                  {t("auth.andPrompt") || "and"}{" "}
                  <Link to="/privacy" target="_blank" className="text-primary-600 hover:underline">
                    {t("auth.privacyPolicy") || "Privacy Policy"}
                  </Link>
                  .
                </label>
              </div>
              {fieldErrors.terms && (
                <p role="alert" className="mt-1.5 text-xs text-red-600 dark:text-red-400 font-medium">
                  {fieldErrors.terms}
                </p>
              )}
            </div>

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                loading={loading}
                disabled={loading || !checks.allValid || !termsAccepted || registrationDisabled}
                className="w-full justify-center py-2.5"
              >
                {loading
                  ? (t("auth.creatingAccount") || "Creating Account...")
                  : (t("auth.signupButton") || "Complete Registration")}
              </Button>
            </div>
          </form>

          <div className="mt-6 pt-6 border-t border-surface-200 dark:border-surface-800 text-center">
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {t("auth.haveAccountPrompt") || "Already have an account?"}{" "}
              <Link
                to="/login"
                className="font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400"
              >
                {t("auth.signInLink") || "Sign in"}
              </Link>
            </p>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default Signup;
