import { useState, useCallback, useEffect } from "react";

const STORAGE_KEY = "prompt_history";
const MAX_ITEMS = 20;

interface UsePromptHistoryReturn {
  history: string[];
  addToHistory: (prompt: string) => void;
  clearHistory: () => void;
}

export function usePromptHistory(): UsePromptHistoryReturn {
  const [history, setHistory] = useState<string[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setHistory(parsed);
        }
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  const addToHistory = useCallback((prompt: string) => {
    setHistory((prev) => {
      // Deduplicate: remove any existing identical prompt
      const filtered = prev.filter((p) => p !== prompt);
      // Prepend the new prompt and cap at MAX_ITEMS
      const updated = [prompt, ...filtered].slice(0, MAX_ITEMS);

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch {
        // quota exceeded or other storage error
      }

      return updated;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  return { history, addToHistory, clearHistory };
}
