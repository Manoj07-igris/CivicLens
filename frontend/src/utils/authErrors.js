/**
 * Centralized Authentication Error Resolver for CivicLens
 * Maps backend error codes, HTTP statuses, and validation detail arrays
 * to user-friendly, translated, accessible error messages in English and Tamil.
 */

export function resolveAuthError(err, t) {
  if (!err) {
    return {
      topLevel: t("auth.errors.generic_error") || "Something went wrong. Please try again.",
      fieldErrors: {},
    };
  }

  const fieldErrors = {};
  let topLevel = null;

  // 1. Network / Backend unreachable (explicit network offline code, status 0, or browser fetch TypeError)
  const isFetchNetworkError =
    err.name === "TypeError" &&
    typeof err.message === "string" &&
    (err.message.toLowerCase().includes("fetch") || err.message.toLowerCase().includes("network"));

  if (err.code === "NETWORK_OFFLINE" || err.status === 0 || isFetchNetworkError) {
    return {
      topLevel:
        t("auth.errors.backend_unreachable") ||
        "Cannot reach the CivicLens server. Please ensure the backend is running and try again.",
      fieldErrors: {},
      isNetworkOffline: true,
    };
  }

  // 2. Throttled / Rate limit exceeded
  if (
    err.status === 429 ||
    err.code === "RATE_LIMIT_EXCEEDED" ||
    err.code === "AUTH_THROTTLED" ||
    err.code === "too_many_attempts"
  ) {
    const retryAfter = err.details?.retry_after_seconds;
    const msg = retryAfter
      ? `${t("auth.errors.too_many_attempts") || "Too many attempts. Please try again in"} ${retryAfter}s.`
      : t("auth.errors.too_many_attempts") || "Too many failed attempts. Please try again later.";
    return {
      topLevel: msg,
      fieldErrors: {},
      retryAfterSeconds: retryAfter || 60,
    };
  }

  // 3. Email already registered
  if (err.status === 409 || err.code === "EMAIL_ALREADY_EXISTS" || err.code === "email_unavailable") {
    const msg =
      t("auth.errors.email_unavailable") ||
      t("auth.emailConflictError") ||
      "An account is already registered with this email address. Please sign in instead.";
    fieldErrors.email = msg;
    return {
      topLevel: msg,
      fieldErrors,
    };
  }

  // 4. Registration disabled
  if (err.code === "REGISTRATION_DISABLED" || err.code === "registration_disabled") {
    return {
      topLevel:
        t("auth.errors.registration_disabled") ||
        "New account registration is currently disabled by system policy.",
      fieldErrors: {},
    };
  }

  // 5. Invalid credentials (login)
  if (err.code === "INVALID_CREDENTIALS" || (err.status === 401 && !err.code)) {
    return {
      topLevel:
        t("auth.errors.invalid_credentials") ||
        t("auth.invalidCredentials") ||
        "Invalid email or password. Please verify your credentials.",
      fieldErrors: {},
    };
  }

  // 6. Invalid or expired reset token
  if (err.code === "INVALID_RESET_TOKEN" || err.code === "invalid_or_expired_token") {
    return {
      topLevel:
        t("auth.errors.invalid_or_expired_token") ||
        t("auth.resetFailed") ||
        "Password reset link is invalid or has expired. Please request a new one.",
      fieldErrors: {},
    };
  }

  // 7. Password policy error
  const detailCode = err.details?.code || err.details?.reason;
  if (err.code === "WEAK_PASSWORD" || detailCode?.startsWith("password_")) {
    let msg = "";
    if (detailCode === "password_too_short" || err.message?.toLowerCase().includes("at least 12")) {
      msg = t("auth.errors.password_too_short") || "Password must be at least 12 characters long.";
    } else if (detailCode === "password_too_long" || err.message?.toLowerCase().includes("128 characters")) {
      msg = t("auth.errors.password_too_long") || "Password must not exceed 128 characters.";
    } else if (detailCode === "password_common" || err.message?.toLowerCase().includes("too common")) {
      msg =
        t("auth.errors.password_common") ||
        "This password is too common and easily guessed. Please choose a more unique passphrase.";
    } else if (
      detailCode === "password_contains_personal_info" ||
      err.message?.toLowerCase().includes("name") ||
      err.message?.toLowerCase().includes("email")
    ) {
      msg =
        t("auth.errors.password_contains_personal_info") ||
        "Password must not contain parts of your name or email address.";
    } else if (detailCode === "password_repetitive" || err.message?.toLowerCase().includes("repetitive")) {
      msg =
        t("auth.errors.password_repetitive") ||
        "Password contains repetitive repeating sequences or simple patterns.";
    } else if (detailCode === "terms_not_accepted") {
      msg =
        t("auth.errors.terms_not_accepted") ||
        t("auth.termsRequiredError") ||
        "You must review and accept the Terms of Service to create an account.";
      fieldErrors.terms = msg;
      return { topLevel: msg, fieldErrors };
    } else {
      msg = err.message || t("auth.passwordPolicyError") || "Password does not meet security standards.";
    }
    fieldErrors.password = msg;
    return { topLevel: msg, fieldErrors };
  }

  // 8. Field-level validation errors from FastAPI (HTTP 422)
  if (err.status === 422 && Array.isArray(err.details)) {
    for (const item of err.details) {
      const loc = (item.location || "").toLowerCase();
      if (loc.includes("accept_terms") || loc.includes("terms_accepted")) {
        const msg =
          t("auth.errors.terms_not_accepted") ||
          t("auth.termsRequiredError") ||
          "You must review and accept the Terms of Service to create an account.";
        fieldErrors.terms = msg;
        if (!topLevel) topLevel = msg;
      } else if (loc.includes("email")) {
        const msg = t("auth.errors.invalid_email") || "Please provide a valid email address.";
        fieldErrors.email = msg;
        if (!topLevel) topLevel = msg;
      } else if (loc.includes("password")) {
        const msg =
          t("auth.errors.password_too_short") || "Password must be at least 12 characters long.";
        fieldErrors.password = msg;
        if (!topLevel) topLevel = msg;
      } else if (loc.includes("full_name")) {
        const msg = "Please enter your full name.";
        fieldErrors.fullName = msg;
        if (!topLevel) topLevel = msg;
      }
    }
  }

  // 9. Fallback if no specific top-level message was set
  if (!topLevel) {
    topLevel =
      (typeof err.message === "string" && err.message.trim()) ||
      t("auth.errors.generic_error") ||
      "Account registration could not be completed. Please check your entries.";
  }

  return {
    topLevel,
    fieldErrors,
  };
}
