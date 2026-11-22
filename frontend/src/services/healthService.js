import { apiClient } from "./apiClient";

export async function getHealth(options = {}) {
  return apiClient.get("/api/v1/health", options);
}

export async function getInfo(options = {}) {
  return apiClient.get("/api/v1/info", options);
}
