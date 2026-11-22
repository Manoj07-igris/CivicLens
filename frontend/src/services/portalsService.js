/**
 * Curated Official Portal Registry API Client (Module 4).
 * Communicates with /api/v1/portals for verified government portal directory.
 */

import { apiClient } from "./apiClient";

export const portalsService = {
  /**
   * List portals from curated registry with optional filtering.
   * @param {Object} [params]
   * @param {string} [params.serviceType]
   * @param {string} [params.scope]
   * @param {string} [params.status="active"]
   * @param {string} [params.kind]
   * @returns {Promise<{ total: number, portals: Array<Object> }>}
   */
  async listPortals(params = {}) {
    const searchParams = new URLSearchParams();
    if (params.serviceType) searchParams.append("service_type", params.serviceType);
    if (params.scope) searchParams.append("scope", params.scope);
    if (params.status) searchParams.append("status", params.status);
    if (params.kind) searchParams.append("kind", params.kind);

    const qs = searchParams.toString();
    const endpoint = `/api/v1/portals${qs ? `?${qs}` : ""}`;
    return apiClient.get(endpoint);
  },

  /**
   * Retrieve a single portal entry.
   * @param {string} portalId
   * @returns {Promise<Object>}
   */
  async getPortal(portalId) {
    if (!portalId) throw new Error("Portal ID is required.");
    return apiClient.get(`/api/v1/portals/${encodeURIComponent(portalId)}`);
  },

  /**
   * Register a new official portal (Requires ALLOW_PORTAL_MANAGEMENT).
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  async createPortal(data) {
    return apiClient.post("/api/v1/portals", data);
  },

  /**
   * Update an existing portal entry.
   * @param {string} portalId
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  async updatePortal(portalId, data) {
    if (!portalId) throw new Error("Portal ID is required.");
    return apiClient.patch(`/api/v1/portals/${encodeURIComponent(portalId)}`, data);
  },

  /**
   * Delete a portal from the registry.
   * @param {string} portalId
   * @returns {Promise<Object>}
   */
  async deletePortal(portalId) {
    if (!portalId) throw new Error("Portal ID is required.");
    return apiClient.delete(`/api/v1/portals/${encodeURIComponent(portalId)}`);
  },

  /**
   * Deterministically match portals against citizen query.
   * @param {Object} params
   * @param {string} params.query
   * @param {Array<string>} [params.linkedSourceIds]
   * @param {number} [params.limit=3]
   * @param {boolean} [params.allowDemo=false]
   * @returns {Promise<Array<Object>>}
   */
  async matchPortals({ query, linkedSourceIds = [], limit = 3, allowDemo = false }) {
    return apiClient.post("/api/v1/portals/match", {
      query,
      linked_source_ids: linkedSourceIds,
      limit,
      allow_demo: allowDemo,
    });
  },
};
