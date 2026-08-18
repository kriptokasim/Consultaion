"use client";

import { useEffect } from "react";
import { fetchWithAuth } from "@/lib/auth";

export const REFERRAL_STORAGE_KEY = "consultaion_referral_token";
const VISIT_SESSION_PREFIX = "consultaion_referral_visit:";

export function ReferralVisitBridge() {
  useEffect(() => {
    const currentUrl = new URL(window.location.href);
    const token = currentUrl.searchParams.get("ref")?.trim();
    if (!token || token.length > 256) return;

    try {
      window.localStorage.setItem(REFERRAL_STORAGE_KEY, token);
    } catch {
      // Attribution is best-effort; public content must remain usable when
      // storage is disabled by the browser/privacy mode.
    }

    // Once the token is captured, remove it from the visible address bar so it
    // is less likely to be copied again or retained in subsequent same-origin
    // navigation/referrer logs. The backend still receives the token only in
    // the POST body and persists only its hash.
    currentUrl.searchParams.delete("ref");
    window.history.replaceState(window.history.state, "", currentUrl.toString());

    const visitKey = `${VISIT_SESSION_PREFIX}${token}`;
    try {
      if (window.sessionStorage.getItem(visitKey)) return;
      window.sessionStorage.setItem(visitKey, "1");
    } catch {
      // Continue with the beacon even when sessionStorage is unavailable.
    }

    const clearVisitDedupe = () => {
      try {
        window.sessionStorage.removeItem(visitKey);
      } catch {
        // no-op
      }
    };

    const controller = new AbortController();
    fetchWithAuth("/referrals/visit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) clearVisitDedupe();
      })
      .catch(clearVisitDedupe);

    return () => controller.abort();
  }, []);

  return null;
}
