/**
 * LocalStorage utility for managing saved chat conversations.
 *
 * NOTE: Phase 15 will migrate conversation history and session persistence
 * to the SQLite backend database with user profiles.
 */

const STORAGE_KEY = "civiclens_chat_conversations";
const ACTIVE_CONV_KEY = "civiclens_active_conversation_id";
const MAX_CONVERSATIONS = 30;

/**
 * Safely read stored conversations list.
 * @returns {Array} List of conversations sorted by updatedAt descending.
 */
export function getStoredConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  } catch (err) {
    console.warn("Failed to read chat history from localStorage", err);
    return [];
  }
}

/**
 * Retrieve a specific conversation by ID.
 * @param {string} id
 * @returns {Object|null}
 */
export function getConversationById(id) {
  if (!id) return null;
  const all = getStoredConversations();
  return all.find((c) => c.id === id) || null;
}

/**
 * Save or update a conversation in localStorage, capped to MAX_CONVERSATIONS.
 * @param {Object} conv
 */
export function saveConversation(conv) {
  if (!conv || !conv.id) return;
  try {
    const all = getStoredConversations();
    const existingIndex = all.findIndex((c) => c.id === conv.id);

    const updatedConv = {
      ...conv,
      updatedAt: new Date().toISOString(),
    };

    if (existingIndex >= 0) {
      all[existingIndex] = updatedConv;
    } else {
      all.unshift(updatedConv);
    }

    // Keep only the most recent MAX_CONVERSATIONS
    const trimmed = all.slice(0, MAX_CONVERSATIONS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch (err) {
    console.warn("Failed to persist conversation to localStorage", err);
  }
}

/**
 * Delete a single conversation by ID.
 * @param {string} id
 */
export function deleteConversation(id) {
  if (!id) return;
  try {
    const all = getStoredConversations();
    const filtered = all.filter((c) => c.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered));

    if (getActiveConversationId() === id) {
      if (filtered.length > 0) {
        setActiveConversationId(filtered[0].id);
      } else {
        clearActiveConversationId();
      }
    }
  } catch (err) {
    console.warn("Failed to delete conversation from localStorage", err);
  }
}

/**
 * Clear all conversations from storage.
 */
export function clearAllConversations() {
  try {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(ACTIVE_CONV_KEY);
  } catch (err) {
    console.warn("Failed to clear conversations", err);
  }
}

/**
 * Get active conversation ID.
 * @returns {string|null}
 */
export function getActiveConversationId() {
  try {
    return localStorage.getItem(ACTIVE_CONV_KEY) || null;
  } catch {
    return null;
  }
}

/**
 * Set active conversation ID.
 * @param {string} id
 */
export function setActiveConversationId(id) {
  try {
    if (id) {
      localStorage.setItem(ACTIVE_CONV_KEY, id);
    } else {
      localStorage.removeItem(ACTIVE_CONV_KEY);
    }
  } catch (err) {
    console.warn("Failed to set active conversation ID", err);
  }
}

/**
 * Remove active conversation ID.
 */
export function clearActiveConversationId() {
  try {
    localStorage.removeItem(ACTIVE_CONV_KEY);
  } catch {
    // Ignore
  }
}

/**
 * Generate a clean, truncated title from the first message.
 * @param {string} text
 * @returns {string}
 */
export function generateConversationTitle(text) {
  if (!text || typeof text !== "string") return "New Conversation";
  const clean = text.replace(/[\r\n]+/g, " ").trim();
  if (clean.length <= 36) return clean;
  return clean.slice(0, 36).trim() + "...";
}
