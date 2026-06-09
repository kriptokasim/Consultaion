interface StoredItem<T> {
  value: T;
  expiresAt: number;
}

/**
 * Store a value in localStorage with a TTL.
 * Safe for SSR (no-ops when window is undefined).
 */
export function setWithExpiry<T>(key: string, value: T, ttlMs: number): void {
  if (typeof window === "undefined") return;
  try {
    const item: StoredItem<T> = {
      value,
      expiresAt: Date.now() + ttlMs,
    };
    window.localStorage.setItem(key, JSON.stringify(item));
  } catch {
    // localStorage full or blocked — fail silently
  }
}

/**
 * Retrieve a value from localStorage, returning null if expired or missing.
 * Safe for SSR.
 */
export function getWithExpiry<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const item: StoredItem<T> = JSON.parse(raw);
    if (Date.now() > item.expiresAt) {
      window.localStorage.removeItem(key);
      return null;
    }
    return item.value;
  } catch {
    // Corrupted entry — remove it
    try { window.localStorage.removeItem(key); } catch { /* ignore */ }
    return null;
  }
}

/**
 * Remove all expired keys matching an optional prefix.
 * Safe for SSR. Call periodically to avoid unbounded growth.
 */
export function removeExpiredKeys(prefix?: string): void {
  if (typeof window === "undefined") return;
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const key = window.localStorage.key(i);
      if (!key) continue;
      if (prefix && !key.startsWith(prefix)) continue;
      try {
        const raw = window.localStorage.getItem(key);
        if (!raw) continue;
        const item = JSON.parse(raw);
        if (item && typeof item.expiresAt === "number" && Date.now() > item.expiresAt) {
          keysToRemove.push(key);
        }
      } catch {
        // Not a TTL-wrapped item or corrupted — skip
      }
    }
    keysToRemove.forEach((k) => window.localStorage.removeItem(k));
  } catch {
    // fail silently
  }
}

/** Default TTLs */
export const TTL = {
  /** Vote UI state — 7 days */
  VOTE_STATE: 7 * 24 * 60 * 60 * 1000,
  /** Session/replay UI cache — 24 hours */
  SESSION_CACHE: 24 * 60 * 60 * 1000,
} as const;
