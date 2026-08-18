"use client";

import { useEffect } from "react";
import { fetchWithAuth } from "@/lib/auth";

export const REFERRAL_STORAGE_KEY = "consultaion_referral_token";
const VISIT_SESSION_PREFIX = "consultaion_referral_visit:";

export function ReferralVisitBridge() {
  useEffect(() => {
    const token = new URL(window.location.href).searchParams.get("ref")?.trim();
    if (!token || token.length > 256) return;

    try {
      window.localStorage.setItem(REFERRAL_STORAGE_KEY, token);
    } catch {
      // Attribution is best-effort; public content must remain usable when
      // storage is disabled by the browser/privacy mode.
    }

    const visitKey = `${VISIT_SESSION_PREFIX}${token}`;
    try {
      if (window.sessionStorage.getItem(visitKey)) return;
      window.sessionStorage.setItem(visitKey, "1");
    } catch {
      // Continue with the beacon even when sessionStorage is unavailable.
    }

    const controller = new AbortController();
    fetchWithAuth("/referrals/visit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
      signal: controller.signal,
    }).catch(() => {
      // Allow a later remount to retry if the best-effort beacon failed.
      try {
        window.sessionStorage.removeItem(visitKey);
      } catch {
        // no-op
      }
    });

    return () => controller.abort();
  }, []);

  return null;
}
