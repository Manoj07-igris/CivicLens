/**
 * Fact Verification Service
 * Handles API calls for Fact Verification (Module 3).
 */

import { apiClient } from "./apiClient";

export const verificationService = {
  /**
   * Submit a public civic claim for fact verification.
   * @param {Object} params
   * @param {string} params.claim - Claim statement to verify (max 1000 chars)
   * @param {string} [params.language="auto"] - Desired output language ("en", "ta", "auto")
   * @param {string} [params.scope="official"] - Scope: "official", "official_and_documents", "documents"
   * @param {Array<string>} [params.documentIds=[]] - User document IDs if scope includes documents
   * @param {boolean} [params.force=false] - Bypass cache
   * @returns {Promise<Object>} Job response with verification_id and initial status
   */
  async submitVerification({
    claim,
    language = "auto",
    scope = "official",
    documentIds = [],
    force = false,
  }) {
    return apiClient.post("/api/v1/verify", {
      claim,
      language,
      scope,
      document_ids: documentIds,
      force,
    });
  },

  /**
   * Fetch verification status or completed report.
   * @param {string} verificationId
   * @returns {Promise<Object>}
   */
  async getVerificationStatus(verificationId) {
    if (!verificationId) throw new Error("Verification ID is required.");
    return apiClient.get(`/api/v1/verify/${encodeURIComponent(verificationId)}`);
  },

  /**
   * Retry AI analysis on an existing verification job.
   * @param {string} verificationId
   * @returns {Promise<Object>}
   */
  async retryAnalysis(verificationId) {
    if (!verificationId) throw new Error("Verification ID is required.");
    return apiClient.post(`/api/v1/verify/${encodeURIComponent(verificationId)}/retry-analysis`, {});
  },

  /**
   * List past fact verification reports.
   * @param {number} [limit=20]
   * @returns {Promise<{verifications: Array, total_count: number}>}
   */
  async listVerifications(limit = 20) {
    return apiClient.get(`/api/v1/verify?limit=${Math.max(1, Math.min(100, limit))}`);
  },

  /**
   * Delete a stored fact verification report.
   * @param {string} verificationId
   * @returns {Promise<void>}
   */
  async deleteVerification(verificationId) {
    if (!verificationId) throw new Error("Verification ID is required.");
    return apiClient.delete(`/api/v1/verify/${encodeURIComponent(verificationId)}`);
  },
};
