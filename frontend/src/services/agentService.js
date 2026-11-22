import { apiClient } from "./apiClient";

/**
 * CivicLens Central AI Agent Service
 * Handles conversational queries with backend function calling, tool registry queries,
 * and citizen approval authorizations.
 */

/**
 * Send a message to the Central AI Agent with automatic tool execution.
 *
 * @param {Object} params
 * @param {string} params.message - User prompt / question
 * @param {Array} [params.history=[]] - Chat history items { role, content }
 * @param {string} [params.language='auto'] - Reply language preference ('en', 'ta', 'auto')
 * @param {Array<string>} [params.documentIds=[]] - UUIDs of documents attached to conversation
 * @param {Object} [options={}] - Custom fetch options (signal, timeout)
 * @returns {Promise<Object>} AgentResponse
 */
export async function sendAgentMessage(
  { message, history = [], language = "auto", documentIds = [], conversationId = null },
  options = {}
) {
  const fetchOptions = {
    timeout: 60000,
    ...options,
  };

  const payload = {
    message,
    history,
    language,
    document_ids: documentIds,
  };
  if (conversationId) {
    payload.conversation_id = conversationId;
  }

  return apiClient.post(
    "/api/v1/agent/chat",
    payload,
    fetchOptions
  );
}

/**
 * Fetch list of all registered tools and their availability status.
 *
 * @param {Object} [options={}]
 * @returns {Promise<Object>} ToolsListResponse
 */
export async function getAgentTools(options = {}) {
  return apiClient.get("/api/v1/agent/tools", options);
}

/**
 * Submit citizen authorization decision ('approve' or 'deny') for a pending tool action.
 *
 * @param {string} approvalId - The unique pending approval identifier
 * @param {string} decision - 'approve' or 'deny'
 * @param {Object} [options={}]
 * @returns {Promise<Object>} ApprovalDecisionResponse
 */
export async function decideApproval(approvalId, decision, options = {}) {
  const fetchOptions = {
    timeout: 30000,
    ...options,
  };

  return apiClient.post(
    `/api/v1/agent/approvals/${encodeURIComponent(approvalId)}`,
    { decision },
    fetchOptions
  );
}
