/**
 * Hook for managing fact verification lifecycle, polling, and results.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { verificationService } from "../services/verificationService";

export function useVerification() {
  const [report, setReport] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | queued | running | completed | completed_with_warnings | failed
  const [stage, setStage] = useState("");
  const [progressPct, setProgressPct] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [pastVerifications, setPastVerifications] = useState([]);
  const [activeId, setActiveId] = useState(null);

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

  const refreshPastList = useCallback(async () => {
    try {
      const data = await verificationService.listVerifications(30);
      setPastVerifications(data.verifications || []);
    } catch {
      // Non-critical, past list will remain as is
    }
  }, []);

  const pollStatus = useCallback(
    async (id) => {
      if (!id || activeIdRef.current !== id) return;

      try {
        const data = await verificationService.getVerificationStatus(id);
        if (activeIdRef.current !== id) return;

        const currentStatus = data.status || "idle";
        setStatus(currentStatus);
        setStage(data.stage || "");
        setProgressPct(data.progress_pct ?? (currentStatus === "completed" ? 100 : 0));

        if (currentStatus === "completed" || currentStatus === "completed_with_warnings") {
          setReport(data.report);
          setError(null);
          setLoading(false);
          stopPolling();
          refreshPastList();
        } else if (currentStatus === "failed") {
          setReport(data.report || null);
          setError(data.error_message || "Fact verification failed.");
          setLoading(false);
          stopPolling();
          refreshPastList();
        } else {
          // Continue polling every 2 seconds
          pollTimerRef.current = setTimeout(() => {
            if (pollStatusRef.current) {
              pollStatusRef.current(id);
            }
          }, 2000);
        }
      } catch (err) {
        if (activeIdRef.current === id) {
          setError(err.message || "Failed to fetch verification status.");
          setLoading(false);
          stopPolling();
        }
      }
    },
    [stopPolling, refreshPastList]
  );

  useEffect(() => {
    pollStatusRef.current = pollStatus;
  }, [pollStatus]);

  useEffect(() => {
    let active = true;
    verificationService
      .listVerifications(30)
      .then((data) => {
        if (active) setPastVerifications(data.verifications || []);
      })
      .catch(() => {});

    return () => {
      active = false;
      stopPolling();
    };
  }, [stopPolling]);

  const startVerification = useCallback(
    async ({ claim, language = "auto", scope = "official", documentIds = [], force = false }) => {
      stopPolling();
      setError(null);
      setLoading(true);
      setStatus("queued");
      setStage("understanding_claim");
      setProgressPct(10);
      setReport(null);

      try {
        const job = await verificationService.submitVerification({
          claim,
          language,
          scope,
          documentIds,
          force,
        });

        activeIdRef.current = job.verification_id;
        setActiveId(job.verification_id);

        if (job.status === "completed" || job.status === "completed_with_warnings") {
          // Cache hit or instant completion
          const fullData = await verificationService.getVerificationStatus(job.verification_id);
          setStatus(fullData.status);
          setProgressPct(100);
          setReport(fullData.report);
          setLoading(false);
          refreshPastList();
        } else {
          setIsPolling(true);
          pollTimerRef.current = setTimeout(() => {
            pollStatus(job.verification_id);
          }, 1200);
        }

        return job.verification_id;
      } catch (err) {
        setError(err.message || "Failed to start fact verification.");
        setStatus("failed");
        setLoading(false);
        throw err;
      }
    },
    [stopPolling, pollStatus, refreshPastList]
  );

  const loadVerification = useCallback(
    async (id) => {
      if (!id) return;
      stopPolling();
      setError(null);
      setLoading(true);
      activeIdRef.current = id;
      setActiveId(id);

      try {
        const data = await verificationService.getVerificationStatus(id);
        setStatus(data.status);
        setStage(data.stage || "");
        setProgressPct(data.progress_pct ?? 0);
        setReport(data.report);
        setLoading(false);

        if (data.status === "queued" || data.status === "running") {
          setIsPolling(true);
          pollTimerRef.current = setTimeout(() => {
            pollStatus(id);
          }, 1500);
        }
      } catch (err) {
        setError(err.message || "Failed to load verification.");
        setStatus("failed");
        setLoading(false);
      }
    },
    [stopPolling, pollStatus]
  );

  const retryAnalysis = useCallback(
    async (id) => {
      const targetId = id || activeIdRef.current;
      if (!targetId) return;

      stopPolling();
      setError(null);
      setLoading(true);
      setStatus("running");
      setStage("analysing_evidence");
      setProgressPct(60);

      try {
        await verificationService.retryAnalysis(targetId);
        activeIdRef.current = targetId;
        setActiveId(targetId);
        setIsPolling(true);
        pollTimerRef.current = setTimeout(() => {
          pollStatus(targetId);
        }, 1200);
      } catch (err) {
        setError(err.message || "Failed to retry analysis.");
        setLoading(false);
      }
    },
    [stopPolling, pollStatus]
  );

  const removeVerification = useCallback(
    async (id) => {
      if (!id) return;
      try {
        await verificationService.deleteVerification(id);
        if (activeIdRef.current === id) {
          stopPolling();
          setReport(null);
          setStatus("idle");
          setProgressPct(0);
        }
        await refreshPastList();
      } catch (err) {
        setError(err.message || "Failed to delete verification.");
      }
    },
    [stopPolling, refreshPastList]
  );

  const reset = useCallback(() => {
    stopPolling();
    activeIdRef.current = null;
    setActiveId(null);
    setReport(null);
    setStatus("idle");
    setStage("");
    setProgressPct(0);
    setError(null);
    setLoading(false);
  }, [stopPolling]);

  return {
    report,
    status,
    stage,
    progressPct,
    error,
    loading,
    isPolling,
    pastVerifications,
    activeId,
    startVerification,
    loadVerification,
    retryAnalysis,
    removeVerification,
    refreshPastList,
    reset,
  };
}
