import apiClient from "./apiClient";

export const authService = {
  /**
   * Fetch auth system capabilities and settings (public).
   */
  async getCapabilities() {
    return apiClient.get("/api/v1/auth/capabilities");
  },

  /**
   * Retrieve current authenticated citizen profile and active session.
   */
  async getMe() {
    return apiClient.get("/api/v1/auth/me");
  },

  /**
   * Register a new citizen account.
   */
  async register(data) {
    return apiClient.post("/api/v1/auth/register", data);
  },

  /**
   * Authenticate citizen with credentials.
   */
  async login(data) {
    return apiClient.post("/api/v1/auth/login", data);
  },

  /**
   * Log out of current session and invalidate cookie.
   */
  async logout() {
    return apiClient.post("/api/v1/auth/logout", {});
  },

  /**
   * Log out of all active sessions across all devices.
   */
  async logoutAll() {
    return apiClient.post("/api/v1/auth/logout-all", {});
  },

  /**
   * List all active sessions for current user.
   */
  async listSessions() {
    return apiClient.get("/api/v1/auth/sessions");
  },

  /**
   * Revoke a specific remote session.
   */
  async revokeSession(sessionId) {
    return apiClient.delete(`/api/v1/auth/sessions/${sessionId}`);
  },

  /**
   * Request password reset instructions via email or console fallback.
   */
  async forgotPassword(email) {
    return apiClient.post("/api/v1/auth/forgot-password", { email });
  },

  /**
   * Reset password using token from email link fragment.
   */
  async resetPassword(token, newPassword) {
    return apiClient.post("/api/v1/auth/reset-password", {
      token,
      new_password: newPassword,
    });
  },

  /**
   * Update profile fields (full name, preferred language).
   */
  async updateProfile(data) {
    return apiClient.patch("/api/v1/auth/me", data);
  },

  /**
   * Change password for authenticated user.
   */
  async changePassword(currentPassword, newPassword) {
    return apiClient.post("/api/v1/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },

  /**
   * Permanently delete account and all owned records.
   */
  async deleteAccount(password, confirmation = "DELETE") {
    return apiClient.delete("/api/v1/auth/me", {
      body: JSON.stringify({ password, confirmation }),
    });
  },

  /**
   * Admin-only: Claim legacy unowned 'local' records into admin account.
   */
  async claimLegacyData() {
    return apiClient.post("/api/v1/auth/claim-local-data", {});
  },
};

export default authService;
