import { useState, useEffect, useCallback, useRef } from "react";
import { getSystemStatus, getSystemStats, runBackup, runMaintenance } from "../services/systemService";

export function useSystemStatus(autoPoll = false) {
  const [status, setStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const pollTimerRef = useRef(null);

  const fetchStatusAndStats = useCallback(async () => {
    try {
      const [statusRes, statsRes] = await Promise.all([
        getSystemStatus(),
        getSystemStats().catch(() => null),
      ]);
      setStatus(statusRes);
      if (statsRes) setStats(statsRes);
      setError(null);
      return statusRes;
    } catch (err) {
      console.warn("Failed to fetch system status", err);
      setError(err?.message || "Could not retrieve system status.");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatusAndStats();

    if (autoPoll) {
      pollTimerRef.current = setInterval(() => {
        fetchStatusAndStats();
      }, 15000);
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [autoPoll, fetchStatusAndStats]);

  const triggerBackup = useCallback(async () => {
    const res = await runBackup();
    await fetchStatusAndStats();
    return res;
  }, [fetchStatusAndStats]);

  const triggerMaintenance = useCallback(async (options = {}) => {
    const res = await runMaintenance(options);
    await fetchStatusAndStats();
    return res;
  }, [fetchStatusAndStats]);

  return {
    status,
    stats,
    isLoading,
    error,
    refetch: fetchStatusAndStats,
    triggerBackup,
    triggerMaintenance,
  };
}
