/**
 * Playwright Browser Automation Service (Controlled Demo Workflow).
 * Communicates with /api/v1/browser for local simulation of public service applications.
 */

import { apiClient } from "./apiClient";

export const browserService = {
  /**
   * Get browser automation capabilities and sandbox limits.
   * @returns {Promise<{ enabled: boolean, headless: boolean, max_concurrent_sessions: number, active_sessions_count: number, supported_workflows: string[], demo_portal_url: string }>}
   */
  async getCapabilities() {
    return apiClient.get("/api/v1/browser/capabilities");
  },

  /**
   * Get the demo portal workflow manifest (steps, fields, sample values).
   * @returns {Promise<Object>}
   */
  async getManifest() {
    return apiClient.get("/api/v1/browser/manifest");
  },

  /**
   * Get verified fictional sample data.
   * @returns {Promise<{ workflow_id: string, disclaimer: string, values: Object }>}
   */
  async getSampleData() {
    return apiClient.get("/api/v1/browser/sample-data");
  },

  /**
   * Start a new controlled browser demo session on the local demo portal.
   * @param {Object} [params]
   * @param {string} [params.portalId="prt_demo_portal"]
   * @param {string} [params.lang="en"]
   * @param {string} [params.workflowId="demo_income_certificate"]
   * @returns {Promise<Object>}
   */
  async createSession({ portalId = "prt_demo_portal", lang = "en", workflowId = "demo_income_certificate" } = {}) {
    return apiClient.post("/api/v1/browser/sessions", {
      portal_id: portalId,
      lang,
      workflow_id: workflowId,
    });
  },

  /**
   * List recent demo browser sessions.
   * @param {number} [limit=20]
   * @returns {Promise<Array<Object>>}
   */
  async listSessions(limit = 20) {
    return apiClient.get(`/api/v1/browser/sessions?limit=${encodeURIComponent(limit)}`);
  },

  /**
   * Retrieve state, step, and screenshot references for a demo session.
   * @param {string} sessionId
   * @returns {Promise<Object>}
   */
  async getSession(sessionId) {
    if (!sessionId) throw new Error("Session ID is required.");
    return apiClient.get(`/api/v1/browser/sessions/${encodeURIComponent(sessionId)}`);
  },

  /**
   * Fill fictional values into form fields for a given step.
   * @param {string} sessionId
   * @param {number} stepIndex
   * @param {Object} values
   * @param {boolean} [fictionalConfirmed=true]
   * @returns {Promise<Object>}
   */
  async fillStep(sessionId, stepIndex, values, fictionalConfirmed = true) {
    if (!sessionId) throw new Error("Session ID is required.");
    return apiClient.post(`/api/v1/browser/sessions/${encodeURIComponent(sessionId)}/fill`, {
      step_index: stepIndex,
      values,
      fictional_confirmed: fictionalConfirmed,
    });
  },

  /**
   * Advance to the next form step.
   * @param {string} sessionId
   * @returns {Promise<Object>}
   */
  async navigateNext(sessionId) {
    if (!sessionId) throw new Error("Session ID is required.");
    return apiClient.post(`/api/v1/browser/sessions/${encodeURIComponent(sessionId)}/next`, {});
  },

  /**
   * Return to the previous form step.
   * @param {string} sessionId
   * @returns {Promise<Object>}
   */
  async navigateBack(sessionId) {
    if (!sessionId) throw new Error("Session ID is required.");
    return apiClient.post(`/api/v1/browser/sessions/${encodeURIComponent(sessionId)}/back`, {});
  },

  /**
   * Retrieve verified submission review preview and canonical review hash.
   * @param {string} sessionId
   * @returns {Promise<{ session_id: string, review_hash: string, filled_values: Object, summary: Object, disclaimer: string }>}
   */
  async getReviewPreview(sessionId) {
    if (!sessionId) throw new Error("Session ID is required.");
    return apiClient.get(`/api/v1/browser/sessions/${encodeURIComponent(sessionId)}/preview`);
  },

  /**
   * Finalize demo application simulation with verified human review hash.
   * @param {string} sessionId
   * @param {string} reviewHash
   * @param {boolean} [fictionalConfirmed=true]
   * @returns {Promise<Object>}
   */
  async submitDemo(sessionId, reviewHash, fictionalConfirmed = true) {
    if (!sessionId) throw new Error("Session ID is required.");
    if (!reviewHash) throw new Error("Review hash is required to confirm submission.");
    return apiClient.post(`/api/v1/browser/sessions/${encodeURIComponent(sessionId)}/submit`, {
      review_hash: reviewHash,
      fictional_confirmed: fictionalConfirmed,
    });
  },

  /**
   * Explicitly close a demo session.
   * @param {string} sessionId
   * @returns {Promise<Object>}
   */
  async closeSession(sessionId) {
    if (!sessionId) throw new Error("Session ID is required.");
    return apiClient.post(`/api/v1/browser/sessions/${encodeURIComponent(sessionId)}/close`, {});
  },

  /**
   * Get screenshot full URL for an image element.
   * @param {string} sessionId
   * @param {string} screenshotId
   * @returns {string}
   */
  getScreenshotUrl(sessionId, screenshotId) {
    if (!sessionId || !screenshotId) return "";
    const baseUrl = apiClient.getBaseUrl ? apiClient.getBaseUrl() : "http://127.0.0.1:8000";
    return `${baseUrl}/api/v1/browser/sessions/${encodeURIComponent(sessionId)}/screenshots/${encodeURIComponent(screenshotId)}`;
  },
};

export default browserService;
