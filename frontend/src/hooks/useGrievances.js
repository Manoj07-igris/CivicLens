/**
 * Hook for managing the list of all citizen grievances (drafts and simulated demo complaints).
 */
import { useState, useCallback, useEffect } from "react";
import { grievanceService } from "../services/grievanceService";

export function useGrievances() {
  const [grievances, setGrievances] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchGrievances = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await grievanceService.listGrievances();
      setGrievances(data.grievances || []);
    } catch (err) {
      setError(err.message || "Failed to load grievance records.");
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteGrievance = useCallback(async (id) => {
    try {
      await grievanceService.deleteGrievance(id);
      setGrievances((prev) => prev.filter((g) => g.id !== id));
    } catch (err) {
      setError(err.message || "Could not delete complaint.");
      throw err;
    }
  }, []);

  useEffect(() => {
    fetchGrievances();
  }, [fetchGrievances]);

  return {
    grievances,
    loading,
    error,
    refresh: fetchGrievances,
    deleteGrievance,
  };
}

export default useGrievances;
