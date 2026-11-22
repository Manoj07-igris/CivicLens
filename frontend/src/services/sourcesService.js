/**
 * Official Sources Service
 * Handles API calls for the Official Source Library (Module 3).
 */

import { apiClient } from "./apiClient";

export const sourcesService = {
  /**
   * List all official government sources.
   * @returns {Promise<{sources: Array, total_count: number}>}
   */
  async listSources() {
    return apiClient.get("/api/v1/sources");
  },

  /**
   * Get metadata for a specific official source.
   * @param {string} sourceId
   * @returns {Promise<Object>}
   */
  async getSource(sourceId) {
    if (!sourceId) throw new Error("Source ID is required.");
    return apiClient.get(`/api/v1/sources/${encodeURIComponent(sourceId)}`);
  },

  /**
   * Upload and register a new official document.
   * @param {FormData} formData
   * @returns {Promise<Object>}
   */
  async uploadSource(formData) {
    return apiClient.post("/api/v1/sources", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },

  /**
   * Update metadata of an existing official source.
   * @param {string} sourceId
   * @param {Object} updateData
   * @returns {Promise<Object>}
   */
  async updateSource(sourceId, updateData) {
    if (!sourceId) throw new Error("Source ID is required.");
    return apiClient.patch(`/api/v1/sources/${encodeURIComponent(sourceId)}`, updateData);
  },

  /**
   * Delete an official source from the library.
   * @param {string} sourceId
   * @returns {Promise<void>}
   */
  async deleteSource(sourceId) {
    if (!sourceId) throw new Error("Source ID is required.");
    return apiClient.delete(`/api/v1/sources/${encodeURIComponent(sourceId)}`);
  },

  /**
   * Rebuild the FAISS vector index for an official source.
   * @param {string} sourceId
   * @returns {Promise<Object>}
   */
  async rebuildIndex(sourceId) {
    if (!sourceId) throw new Error("Source ID is required.");
    return apiClient.post(`/api/v1/sources/${encodeURIComponent(sourceId)}/index`, {});
  },

  /**
   * Get URL for original PDF file download or preview.
   * @param {string} sourceId
   * @returns {string}
   */
  getSourceFileUrl(sourceId) {
    return `/api/v1/sources/${encodeURIComponent(sourceId)}/file`;
  },

  /**
   * Get URL for rendered page image.
   * @param {string} sourceId
   * @param {number} pageNumber
   * @returns {string}
   */
  getSourcePageImageUrl(sourceId, pageNumber) {
    return `/api/v1/sources/${encodeURIComponent(sourceId)}/pages/${pageNumber}`;
  },
};
