/**
 * CivicLens Grievance Assistant API Service (Phase 13: Module 5)
 * Handles grievance creation, image upload with consent, deterministic review,
 * hash-bound simulated DEMO registration, and step advancement.
 */
import apiClient from "./apiClient";

export const grievanceService = {
  /**
   * Fetch grievance capabilities, safety rules summary, and configured limits.
   */
  async getCapabilities() {
    return apiClient.get("/api/v1/grievances/capabilities");
  },

  /**
   * Upload an optional photo for grievance analysis.
   * Image is metadata-stripped, orientation-adjusted, downscaled, and converted to clean JPEG.
   * @param {File} file
   * @returns {Promise<{image_id: string, width: number, height: number, size_bytes: number}>}
   */
  async uploadImage(file) {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post("/api/v1/grievances/image", formData, {
      timeout: 30000,
    });
  },

  /**
   * Start grievance analysis pipeline.
   * @param {Object} payload
   * @param {string} payload.description
   * @param {string} [payload.location_text]
   * @param {string} [payload.duration_text]
   * @param {string} [payload.language_of_draft="en"]
   * @param {string} [payload.category_hint]
   * @param {string} [payload.image_id]
   * @param {boolean} [payload.image_consent=false]
   */
  async analyzeGrievance(payload) {
    return apiClient.post("/api/v1/grievances/analyze", payload, {
      timeout: 45000,
    });
  },

  /**
   * Fetch a grievance record and async job status by ID.
   * @param {string} id
   */
  async getGrievance(id) {
    return apiClient.get(`/api/v1/grievances/${id}`);
  },

  /**
   * Re-run analysis with modified category hint, additional text, or newly attached image.
   * @param {string} id
   * @param {Object} payload
   */
  async retryAnalysis(id, payload) {
    return apiClient.post(`/api/v1/grievances/${id}/retry-analysis`, payload, {
      timeout: 45000,
    });
  },

  /**
   * Update draft fields (category, severity, subject, body, observations) during citizen review.
   * Re-verifies fact integrity and recalculates the SHA-256 draft hash.
   * @param {string} id
   * @param {Object} patch
   */
  async patchGrievance(id, patch) {
    return apiClient.patch(`/api/v1/grievances/${id}`, patch);
  },

  /**
   * Register a simulated DEMO complaint record.
   * Bound to human approval (approved=true) and exact draft SHA-256 hash.
   * @param {string} id
   * @param {Object} payload
   * @param {boolean} payload.approved
   * @param {string} payload.approved_hash
   */
  async registerDemo(id, payload) {
    return apiClient.post(`/api/v1/grievances/${id}/register-demo`, payload);
  },

  /**
   * Advance the simulated demo status forward.
   * Forward-only: registered -> under_review -> in_progress -> resolved
   * @param {string} id
   * @param {Object} [payload={}]
   * @param {string} [payload.note]
   */
  async advanceDemoStatus(id, payload = {}) {
    return apiClient.post(`/api/v1/grievances/${id}/demo-advance`, payload);
  },

  /**
   * List all stored grievance records (drafts & demo-registered), sorted newest first.
   */
  async listGrievances() {
    return apiClient.get("/api/v1/grievances");
  },

  /**
   * Permanently delete a grievance record and its associated image.
   * @param {string} id
   */
  async deleteGrievance(id) {
    return apiClient.delete(`/api/v1/grievances/${id}`);
  },

  /**
   * Helper to construct image URL for a processed grievance image.
   * @param {string} imageId
   */
  getImageUrl(imageId) {
    const base = apiClient.getBaseUrl ? apiClient.getBaseUrl() : "http://localhost:8000";
    return `${base}/api/v1/grievances/image/${imageId}`;
  },
};

export default grievanceService;
