/**
 * Hook for managing single grievance lifecycle: analysis, polling, draft editing,
 * photo observation confirmation, demo registration, and simulation advancement.
 */
import { useState, useRef, useCallback, useEffect } from "react";
import { grievanceService } from "../services/grievanceService";

export function useGrievance() {
  const [grievance, setGrievance] = useState(null);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isPolling, setIsPolling] = useState(false);

  const activeIdRef = useRef(null);
  const pollTimerRef = useRef(null);
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const pollStatus = useCallback(
    async (id) => {
      if (!id || activeIdRef.current !== id) return;

      try {
        const data = await grievanceService.getGrievance(id);
        if (activeIdRef.current !== id) return;

        if (data.record) {
          setGrievance(data.record);
        }
        if (data.job) {
          setJob(data.job);
        }

        const jobStatus = data.job?.status;
        if (!jobStatus || jobStatus === "completed") {
          setLoading(false);
          stopPolling();
          if (data.job?.error_message) {
            setError(data.job.error_message);
          }
        } else if (jobStatus === "failed") {
          setLoading(false);
          setError(data.job?.error_message || "Grievance analysis failed.");
          stopPolling();
        } else {
          // Continue polling while queued or running
          pollTimerRef.current = setTimeout(() => {
            if (pollRef.current) {
              pollRef.current(id);
            }
          }, 1500);
        }
      } catch (err) {
        if (activeIdRef.current === id) {
          setError(err.message || "Failed to check grievance analysis progress.");
          setLoading(false);
          stopPolling();
        }
      }
    },
    [stopPolling]
  );

  useEffect(() => {
    pollRef.current = pollStatus;
  }, [pollStatus]);

  useEffect(() => {
    return () => {
      stopPolling();
    };
  }, [stopPolling]);

  const loadGrievance = useCallback(
    async (id) => {
      if (!id) return;
      stopPolling();
      activeIdRef.current = id;
      setLoading(true);
      setError(null);

      try {
        const data = await grievanceService.getGrievance(id);
        if (activeIdRef.current !== id) return;
        setGrievance(data.record || null);
        setJob(data.job || null);

        if (data.job && (data.job.status === "queued" || data.job.status === "running")) {
          setIsPolling(true);
          pollStatus(id);
        } else {
          setLoading(false);
        }
      } catch (err) {
        if (activeIdRef.current === id) {
          setError(err.message || "Could not load grievance record.");
          setLoading(false);
        }
      }
    },
    [pollStatus, stopPolling]
  );

  const startAnalysis = useCallback(
    async (payload) => {
      stopPolling();
      setLoading(true);
      setError(null);
      setGrievance(null);
      setJob(null);

      try {
        const res = await grievanceService.analyzeGrievance(payload);
        const gid = res.id;
        activeIdRef.current = gid;
        setGrievance(res);
        setLoading(false);
        return res;
      } catch (err) {
        setError(err.message || "Failed to analyze grievance.");
        setLoading(false);
        throw err;
      }
    },
    [stopPolling]
  );

  const patchDraft = useCallback(
    async (patch) => {
      if (!grievance?.id) return;
      setLoading(true);
      setError(null);

      try {
        const updated = await grievanceService.patchGrievance(grievance.id, patch);
        setGrievance(updated);
        setLoading(false);
        return updated;
      } catch (err) {
        setError(err.message || "Failed to update complaint draft.");
        setLoading(false);
        throw err;
      }
    },
    [grievance]
  );

  const toggleObservation = useCallback(
    async (obsId, confirmed) => {
      if (!grievance?.draft) return;
      const currentObs = grievance.draft.observations || [];
      const confirmedIds = currentObs
        .filter((o) => (o.item_id === obsId ? confirmed : o.confirmed))
        .map((o) => o.item_id);

      return patchDraft({
        confirmed_observation_ids: confirmedIds,
      });
    },
    [grievance, patchDraft]
  );

  const registerDemo = useCallback(
    async (approvedHash) => {
      if (!grievance?.id) return;
      setLoading(true);
      setError(null);

      try {
        const updated = await grievanceService.registerDemo(grievance.id, {
          approved: true,
          approved_hash: approvedHash || grievance.draft_hash,
        });
        setGrievance(updated);
        setLoading(false);
        return updated;
      } catch (err) {
        setError(err.message || "Failed to register demo complaint.");
        setLoading(false);
        throw err;
      }
    },
    [grievance]
  );

  const advanceDemoStatus = useCallback(
    async (note = "") => {
      if (!grievance?.id) return;
      setLoading(true);
      setError(null);

      try {
        const updated = await grievanceService.advanceDemoStatus(grievance.id, { note });
        setGrievance(updated);
        setLoading(false);
        return updated;
      } catch (err) {
        setError(err.message || "Failed to advance demo status.");
        setLoading(false);
        throw err;
      }
    },
    [grievance]
  );

  const retryAnalysis = useCallback(
    async (payload) => {
      if (!grievance?.id) return;
      setLoading(true);
      setError(null);

      try {
        const updated = await grievanceService.retryAnalysis(grievance.id, payload);
        setGrievance(updated);
        setLoading(false);
        return updated;
      } catch (err) {
        setError(err.message || "Failed to re-run grievance analysis.");
        setLoading(false);
        throw err;
      }
    },
    [grievance]
  );

  const deleteActiveGrievance = useCallback(async () => {
    if (!grievance?.id) return;
    setLoading(true);
    try {
      await grievanceService.deleteGrievance(grievance.id);
      setGrievance(null);
      setJob(null);
      setLoading(false);
    } catch (err) {
      setError(err.message || "Failed to delete grievance record.");
      setLoading(false);
      throw err;
    }
  }, [grievance]);

  const reset = useCallback(() => {
    stopPolling();
    activeIdRef.current = null;
    setGrievance(null);
    setJob(null);
    setError(null);
    setLoading(false);
  }, [stopPolling]);

  return {
    grievance,
    job,
    loading,
    error,
    isPolling,
    loadGrievance,
    startAnalysis,
    patchDraft,
    toggleObservation,
    registerDemo,
    advanceDemoStatus,
    retryAnalysis,
    deleteActiveGrievance,
    reset,
  };
}

export default useGrievance;
