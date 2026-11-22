import { apiClient } from "./apiClient";

/**
 * Fetch Gemini configuration status without consuming AI quota.
 * Returns { configured: boolean, model: string }
 */
export async function getGeminiStatus(options = {}) {
  return apiClient.get("/api/v1/gemini/status", options);
}

/**
 * Run a single lightweight diagnostic test call to verify live Gemini connectivity.
 * Returns { success: boolean, message: string, model: string, latency_ms: number, token_usage: object }
 */
export async function runGeminiTest(options = {}) {
  return apiClient.post("/api/v1/gemini/test", {}, options);
}
