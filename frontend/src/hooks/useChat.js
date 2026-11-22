import { useState, useCallback, useRef, useEffect } from "react";
import { sendAgentMessage, decideApproval } from "../services/agentService";
import {
  listConversations,
  getConversation,
  createConversation,
  updateConversation,
  deleteConversation as deleteBackendConversation,
  importConversations,
} from "../services/conversationService";
import {
  getStoredConversations,
  getConversationById,
  saveConversation,
  deleteConversation as deleteStoredConversation,
  setActiveConversationId,
  getActiveConversationId,
  generateConversationTitle,
} from "../utils/chatStorage";

export function useChat(initialLanguage = "auto") {
  const [conversations, setConversations] = useState(() => getStoredConversations());
  const [activeId, setActiveId] = useState(() => getActiveConversationId());
  const [messages, setMessages] = useState([]);
  const [selectedDocumentIds, setSelectedDocumentIdsState] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [language, setLanguage] = useState(initialLanguage);

  // Migration status
  const [unmigratedCount, setUnmigratedCount] = useState(0);
  const [isMigrating, setIsMigrating] = useState(false);

  const abortControllerRef = useRef(null);

  // Safely limit selected documents to max 5
  const setSelectedDocumentIds = useCallback((newIds) => {
    const safeIds = Array.isArray(newIds) ? newIds.slice(0, 5) : [];
    setSelectedDocumentIdsState(safeIds);
  }, []);

  const toggleDocumentId = useCallback((docId) => {
    if (!docId) return;
    setSelectedDocumentIdsState((prev) => {
      if (prev.includes(docId)) {
        return prev.filter((id) => id !== docId);
      }
      if (prev.length >= 5) {
        return prev;
      }
      return [...prev, docId];
    });
  }, []);

  // Helper to map backend message row to UI message object
  const mapBackendMessage = useCallback((m) => {
    const meta = m.meta || {};
    return {
      id: m.id,
      role: m.role,
      content: m.content,
      languageUsed: m.language_used,
      intent: m.intent,
      grounded: m.grounded !== undefined ? Boolean(m.grounded) : undefined,
      sources: meta.sources || [],
      toolActivity: meta.tool_activity || [],
      model: m.model,
      pendingApproval: meta.pending_approval || null,
      warnings: meta.warnings || [],
      verifications: meta.verifications || [],
      checklists: meta.checklists || [],
      grievances: meta.grievances || [],
      browserSessions: meta.browser_sessions || [],
      timestamp: m.created_at || new Date().toISOString(),
    };
  }, []);

  // Load a conversation's messages from backend
  const loadConversationMessages = useCallback(
    async (convId) => {
      if (!convId) return;
      try {
        const res = await getConversation(convId);
        if (res && res.messages) {
          const uiMsgs = res.messages.map(mapBackendMessage);
          setMessages(uiMsgs);
          if (res.conversation?.document_ids) {
            setSelectedDocumentIdsState(res.conversation.document_ids);
          }
        }
      } catch (err) {
        console.warn(`Failed to load messages for conversation ${convId} from backend`, err);
        // Fallback to local storage if present
        const local = getConversationById(convId);
        if (local) {
          setMessages(local.messages || []);
          setSelectedDocumentIdsState(local.selectedDocumentIds || []);
        }
      }
    },
    [mapBackendMessage]
  );

  // Initialize and load conversations on mount
  useEffect(() => {
    // Check for unmigrated local conversations
    const isMigrated = localStorage.getItem("civiclens_conversations_migrated");
    const localConvs = getStoredConversations();
    if (!isMigrated && localConvs.length > 0) {
      setUnmigratedCount(localConvs.length);
    }

    // Load from backend
    listConversations({ limit: 50 })
      .then((res) => {
        if (res && Array.isArray(res.items) && res.items.length > 0) {
          setConversations(res.items);
          const savedActiveId = getActiveConversationId();
          const targetId =
            (res.items.some((c) => c.id === savedActiveId) && savedActiveId) ||
            res.items[0].id;
          setActiveId(targetId);
          setActiveConversationId(targetId);
          loadConversationMessages(targetId);
        } else if (localConvs.length > 0) {
          // If backend has no conversations yet but local storage does
          setConversations(localConvs);
          const savedActiveId = getActiveConversationId();
          if (savedActiveId) {
            const activeConv = getConversationById(savedActiveId);
            if (activeConv) {
              setMessages(activeConv.messages || []);
              setSelectedDocumentIdsState(activeConv.selectedDocumentIds || []);
            }
          }
        }
      })
      .catch((err) => {
        console.warn("Could not fetch conversations from backend, using local storage", err);
        setConversations(localConvs);
        const savedActiveId = getActiveConversationId();
        if (savedActiveId) {
          const activeConv = getConversationById(savedActiveId);
          if (activeConv) {
            setMessages(activeConv.messages || []);
            setSelectedDocumentIdsState(activeConv.selectedDocumentIds || []);
          }
        }
      });
  }, [loadConversationMessages]);

  const startNewChat = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setActiveId(null);
    setMessages([]);
    setSelectedDocumentIdsState([]);
    setError(null);
    setIsLoading(false);
    setActiveConversationId("");
  }, []);

  const switchConversation = useCallback(
    (id) => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      setActiveId(id);
      setActiveConversationId(id);
      setError(null);
      setIsLoading(false);
      loadConversationMessages(id);
    },
    [loadConversationMessages]
  );

  const deleteChat = useCallback(
    async (id) => {
      // 1. Delete from backend
      try {
        await deleteBackendConversation(id);
      } catch (err) {
        console.warn("Backend conversation deletion failed, cleaning locally", err);
      }
      // 2. Delete from localStorage
      deleteStoredConversation(id);

      // 3. Update list state
      setConversations((prev) => {
        const updated = prev.filter((c) => c.id !== id);
        if (activeId === id) {
          if (updated.length > 0) {
            switchConversation(updated[0].id);
          } else {
            startNewChat();
          }
        }
        return updated;
      });
    },
    [activeId, switchConversation, startNewChat]
  );

  const renameChat = useCallback(async (id, newTitle) => {
    const cleanTitle = newTitle.trim();
    if (!cleanTitle) return;

    // 1. Update on backend
    try {
      await updateConversation(id, { title: cleanTitle });
    } catch (err) {
      console.warn("Backend conversation rename failed", err);
    }

    // 2. Update locally
    const conv = getConversationById(id);
    if (conv) {
      saveConversation({ ...conv, title: cleanTitle });
    }

    // 3. Update state
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: cleanTitle } : c))
    );
  }, []);

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
  }, []);

  const sendMessage = useCallback(
    async (text, overrideDocIds = null) => {
      const cleanText = text?.trim();
      if (!cleanText || isLoading) return;

      setError(null);
      setIsLoading(true);

      const userMsgId = `user_${Date.now()}`;
      const userMessage = {
        id: userMsgId,
        role: "user",
        content: cleanText,
        timestamp: new Date().toISOString(),
      };

      const updatedMessages = [...messages, userMessage];
      setMessages(updatedMessages);

      // Active documents context
      const activeDocIds =
        overrideDocIds !== null ? overrideDocIds.slice(0, 5) : selectedDocumentIds;

      // Determine or provision conversation ID
      let currentConvId = activeId;
      if (!currentConvId) {
        try {
          const newConv = await createConversation({
            title: generateConversationTitle(cleanText),
            language_setting: language,
            document_ids: activeDocIds,
          });
          currentConvId = newConv.id;
          setActiveId(currentConvId);
          setActiveConversationId(currentConvId);
          setConversations((prev) => [newConv, ...prev.filter((c) => c.id !== currentConvId)]);
        } catch (convErr) {
          console.warn("Failed to provision conversation on backend", convErr);
          currentConvId = `conv_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
          setActiveId(currentConvId);
          setActiveConversationId(currentConvId);
        }
      }

      // Create AbortController for cancellation
      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Prepare history payload for active turn (backend will also supplement via budget)
      const historyPayload = messages
        .filter((m) => !m.error)
        .map((m) => ({
          role: m.role,
          content: m.content,
        }));

      try {
        const response = await sendAgentMessage(
          {
            message: cleanText,
            history: historyPayload,
            language,
            documentIds: activeDocIds,
            conversationId: currentConvId,
          },
          { signal: controller.signal }
        );

        const assistantMessage = {
          id: response.message_id || `asst_${Date.now()}`,
          role: "assistant",
          content: response.reply,
          languageUsed: response.language_used,
          intent: response.intent,
          grounded: response.grounded,
          sources: response.sources || [],
          toolActivity: response.tool_activity || [],
          stepsUsed: response.steps_used || 1,
          model: response.model,
          latencyMs: response.latency_ms,
          tokenUsage: response.token_usage,
          pendingApproval: response.pending_approval || null,
          warnings: response.warnings || [],
          verifications: response.verifications || [],
          checklists: response.checklists || [],
          grievances: response.grievances || [],
          browserSessions: response.browser_sessions || [],
          timestamp: new Date().toISOString(),
        };

        const finalMessages = [...updatedMessages, assistantMessage];
        setMessages(finalMessages);

        // Update conversation metadata in list
        setConversations((prev) =>
          prev.map((c) => {
            if (c.id === currentConvId) {
              const updatedTitle =
                c.title === "New Conversation"
                  ? generateConversationTitle(cleanText)
                  : c.title;
              return {
                ...c,
                title: updatedTitle,
                message_count: (c.message_count || 0) + 2,
                updated_at: new Date().toISOString(),
              };
            }
            return c;
          })
        );
      } catch (err) {
        if (err.name === "AbortError") {
          return;
        }

        const errorMessage =
          err?.message || "Failed to get a response from CivicLens central agent.";
        setError(errorMessage);

        const errorAssistantMessage = {
          id: `err_${Date.now()}`,
          role: "assistant",
          content: errorMessage,
          error: true,
          timestamp: new Date().toISOString(),
        };

        setMessages([...updatedMessages, errorAssistantMessage]);
      } finally {
        setIsLoading(false);
        abortControllerRef.current = null;
      }
    },
    [activeId, messages, isLoading, language, selectedDocumentIds]
  );

  const submitApproval = useCallback(
    async (messageId, approvalId, decision) => {
      if (!approvalId || !decision) return;
      setIsLoading(true);
      setError(null);

      try {
        const result = await decideApproval(approvalId, decision);
        const resumed = result.resumed_response;

        setMessages((prevMessages) => {
          return prevMessages.map((msg) => {
            if (
              msg.id === messageId ||
              (msg.pendingApproval && msg.pendingApproval.approval_id === approvalId)
            ) {
              return {
                ...msg,
                pendingApproval: null,
                content:
                  resumed?.reply ||
                  (decision === "approve"
                    ? "Action authorized and completed."
                    : "Action declined."),
                intent: resumed?.intent || msg.intent,
                grounded: resumed?.grounded ?? msg.grounded,
                sources: [...(msg.sources || []), ...(resumed?.sources || [])],
                toolActivity: [...(msg.toolActivity || []), ...(resumed?.toolActivity || [])],
                latencyMs: resumed?.latency_ms || msg.latencyMs,
                tokenUsage: resumed?.token_usage || msg.tokenUsage,
                warnings: [...(msg.warnings || []), ...(resumed?.warnings || [])],
                grievances: [...(msg.grievances || []), ...(resumed?.grievances || [])],
                browserSessions: [
                  ...(msg.browserSessions || []),
                  ...(resumed?.browser_sessions || []),
                ],
              };
            }
            return msg;
          });
        });
      } catch (err) {
        const errorMsg = err?.message || "Failed to submit authorization decision.";
        setError(errorMsg);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const retryLastMessage = useCallback(() => {
    const lastUserIdx = messages.map((m) => m.role).lastIndexOf("user");
    if (lastUserIdx >= 0) {
      const lastUserText = messages[lastUserIdx].content;
      const cleanedMessages = messages.slice(0, lastUserIdx);
      setMessages(cleanedMessages);
      sendMessage(lastUserText);
    }
  }, [messages, sendMessage]);

  const clearMessages = useCallback(() => {
    if (activeId) {
      deleteChat(activeId);
    } else {
      setMessages([]);
      setError(null);
    }
  }, [activeId, deleteChat]);

  // Migration action for localStorage conversations
  const migrateLocalConversations = useCallback(async () => {
    const localConvs = getStoredConversations();
    if (localConvs.length === 0) {
      localStorage.setItem("civiclens_conversations_migrated", "true");
      setUnmigratedCount(0);
      return 0;
    }

    setIsMigrating(true);
    try {
      const payload = localConvs.map((c) => ({
        id: c.id,
        title: c.title || "Imported Conversation",
        language_setting: c.languageSetting || "auto",
        document_ids: c.selectedDocumentIds || [],
        created_at: c.createdAt || new Date().toISOString(),
        updated_at: c.updatedAt || new Date().toISOString(),
        messages: (c.messages || []).map((m) => ({
          role: m.role || "user",
          content: m.content || "",
          meta: {
            sources: m.sources,
            tool_activity: m.toolActivity,
            intent: m.intent,
            grounded: m.grounded,
            verifications: m.verifications,
            checklists: m.checklists,
            grievances: m.grievances,
            browser_sessions: m.browserSessions,
          },
          created_at: m.timestamp || new Date().toISOString(),
        })),
      }));

      const res = await importConversations(payload);
      localStorage.setItem("civiclens_conversations_migrated", "true");
      setUnmigratedCount(0);

      // Reload conversations list from backend
      const listRes = await listConversations({ limit: 50 });
      if (listRes && Array.isArray(listRes.items)) {
        setConversations(listRes.items);
      }
      return res?.imported_count || payload.length;
    } finally {
      setIsMigrating(false);
    }
  }, []);

  const dismissMigration = useCallback(() => {
    localStorage.setItem("civiclens_conversations_migrated", "true");
    setUnmigratedCount(0);
  }, []);

  return {
    conversations,
    activeId,
    messages,
    isLoading,
    error,
    language,
    setLanguage,
    selectedDocumentIds,
    setSelectedDocumentIds,
    toggleDocumentId,
    sendMessage,
    submitApproval,
    retryLastMessage,
    stopGeneration,
    startNewChat,
    switchConversation,
    deleteChat,
    renameChat,
    clearMessages,
    unmigratedCount,
    isMigrating,
    migrateLocalConversations,
    dismissMigration,
  };
}