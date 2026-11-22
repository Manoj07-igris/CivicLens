import { apiClient } from "./apiClient";

/**
 * Service for system administration, diagnostics, maintenance, and storage (Phase 15).
 */

export async function getSystemStatus() {
  return apiClient.get("/api/v1/system/status");
}

export async function getSystemStats() {
  return apiClient.get("/api/v1/system/stats");
}

export async function runBackup() {
  return apiClient.post("/api/v1/system/backup", {});
}

export async function runMaintenance(options = {}) {
  return apiClient.post("/api/v1/system/maintenance", options);
}

export async function deleteData(confirmPhrase, includeLibrary = false) {
  const query = new URLSearchParams({
    confirm: confirmPhrase,
    include_library: String(includeLibrary),
  });
  return apiClient.delete(`/api/v1/system/data?${query.toString()}`);
}

export async function getImportReport() {
  return apiClient.get("/api/v1/system/import-report");
}

export async function getActivity(params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", params.limit);
  if (params.offset) query.set("offset", params.offset);
  if (params.eventType) query.set("event_type", params.eventType);
  const qStr = query.toString();
  return apiClient.get(`/api/v1/activity${qStr ? `?${qStr}` : ""}`);
}

export async function getToolRuns(params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", params.limit);
  if (params.offset) query.set("offset", params.offset);
  const qStr = query.toString();
  return apiClient.get(`/api/v1/activity/tool-runs${qStr ? `?${qStr}` : ""}`);
}

export async function getPreferences() {
  return apiClient.get("/api/v1/preferences");
}

export async function setPreference(key, value) {
  return apiClient.put(`/api/v1/preferences/${encodeURIComponent(key)}`, { value: String(value) });
}
