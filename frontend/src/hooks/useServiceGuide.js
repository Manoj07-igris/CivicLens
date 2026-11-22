/**
 * Hook for managing public service guidance reports, checklists, and history.
 */

import { useState, useCallback, useEffect } from "react";
import { servicesService } from "../services/servicesService";

export function useServiceGuide(initialGuideId = null) {
  const [guide, setGuide] = useState(null);
  const [pastGuides, setPastGuides] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [piiError, setPiiError] = useState(null);

  // Fetch past guides list
  const fetchPastGuides = useCallback(async (limit = 20) => {
    try {
      const res = await servicesService.listGuides(limit);
      setPastGuides(res.guides || []);
    } catch {
      // Non-critical background failure
    }
  }, []);

  // Fetch specific guide by ID
  const fetchGuide = useCallback(async (guideId) => {
    if (!guideId) return null;
    setIsLoading(true);
    setError(null);
    setPiiError(null);
    try {
      const res = await servicesService.getGuide(guideId);
      setGuide(res);
      return res;
    } catch (err) {
      setError(err?.message || "Failed to load public service guide.");
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Generate a new guide
  const generateGuide = useCallback(
    async (params) => {
      setIsGenerating(true);
      setError(null);
      setPiiError(null);
      try {
        const res = await servicesService.generateGuide(params);
        setGuide(res);
        // Refresh history list
        fetchPastGuides();
        return res;
      } catch (err) {
        if (err?.code === "PII_DETECTED" || err?.status === 422) {
          setPiiError(
            err?.message ||
              "Personal identifiers detected in your query. For privacy, please remove any Aadhaar, PAN, phone number, or account numbers."
          );
        } else {
          setError(err?.message || "Failed to generate service guidance.");
        }
        return null;
      } finally {
        setIsGenerating(false);
      }
    },
    [fetchPastGuides]
  );

  // Retry an existing guide analysis
  const retryGuide = useCallback(
    async (guideId) => {
      if (!guideId) return null;
      setIsGenerating(true);
      setError(null);
      try {
        const res = await servicesService.retryGuide(guideId);
        setGuide(res);
        fetchPastGuides();
        return res;
      } catch (err) {
        setError(err?.message || "Failed to re-analyze service guide.");
        return null;
      } finally {
        setIsGenerating(false);
      }
    },
    [fetchPastGuides]
  );

  // Clear active report
  const clearActiveGuide = useCallback(() => {
    setGuide(null);
    setError(null);
    setPiiError(null);
  }, []);

  // Load initial guide if provided
  useEffect(() => {
    if (initialGuideId) {
      fetchGuide(initialGuideId);
    }
  }, [initialGuideId, fetchGuide]);

  // Initial load of history
  useEffect(() => {
    fetchPastGuides();
  }, [fetchPastGuides]);

  return {
    guide,
    pastGuides,
    isLoading,
    isGenerating,
    error,
    piiError,
    generateGuide,
    fetchGuide,
    retryGuide,
    fetchPastGuides,
    clearActiveGuide,
  };
}
