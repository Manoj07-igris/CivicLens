import React, { useState, useEffect } from "react";
import { Link, useNavigate, useLocation, useSearchParams } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import { useLanguage } from "../hooks/useLanguage";
import { useToast } from "../hooks/useToast";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Alert } from "../components/ui/Alert";
import { Logo } from "../components/ui/Logo";
import { LanguageSwitcher } from "../components/ui/LanguageSwitcher";
import { resolveAuthError } from "../utils/authErrors";

export function Login() {
  const { login, isAuthenticated } = useAuth();
  const { t } = useLanguage();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lockoutSeconds, setLockoutSeconds] = useState(0);

  // Determine redirect target
  const nextTarget =
    searchParams.get("next") ||
    location.state?.from?.pathname ||
    "/dashboard";

  useEffect(() => {
    if (isAuthenticated) {
      navigate(nextTarget, { replace: true });
    }
  }, [isAuthenticated, navigate, nextTarget]);

  // Lockout countdown timer
  useEffect(() => {
    if (lockoutSeconds <= 0) return;
    const interval = setInterval(() => {
      setLockoutSeconds((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [lockoutSeconds]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading || lockoutSeconds > 0) return;

    setError(null);
    setLoading(true);

    try {
      await login(email.trim(), password, rememberMe);
      addToast({
        type: "success",
        title: t("auth.loginSuccess") || "Welcome back!",
        message: t("auth.loginSuccessMessage") || "Signed in successfully.",
      });
      navigate(nextTarget, { replace: true });
    } catch (err) {
      const resolved = resolveAuthError(err, t);
      if (resolved.retryAfterSeconds) {
        setLockoutSeconds(resolved.retryAfterSeconds);
      }
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
          {t("auth.signInTitle") || "Sign in to CivicLens"}
        </h2>
        <p className="mt-2 text-center text-sm text-surface-600 dark:text-surface-400">
          {t("auth.tagline") || "Understand. Verify. Act. — Grounded Civic Intelligence"}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card className="p-6 sm:p-8 shadow-md">
          {error && (
            <div className="mb-6">
              <Alert
                variant="error"
                title={lockoutSeconds > 0 ? (t("auth.locked") || "Security Lockout Active") : undefined}
              >
                {lockoutSeconds > 0
                  ? `${t("auth.lockoutCountdown") || "Please wait before retrying:"} ${lockoutSeconds}s`
                  : error}
              </Alert>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="block text-sm font-medium text-surface-700 dark:text-surface-300 mb-1"
              >
                {t("auth.emailLabel") || "Email address"}
              </label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="citizen@example.com"
                disabled={loading || lockoutSeconds > 0}
                className="w-full"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-surface-700 dark:text-surface-300"
                >
                  {t("auth.passwordLabel") || "Password"}
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400"
                >
                  {t("auth.forgotPasswordLink") || "Forgot password?"}
                </Link>
              </div>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                disabled={loading || lockoutSeconds > 0}
                className="w-full"
              />
            </div>

            <div className="flex items-center">
              <input
                id="remember-me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                disabled={loading || lockoutSeconds > 0}
                className="h-4 w-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500 dark:border-surface-700 dark:bg-surface-800"
              />
              <label
                htmlFor="remember-me"
                className="ml-2 block text-sm text-surface-700 dark:text-surface-300"
              >
                {t("auth.rememberMe") || "Remember this device for 30 days"}
              </label>
            </div>

            <div>
              <Button
                type="submit"
                variant="primary"
                loading={loading}
                disabled={loading || lockoutSeconds > 0}
                className="w-full justify-center py-2.5"
              >
                {loading
                  ? (t("auth.signingIn") || "Signing in...")
                  : lockoutSeconds > 0
                  ? `${t("auth.locked") || "Locked"} (${lockoutSeconds}s)`
                  : (t("auth.signInButton") || "Sign In")}
              </Button>
            </div>
          </form>

          <div className="mt-6 pt-6 border-t border-surface-200 dark:border-surface-800 text-center">
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {t("auth.noAccountPrompt") || "Don't have an account?"}{" "}
              <Link
                to="/signup"
                className="font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400"
              >
                {t("auth.createAccountLink") || "Create citizen account"}
              </Link>
            </p>
          </div>
        </Card>

        <div className="mt-8 text-center text-xs text-surface-500 dark:text-surface-500 flex justify-center gap-4">
          <Link to="/terms" className="hover:underline">
            {t("auth.termsOfService") || "Terms of Service"}
          </Link>
          <span>•</span>
          <Link to="/privacy" className="hover:underline">
            {t("auth.privacyPolicy") || "Privacy Policy"}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default Login;
