/**
 * Hook for managing Playwright Browser Automation demo sessions.
 */

import { useState, useCallback, useEffect } from "react";
import { browserService } from "../services/browserService";

export function useBrowserSession() {
  const [session, setSession] = useState(null);
  const [manifest, setManifest] = useState(null);
  const [capabilities, setCapabilities] = useState(null);
  const [pastSessions, setPastSessions] = useState([]);
  const [preview, setPreview] = useState(null);
  const [submissionResult, setSubmissionResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isActing, setIsActing] = useState(false);
  const [error, setError] = useState(null);
  const [piiError, setPiiError] = useState(null);

  // Load manifest and capabilities on mount
  const loadInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [man, cap, past] = await Promise.all([
        browserService.getManifest().catch(() => null),
        browserService.getCapabilities().catch(() => null),
        browserService.listSessions(10).catch(() => []),
      ]);
      if (man) setManifest(man);
      if (cap) setCapabilities(cap);
      if (past) setPastSessions(past);
    } catch (err) {
      setError(err?.message || "Failed to load browser automation settings.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Refresh past sessions
  const refreshPastSessions = useCallback(async () => {
    try {
      const list = await browserService.listSessions(10);
      setPastSessions(list || []);
    } catch {
      // Background non-critical
    }
  }, []);

  // Start new demo session
  const startSession = useCallback(
    async ({ portalId = "prt_demo_portal", lang = "en" } = {}) => {
      setIsActing(true);
      setError(null);
      setPiiError(null);
      setPreview(null);
      setSubmissionResult(null);
      try {
        const newSession = await browserService.createSession({ portalId, lang });
        setSession(newSession);
        refreshPastSessions();
        return newSession;
      } catch (err) {
        setError(err?.message || "Could not launch demo browser session.");
        return null;
      } finally {
        setIsActing(false);
      }
    },
    [refreshPastSessions]
  );

  // Fill form step
  const fillStep = useCallback(
    async (stepIndex, values, fictionalConfirmed = true) => {
      if (!session?.session_id) return null;
      setIsActing(true);
      setError(null);
      setPiiError(null);
      try {
        const updated = await browserService.fillStep(
          session.session_id,
          stepIndex,
          values,
          fictionalConfirmed
        );
        setSession(updated);
        return updated;
      } catch (err) {
        if (err?.code === "PII_DETECTED" || err?.status === 422) {
          setPiiError(
            err?.message ||
              "Personal identifiers detected. Please remove any real Aadhaar, PAN, or phone numbers."
          );
        } else {
          setError(err?.message || `Failed to fill step ${stepIndex}.`);
        }
        return null;
      } finally {
        setIsActing(false);
      }
    },
    [session]
  );

  // Advance to next step
  const nextStep = useCallback(async () => {
    if (!session?.session_id) return null;
    setIsActing(true);
    setError(null);
    setPiiError(null);
    try {
      const updated = await browserService.navigateNext(session.session_id);
      setSession(updated);
      return updated;
    } catch (err) {
      setError(err?.message || "Failed to navigate to next step.");
      return null;
    } finally {
      setIsActing(false);
    }
  }, [session]);

  // Return to previous step
  const prevStep = useCallback(async () => {
    if (!session?.session_id) return null;
    setIsActing(true);
    setError(null);
    setPiiError(null);
    try {
      const updated = await browserService.navigateBack(session.session_id);
      setSession(updated);
      return updated;
    } catch (err) {
      setError(err?.message || "Failed to navigate to previous step.");
      return null;
    } finally {
      setIsActing(false);
    }
  }, [session]);

  // Load review preview and canonical hash
  const loadPreview = useCallback(async () => {
    if (!session?.session_id) return null;
    setIsActing(true);
    setError(null);
    try {
      const p = await browserService.getReviewPreview(session.session_id);
      setPreview(p);
      return p;
    } catch (err) {
      setError(err?.message || "Failed to generate review preview.");
      return null;
    } finally {
      setIsActing(false);
    }
  }, [session]);

  // Submit demo application
  const submitDemo = useCallback(
    async (reviewHash, fictionalConfirmed = true) => {
      if (!session?.session_id) return null;
      setIsActing(true);
      setError(null);
      setPiiError(null);
      try {
        const res = await browserService.submitDemo(
          session.session_id,
          reviewHash,
          fictionalConfirmed
        );
        setSubmissionResult(res);
        refreshPastSessions();
        return res;
      } catch (err) {
        setError(err?.message || "Failed to submit demo application.");
        return null;
      } finally {
        setIsActing(false);
      }
    },
    [session, refreshPastSessions]
  );

  // Close demo session
  const closeSession = useCallback(async () => {
    if (!session?.session_id) return;
    try {
      await browserService.closeSession(session.session_id);
      setSession(null);
      setPreview(null);
      setSubmissionResult(null);
      refreshPastSessions();
    } catch {
      setSession(null);
    }
  }, [session, refreshPastSessions]);

  // Reset to initial state
  const resetSession = useCallback(() => {
    setSession(null);
    setPreview(null);
    setSubmissionResult(null);
    setError(null);
    setPiiError(null);
  }, []);

  return {
    session,
    manifest,
    capabilities,
    pastSessions,
    preview,
    submissionResult,
    isLoading,
    isActing,
    error,
    piiError,
    startSession,
    fillStep,
    nextStep,
    prevStep,
    loadPreview,
    submitDemo,
    closeSession,
    resetSession,
    refreshPastSessions,
  };
}

export default useBrowserSession;
