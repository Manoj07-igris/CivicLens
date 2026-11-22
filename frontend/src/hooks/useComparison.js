/**
 * Hook for managing policy document comparison lifecycle and polling.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { comparisonService } from "../services/comparisonService";

export function useComparison() {
  const [comparison, setComparison] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | queued | running | completed | failed
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);

  const activeIdRef = useRef(null);
  const pollTimerRef = useRef(null);
  const pollStatusRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const pollStatus = useCallback(async (id) => {
    if (!id || activeIdRef.current !== id) return;

    try {
      const data = await comparisonService.getComparison(id);
      if (activeIdRef.current !== id) return;

      const currentStatus = data.status || "idle";
      setStatus(currentStatus);
      setProgress(data.progress ?? (currentStatus === "completed" ? 100 : 0));
      setCurrentStep(data.current_step || "");

      if (currentStatus === "completed") {
        setComparison(data);
        setError(null);
        setLoading(false);
        stopPolling();
      } else if (currentStatus === "failed") {
        setComparison(data);
        setError(data.error_message || "Comparison failed.");
        setLoading(false);
        stopPolling();
      } else {
        // Continue polling every 2 seconds via ref to avoid circular callback initialization
        pollTimerRef.current = setTimeout(() => {
          if (pollStatusRef.current) {
            pollStatusRef.current(id);
          }
        }, 2000);
      }
    } catch (err) {
      if (activeIdRef.current === id) {
        setError(err.message || "Failed to fetch comparison status.");
        setLoading(false);
        stopPolling();
      }
    }
  }, [stopPolling]);

  useEffect(() => {
    pollStatusRef.current = pollStatus;
  }, [pollStatus]);

  const start = useCallback(async ({ oldDocumentId, newDocumentId, language = "auto", force = false }) => {
    stopPolling();
    setError(null);
    setLoading(true);
    setStatus("queued");
    setProgress(5);
    setCurrentStep("Initializing comparison...");

    try {
      const job = await comparisonService.startComparison({
        oldDocumentId,
        newDocumentId,
        language,
        force,
      });

      const compId = job.comparison_id;
      activeIdRef.current = compId;

      if (job.status === "completed") {
        // Was returned immediately from cache
        setStatus("completed");
        setProgress(100);
        setCurrentStep("Completed (cached)");
        setComparison(job);
        setLoading(false);
        return job;
      }

      setStatus(job.status || "running");
      setProgress(job.progress || 15);
      setCurrentStep(job.current_step || "Analyzing documents...");
      setIsPolling(true);

      // Start polling
      pollTimerRef.current = setTimeout(() => {
        pollStatus(compId);
      }, 1500);

      return job;
    } catch (err) {
      setError(err.message || "Failed to start comparison.");
      setStatus("failed");
      setLoading(false);
      throw err;
    }
  }, [stopPolling, pollStatus]);

  const fetchById = useCallback(async (id) => {
    if (!id) return;
    stopPolling();
    setError(null);
    setLoading(true);
    activeIdRef.current = id;

    try {
      const data = await comparisonService.getComparison(id);
      setStatus(data.status);
      setProgress(data.progress ?? (data.status === "completed" ? 100 : 0));
      setCurrentStep(data.current_step || "");
      setComparison(data);

      if (data.status === "queued" || data.status === "running") {
        setIsPolling(true);
        pollTimerRef.current = setTimeout(() => {
          pollStatus(id);
        }, 2000);
      } else {
        setLoading(false);
      }
      return data;
    } catch (err) {
      setError(err.message || "Failed to load comparison.");
      setStatus("failed");
      setLoading(false);
      throw err;
    }
  }, [stopPolling, pollStatus]);

  const retry = useCallback(async (id) => {
    const targetId = id || activeIdRef.current;
    if (!targetId) return;

    stopPolling();
    setError(null);
    setLoading(true);
    setStatus("running");
    setProgress(50);
    setCurrentStep("Retrying AI analysis...");
    activeIdRef.current = targetId;

    try {
      const data = await comparisonService.retryAnalysis(targetId);
      if (data.status === "completed") {
        setComparison(data);
        setStatus("completed");
        setProgress(100);
        setLoading(false);
      } else {
        setIsPolling(true);
        pollTimerRef.current = setTimeout(() => {
          pollStatus(targetId);
        }, 2000);
      }
      return data;
    } catch (err) {
      setError(err.message || "Failed to retry AI analysis.");
      setStatus("failed");
      setLoading(false);
      throw err;
    }
  }, [stopPolling, pollStatus]);

  const clear = useCallback(() => {
    stopPolling();
    activeIdRef.current = null;
    setComparison(null);
    setStatus("idle");
    setProgress(0);
    setCurrentStep("");
    setError(null);
    setLoading(false);
  }, [stopPolling]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  return {
    comparison,
    status,
    progress,
    currentStep,
    error,
    loading,
    isPolling,
    startComparison: start,
    fetchComparison: fetchById,
    retryAnalysis: retry,
    clearComparison: clear,
  };
}
