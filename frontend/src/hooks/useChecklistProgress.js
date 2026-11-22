/**
 * Hook for managing citizen checklist progress locally in the browser.
 * Privacy guarantee: Checkbox states are stored exclusively in localStorage
 * and never transmitted to the server.
 */

import { useState, useEffect, useCallback, useMemo } from "react";

export function useChecklistProgress(guideId, totalItemsCount = 0) {
  const storageKey = useMemo(
    () => (guideId ? `civiclens_checklist_${guideId}` : null),
    [guideId]
  );

  // Initialize checked IDs from localStorage
  const [checkedIds, setCheckedIds] = useState(() => {
    if (!storageKey) return new Set();
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          return new Set(parsed);
        }
      }
    } catch {
      // Ignore local storage parse errors
    }
    return new Set();
  });

  // Re-read when guideId changes
  useEffect(() => {
    if (!storageKey) {
      setCheckedIds(new Set());
      return;
    }
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setCheckedIds(new Set(parsed));
          return;
        }
      }
    } catch {
      // Ignore
    }
    setCheckedIds(new Set());
  }, [storageKey]);

  // Persist to localStorage
  const persist = useCallback(
    (newSet) => {
      if (!storageKey) return;
      try {
        localStorage.setItem(storageKey, JSON.stringify(Array.from(newSet)));
      } catch {
        // Storage quota exceeded or disabled
      }
    },
    [storageKey]
  );

  const toggleItem = useCallback(
    (itemId) => {
      setCheckedIds((prev) => {
        const next = new Set(prev);
        if (next.has(itemId)) {
          next.delete(itemId);
        } else {
          next.add(itemId);
        }
        persist(next);
        return next;
      });
    },
    [persist]
  );

  const isChecked = useCallback(
    (itemId) => checkedIds.has(itemId),
    [checkedIds]
  );

  const resetProgress = useCallback(() => {
    const empty = new Set();
    setCheckedIds(empty);
    persist(empty);
  }, [persist]);

  const checkedCount = checkedIds.size;
  const progressPct =
    totalItemsCount > 0 ? Math.round((checkedCount / totalItemsCount) * 100) : 0;

  return {
    checkedIds,
    isChecked,
    toggleItem,
    resetProgress,
    checkedCount,
    progressPct,
  };
}
