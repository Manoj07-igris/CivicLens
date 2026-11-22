/**
 * CivicLens Central API Client
 * Lightweight, robust fetch wrapper with timeout, standardized error parsing,
 * in-memory CSRF token management, credentials: "include", and automatic 401 interception.
 */

export class ApiError extends Error {
  constructor(message, code = "API_ERROR", status = 0, details = null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

const DEFAULT_TIMEOUT_MS = 15000;

// In-memory CSRF token storage (never stored in localStorage or cookies)
let _csrfToken = null;

export const setCsrfToken = (token) => {
  _csrfToken = token || null;
};

export const getCsrfToken = () => _csrfToken;

// Listeners for 401 Unauthorized events (to synchronize AuthContext without page reload)
const _unauthorizedListeners = new Set();

export const onUnauthorized = (listener) => {
  _unauthorizedListeners.add(listener);
  return () => _unauthorizedListeners.delete(listener);
};

export const notifyUnauthorized = () => {
  _csrfToken = null;
  _unauthorizedListeners.forEach((listener) => {
    try {
      listener();
    } catch (e) {
      console.error("Error in unauthorized listener:", e);
    }
  });
};

const getBaseUrl = () => {
  const envUrl = import.meta.env?.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim()) {
    return envUrl.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
};

async function request(endpoint, options = {}) {
  const baseUrl = getBaseUrl();
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${baseUrl}${cleanEndpoint}`;

  const {
    timeout = DEFAULT_TIMEOUT_MS,
    headers = {},
    signal: customSignal,
    method = "GET",
    ...fetchOptions
  } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // If a custom signal is supplied, listen to it as well
  if (customSignal) {
    customSignal.addEventListener("abort", () => controller.abort());
  }

  const defaultHeaders = {
    Accept: "application/json",
  };

  // Only set Content-Type to JSON if body is not FormData
  if (!(fetchOptions.body instanceof FormData)) {
    defaultHeaders["Content-Type"] = "application/json";
  }

  // Attach CSRF token and custom header for state-changing requests
  const normalizedMethod = method.toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(normalizedMethod)) {
    defaultHeaders["X-Requested-With"] = "CivicLens";
    if (_csrfToken) {
      defaultHeaders["X-CSRF-Token"] = _csrfToken;
    }
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      method: normalizedMethod,
      credentials: "include", // Enforce HttpOnly session cookie delivery
      signal: controller.signal,
      headers: {
        ...defaultHeaders,
        ...headers,
      },
    });

    clearTimeout(timeoutId);

    // Try to parse JSON response body
    let data;
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      // Intercept 401 Unauthorized
      if (response.status === 401) {
        // Only trigger auth logout state if not checking me or attempting login
        const isAuthCheck = cleanEndpoint.includes("/api/v1/auth/me");
        const isLoginAttempt = cleanEndpoint.includes("/api/v1/auth/login");
        if (!isAuthCheck && !isLoginAttempt) {
          notifyUnauthorized();
        }
      }

      // Backend standard error format: { error: { code, message, details } }
      if (data && typeof data === "object" && data.error) {
        throw new ApiError(
          data.error.message || `Request failed with status ${response.status}`,
          data.error.code || "REQUEST_FAILED",
          response.status,
          data.error.details
        );
      }
      throw new ApiError(
        typeof data === "string" && data ? data : `HTTP ${response.status} error`,
        `HTTP_${response.status}`,
        response.status
      );
    }

    // Capture CSRF token if returned in response payload or headers
    if (data && typeof data === "object" && data.csrf_token) {
      setCsrfToken(data.csrf_token);
    }

    return data;
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof ApiError) {
      throw error;
    }

    if (error.name === "AbortError") {
      throw new ApiError(
        "Request timed out. The CivicLens server took too long to respond.",
        "TIMEOUT",
        408
      );
    }

    // Network disconnection / server offline
    throw new ApiError(
      "Cannot reach the CivicLens backend server. Please verify the backend is running.",
      "NETWORK_OFFLINE",
      0
    );
  }
}

export const apiClient = {
  getBaseUrl() {
    return getBaseUrl();
  },

  setCsrfToken(token) {
    setCsrfToken(token);
  },

  getCsrfToken() {
    return getCsrfToken();
  },

  onUnauthorized(listener) {
    return onUnauthorized(listener);
  },

  get(endpoint, options = {}) {
    return request(endpoint, { ...options, method: "GET" });
  },

  post(endpoint, body, options = {}) {
    const isFormData = body instanceof FormData;
    return request(endpoint, {
      ...options,
      method: "POST",
      body: isFormData ? body : JSON.stringify(body),
    });
  },

  put(endpoint, body, options = {}) {
    const isFormData = body instanceof FormData;
    return request(endpoint, {
      ...options,
      method: "PUT",
      body: isFormData ? body : JSON.stringify(body),
    });
  },

  patch(endpoint, body, options = {}) {
    const isFormData = body instanceof FormData;
    return request(endpoint, {
      ...options,
      method: "PATCH",
      body: isFormData ? body : JSON.stringify(body),
    });
  },

  upload(endpoint, formData, options = {}) {
    return request(endpoint, {
      ...options,
      method: "POST",
      body: formData,
    });
  },

  delete(endpoint, options = {}) {
    return request(endpoint, {
      ...options,
      method: "DELETE",
    });
  },
};

export default apiClient;
