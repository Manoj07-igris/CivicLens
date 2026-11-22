import { apiClient } from "./apiClient";

/**
 * Service for persisted Chat Conversations and message history (Phase 15).
 */

export async function listConversations(params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", params.limit);
  if (params.offset) query.set("offset", params.offset);
  const qStr = query.toString();
  return apiClient.get(`/api/v1/conversations${qStr ? `?${qStr}` : ""}`);
}

export async function createConversation(data = {}) {
  return apiClient.post("/api/v1/conversations", data);
}

export async function getConversation(conversationId, params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", params.limit);
  if (params.beforeSeq) query.set("before_seq", params.beforeSeq);
  const qStr = query.toString();
  return apiClient.get(`/api/v1/conversations/${conversationId}${qStr ? `?${qStr}` : ""}`);
}

export async function updateConversation(conversationId, data = {}) {
  return apiClient.patch(`/api/v1/conversations/${conversationId}`, data);
}

export async function deleteConversation(conversationId) {
  return apiClient.delete(`/api/v1/conversations/${conversationId}`);
}

export async function deleteAllConversations(confirmPhrase) {
  return apiClient.delete(
    `/api/v1/conversations?confirm=${encodeURIComponent(confirmPhrase)}`
  );
}

export async function importConversations(conversations) {
  return apiClient.post("/api/v1/conversations/import", { conversations });
}
