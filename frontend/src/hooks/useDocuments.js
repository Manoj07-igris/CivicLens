import { useState, useEffect, useCallback, useRef } from "react";
import { documentService } from "../services/documentService";
import { useToast } from "./useToast";

export function useDocuments() {
  const [documents, setDocuments] = useState([]);
  const [capabilities, setCapabilities] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const { addToast } = useToast();

  const pollingRef = useRef(null);

  const fetchCapabilities = useCallback(async () => {
    try {
      const caps = await documentService.getCapabilities();
      setCapabilities(caps);
    } catch (err) {
      console.warn("Failed to fetch document capabilities:", err);
    }
  }, []);

  const fetchDocuments = useCallback(async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    try {
      const docs = await documentService.getDocuments();
      setDocuments(docs || []);
      setError(null);
      return docs;
    } catch (err) {
      console.error("Failed to fetch documents:", err);
      setError(err.message || "Failed to load documents.");
      return [];
    } finally {
      if (showLoading) setIsLoading(false);
    }
  }, []);

  // Check if any document is currently in an active processing state
  const hasActiveProcessing = documents.some(
    (d) => d.status === "uploaded" || d.status === "processing"
  );

  // Set up polling when there are active processing tasks
  useEffect(() => {
    if (hasActiveProcessing) {
      if (!pollingRef.current) {
        pollingRef.current = setInterval(async () => {
          const updated = await fetchDocuments(false);
          const stillProcessing = updated.some(
            (d) => d.status === "uploaded" || d.status === "processing"
          );
          if (!stillProcessing && pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }, 2500);
      }
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [hasActiveProcessing, fetchDocuments]);

  // Initial concurrent load
  useEffect(() => {
    let isMounted = true;
    const init = async () => {
      try {
        const [caps, docs] = await Promise.all([
          documentService.getCapabilities().catch(() => null),
          documentService.getDocuments().catch(() => []),
        ]);
        if (isMounted) {
          if (caps) setCapabilities(caps);
          setDocuments(docs || []);
          setIsLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || "Failed to load documents.");
          setIsLoading(false);
        }
      }
    };
    init();
    return () => {
      isMounted = false;
    };
  }, []);

  const uploadFile = useCallback(
    async (file) => {
      setIsUploading(true);
      setError(null);
      try {
        const res = await documentService.uploadDocument(file);
        if (res.is_duplicate) {
          addToast({
            message: `Document already exists (${res.filename}). Displaying existing record.`,
            type: "info",
            duration: 5000,
          });
        } else {
          addToast({
            message: `"${res.filename}" uploaded successfully. Text extraction started.`,
            type: "success",
            duration: 4000,
          });
        }
        await fetchDocuments(false);
        return res;
      } catch (err) {
        const errMsg = err.message || "Failed to upload document.";
        setError(errMsg);
        addToast({
          message: errMsg,
          type: "error",
          duration: 6000,
        });
        throw err;
      } finally {
        setIsUploading(false);
      }
    },
    [addToast, fetchDocuments]
  );

  const deleteDoc = useCallback(
    async (documentId, filename = "document") => {
      try {
        await documentService.deleteDocument(documentId);
        setDocuments((prev) => prev.filter((d) => d.document_id !== documentId));
        addToast({
          message: `"${filename}" deleted successfully.`,
          type: "success",
          duration: 3500,
        });
      } catch (err) {
        const errMsg = err.message || "Failed to delete document.";
        addToast({
          message: errMsg,
          type: "error",
          duration: 5000,
        });
        throw err;
      }
    },
    [addToast]
  );

  return {
    documents,
    capabilities,
    isLoading,
    isUploading,
    error,
    refresh: () => fetchDocuments(true),
    uploadFile,
    deleteDoc,
    fetchCapabilities,
  };
}
