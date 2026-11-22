import { apiClient } from "./apiClient";

/**
 * Send a chat turn to the CivicLens conversational AI assistant.
 *
 * @param {Object} params
 * @param {string} params.message - The citizen's message text (max 4000 chars)
 * @param {Array} [params.history=[]] - Array of { role: 'user'|'assistant', content: string }
 * @param {string} [params.language='auto'] - Desired reply language ('en', 'ta', 'auto')
 * @param {Object} [options={}] - Extra request options (e.g. signal for AbortController, timeout)
 * @returns {Promise<Object>} ChatResponse containing reply, language_used, model, latency_ms, etc.
 */
export async function sendChatMessage({ message, history = [], language = "auto" }, options = {}) {
  return apiClient.post(
    "/api/v1/chat",
    {
      message,
      history,
      language,
    },
    options
  );
}
