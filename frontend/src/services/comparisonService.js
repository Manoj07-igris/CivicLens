/**
 * Comparison Service
 * Handles API calls for Policy Change Detection (Module 2).
 */

import { apiClient } from "./apiClient";

export const comparisonService = {
  /**
   * Start a new policy comparison job.
   * @param {Object} params
   * @param {string} params.oldDocumentId - UUID of the older policy document
   * @param {string} params.newDocumentId - UUID of the newer policy document
   * @param {string} [params.language="auto"] - Language for summaries ("en", "ta", "auto")
   * @param {boolean} [params.force=false] - Bypass cache and re-run comparison
   * @returns {Promise<Object>} Job response with comparison_id and status
   */
  async startComparison({ oldDocumentId, newDocumentId, language = "auto", force = false }) {
    return apiClient.post("/api/v1/compare", {
      old_document_id: oldDocumentId,
      new_document_id: newDocumentId,
      language,
      force,
    });
  },

  /**
   * Fetch comparison status or completed report.
   * @param {string} comparisonId - Comparison UUID
   * @returns {Promise<Object>} Comparison report or job status
   */
  async getComparison(comparisonId) {
    if (!comparisonId) throw new Error("Comparison ID is required.");
    return apiClient.get(`/api/v1/compare/${encodeURIComponent(comparisonId)}`);
  },

  /**
   * Retry AI analysis on an existing comparison without re-aligning.
   * @param {string} comparisonId - Comparison UUID
   * @returns {Promise<Object>} Updated report or job status
   */
  async retryAnalysis(comparisonId) {
    if (!comparisonId) throw new Error("Comparison ID is required.");
    return apiClient.post(`/api/v1/compare/${encodeURIComponent(comparisonId)}/retry-analysis`, {});
  },

  /**
   * List past comparison reports.
   * @param {number} [limit=20] - Maximum records to retrieve
   * @returns {Promise<{comparisons: Array, total: number}>}
   */
  async listComparisons(limit = 20) {
    return apiClient.get(`/api/v1/compare?limit=${Math.max(1, Math.min(100, limit))}`);
  },

  /**
   * Delete a stored comparison report.
   * @param {string} comparisonId - Comparison UUID
   * @returns {Promise<{deleted: boolean, comparison_id: string}>}
   */
  async deleteComparison(comparisonId) {
    if (!comparisonId) throw new Error("Comparison ID is required.");
    return apiClient.delete(`/api/v1/compare/${encodeURIComponent(comparisonId)}`);
  },
};
