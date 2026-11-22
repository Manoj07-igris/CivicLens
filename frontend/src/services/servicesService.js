/**
 * Public Service Assistant Service (Module 4)
 * Handles API calls for procedural guidance, interactive checklists,
 * and form field explanations.
 */

import { apiClient } from "./apiClient";

export const servicesService = {
  /**
   * Request evidence-grounded procedural guidance and checklist.
   * @param {Object} params
   * @param {string} params.query - Target public service query
   * @param {string} [params.applicantType="unspecified"] - Demographic category
   * @param {string} [params.applicantSituation] - Optional situational context
   * @param {string} [params.language="auto"] - Language preference ("en", "ta", "auto")
   * @param {boolean} [params.allowGeneral=false] - Allow general guidance if 0 sources
   * @param {string} [params.sourceScope="all"] - "all", "official_only", "user_documents_only"
   * @param {Array<string>} [params.documentIds] - Specific user documents to include
   * @returns {Promise<Object>} ServiceGuideReport
   */
  async generateGuide({
    query,
    applicantType = "unspecified",
    applicantSituation = null,
    language = "auto",
    allowGeneral = false,
    sourceScope = "all",
    documentIds = null,
  }) {
    return apiClient.post("/api/v1/services/guide", {
      query,
      applicant_type: applicantType,
      applicant_situation: applicantSituation,
      language,
      allow_general: allowGeneral,
      source_scope: sourceScope,
      document_ids: documentIds,
    });
  },

  /**
   * Retrieve an existing public service guidance report.
   * @param {string} guideId
   * @returns {Promise<Object>}
   */
  async getGuide(guideId) {
    if (!guideId) throw new Error("Guide ID is required.");
    return apiClient.get(`/api/v1/services/guide/${encodeURIComponent(guideId)}`);
  },

  /**
   * Retry guidance analysis for an existing guide.
   * @param {string} guideId
   * @returns {Promise<Object>}
   */
  async retryGuide(guideId) {
    if (!guideId) throw new Error("Guide ID is required.");
    return apiClient.post(`/api/v1/services/guide/${encodeURIComponent(guideId)}/retry-analysis`);
  },

  /**
   * List previously generated service guides.
   * @param {number} [limit=20]
   * @returns {Promise<Object>} { total, guides }
   */
  async listGuides(limit = 20) {
    return apiClient.get(`/api/v1/services/guides?limit=${encodeURIComponent(limit)}`);
  },

  /**
   * Delete a saved service guide.
   * @param {string} guideId
   * @returns {Promise<Object>}
   */
  async deleteGuide(guideId) {
    if (!guideId) throw new Error("Guide ID is required.");
    return apiClient.delete(`/api/v1/services/guide/${encodeURIComponent(guideId)}`);
  },

  /**
   * Extract candidate fields from a user-uploaded PDF or pasted text.
   * @param {Object} params
   * @param {string} [params.documentId]
   * @param {string} [params.rawText]
   * @returns {Promise<Object>} { fields, total_detected }
   */
  async extractFormFields({ documentId = null, rawText = null }) {
    return apiClient.post("/api/v1/services/form-fields/extract", {
      document_id: documentId,
      raw_text: rawText,
    });
  },

  /**
   * Generate plain-language explanations for candidate form fields.
   * @param {Object} params
   * @param {Array<string>} params.fieldNames
   * @param {string} [params.documentId]
   * @param {string} [params.contextText]
   * @param {string} [params.language="auto"]
   * @returns {Promise<Object>} { explanations, disclaimer }
   */
  async explainFormFields({
    fieldNames,
    documentId = null,
    contextText = null,
    language = "auto",
  }) {
    return apiClient.post("/api/v1/services/form-fields/explain", {
      field_names: fieldNames,
      document_id: documentId,
      context_text: contextText,
      language,
    });
  },
};
