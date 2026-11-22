import { useState, useEffect, useCallback, useRef } from "react";
import { getInfo, getHealth } from "../services/healthService";

const POLL_INTERVAL_MS = 30000;

export function useBackendStatus() {
  const [status, setStatus] = useState("checking");
  const [info, setInfo] = useState(null);
  const [health, setHealth] = useState(null);
  const [lastChecked, setLastChecked] = useState(null);
  const [error, setError] = useState(null);

  const isMountedRef = useRef(true);

  const fetchStatus = useCallback(async () => {
    try {
      const [healthData, infoData] = await Promise.all([
        getHealth({ timeout: 5000 }),
        getInfo({ timeout: 5000 }),
      ]);

      if (!isMountedRef.current) return;
      setHealth(healthData);
      setInfo(infoData);

      // Check if backend reports degraded database or service state
      if (healthData?.database === "degraded" || healthData?.status === "degraded") {
        setStatus("degraded");
        setError("Database degraded / migrating");
      } else {
        setStatus("online");
        setError(null);
      }
      setLastChecked(new Date());
    } catch (err) {
      if (!isMountedRef.current) return;
      setHealth(null);
      setInfo(null);
      setLastChecked(new Date());

      // Distinguish network unreachable from reachable-but-degraded/server error
      const isServerError =
        err?.status === 503 ||
        err?.code === "DATABASE_DEGRADED" ||
        (typeof err?.status === "number" && err.status >= 500 && err.status < 600);

      if (isServerError) {
        setStatus("degraded");
        setError(err?.message || "Database degraded / migrating");
      } else {
        setStatus("offline");
        setError(
          err?.message ||
            "Cannot reach the CivicLens backend server. Please verify the backend is running."
        );
      }
    }
  }, []);

  const retry = useCallback(() => {
    if (!isMountedRef.current) return;
    setStatus("checking");
    setError(null);
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    isMountedRef.current = true;
    // oxlint-disable-next-line react/set-state-in-effect
    fetchStatus();

    const intervalId = setInterval(() => {
      if (isMountedRef.current) {
        fetchStatus();
      }
    }, POLL_INTERVAL_MS);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchStatus]);

  return {
    status,
    isOnline: status === "online",
    isDegraded: status === "degraded",
    isOffline: status === "offline",
    isChecking: status === "checking",
    info,
    health,
    lastChecked,
    error,
    retry,
  };
}
