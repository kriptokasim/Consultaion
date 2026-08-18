"use client";

import { useEffect } from "react";
import { fetchWithAuth } from "@/lib/auth";
import { REFERRAL_STORAGE_KEY } from "./ReferralVisitBridge";

export function ReferralClaimBridge({ enabled }: { enabled: boolean }) {
  useEffect(() => {
    if (!enabled) return;

    let token: string | null = null;
    try {
      token = window.localStorage.getItem(REFERRAL_STORAGE_KEY)?.trim() || null;
    } catch {
      return;
    }
    if (!token || token.length > 256) {
      try {
        window.localStorage.removeItem(REFERRAL_STORAGE_KEY);
      } catch {
        // no-op
      }
      return;
    }

    const controller = new AbortController();
    fetchWithAuth("/referrals/claim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) return;
        // A 200 response means the backend handled valid/invalid/expired state
        // without exposing token validity. Stop retrying this browser token.
        try {
          window.localStorage.removeItem(REFERRAL_STORAGE_KEY);
        } catch {
          // no-op
        }
      })
      .catch(() => {
        // Keep the token for a later authenticated route when the request fails
        // due to a transient network/backend condition.
      });

    return () => controller.abort();
  }, [enabled]);

  return null;
}
