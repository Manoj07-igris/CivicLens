/**
 * CivicLens Document Intelligence Service
 * Interacts with backend /api/v1/documents endpoints for PDF upload,
 * processing lifecycle polling, page-level text extraction, and AI summarization.
 */

import { apiClient } from "./apiClient";

const getBaseUrl = () => {
  const envUrl = import.meta.env?.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === "string" && envUrl.trim()) {
    return envUrl.replace(/\/+$/, "");
  }
  return "http://localhost:8000";
};

export const documentService = {
  /**
   * Check system PDF processing limits and OCR capabilities.
   */
  async getCapabilities() {
    return apiClient.get("/api/v1/documents/capabilities");
  },

  /**
   * Upload an official government PDF.
   * Returns DocumentUploadResponse with 202 (processing started) or 200 (duplicate found).
   */
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append("file", file, file.name);
    return apiClient.upload("/api/v1/documents/upload", formData, {
      timeout: 60000, // 60s timeout for large uploads
    });
  },

  /**
   * Retrieve list of all uploaded documents, sorted newest first.
   */
  async getDocuments() {
    return apiClient.get("/api/v1/documents");
  },

  /**
   * Retrieve detailed metadata, page summaries, and chunk count for a document.
   */
  async getDocument(documentId) {
    return apiClient.get(`/api/v1/documents/${documentId}`);
  },

  /**
   * Retrieve paginated extracted pages with full text and extraction method.
   */
  async getDocumentPages(documentId, page = 1, pageSize = 20) {
    return apiClient.get(
      `/api/v1/documents/${documentId}/pages?page=${page}&page_size=${pageSize}`
    );
  },

  /**
   * Retrieve single extracted page.
   */
  async getDocumentPage(documentId, pageNumber) {
    return apiClient.get(`/api/v1/documents/${documentId}/pages/${pageNumber}`);
  },

  /**
   * Generate an AI civic summary of the document, cached per document & language.
   */
  async generateSummary(documentId, language = "auto") {
    return apiClient.post(`/api/v1/documents/${documentId}/summary`, {
      language,
    });
  },

  /**
   * Permanently delete a document and its stored artifacts.
   */
  async deleteDocument(documentId) {
    return apiClient.delete(`/api/v1/documents/${documentId}`);
  },

  /**
   * Explicitly trigger FAISS vector index creation or recreation.
   */
  async buildIndex(documentId, force = false) {
    return apiClient.post(`/api/v1/documents/${documentId}/index`, {
      force,
    });
  },

  /**
   * Retrieve ranked passages for a search query using hybrid vector + lexical scoring.
   */
  async retrievePassages(documentId, query, topK = 6) {
    return apiClient.post(`/api/v1/documents/${documentId}/retrieve`, {
      query,
      top_k: topK,
    });
  },

  /**
   * Ask an evidence-grounded question about an uploaded policy document.
   * Returns GroundedAnswer with verified citations and evidence levels.
   */
  async askDocument(documentId, question, language = "auto", history = []) {
    return apiClient.post(
      `/api/v1/documents/${documentId}/ask`,
      {
        question,
        language,
        history,
      },
      {
        timeout: 60000, // 60s timeout in case index is lazily built on first question
      }
    );
  },

  /**
   * Build direct URL to stream the original PDF with inline Content-Disposition.
   */
  getOriginalFileUrl(documentId) {
    return `${getBaseUrl()}/api/v1/documents/${documentId}/file`;
  },
};
