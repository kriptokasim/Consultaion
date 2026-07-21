/**
 * FH112: Server-side Google OAuth callback.
 *
 * Exchanges the authorization code server-side, sets HttpOnly/Secure/SameSite
 * cookie, and redirects to the dashboard. Replaces client-side ?token= reading.
 */

import { NextRequest, NextResponse } from "next/server";
import { sanitizeInternalPath } from "@/lib/security/internalPath";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");

  // 1. Check for OAuth error
  if (error) {
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(error)}`, request.url)
    );
  }

  // 2. Validate state parameter (nonce stored in cookie)
  const storedState = request.cookies.get("oauth_state")?.value;
  if (!state || !storedState || state !== storedState) {
    return NextResponse.redirect(
      new URL("/login?error=invalid_state", request.url)
    );
  }

  // 3. Validate authorization code
  if (!code) {
    return NextResponse.redirect(
      new URL("/login?error=missing_code", request.url)
    );
  }

  try {
    // 4. Exchange code server-side via backend
    const internalSecret = process.env.INTERNAL_SECRET || "";
    // Canonical app origin — required by backend origin check when state is
    // frontend-generated (not in backend state_store).
    const appOrigin =
      process.env.NEXT_PUBLIC_APP_URL ||
      process.env.NEXT_PUBLIC_SITE_URL ||
      "https://web.consultaion.com";
    const apiBase = API_BASE.replace(/\/$/, "");
    const response = await fetch(`${apiBase}/auth/google/callback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-internal-secret": internalSecret,
        Origin: appOrigin,
        Referer: `${appOrigin}/`,
      },
      body: JSON.stringify({ code, state }),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      console.error("OAuth callback exchange failed:", errBody);
      return NextResponse.redirect(
        new URL(`/login?error=${encodeURIComponent(errBody.code || errBody.detail || "exchange_failed")}`, request.url)
      );
    }

    const data = await response.json();
    const token = data.access_token || data.token;

    if (!token) {
      return NextResponse.redirect(
        new URL("/login?error=no_token", request.url)
      );
    }

    // 5. Set HttpOnly/Secure/SameSite cookie
    const nextPath = sanitizeInternalPath(
      request.cookies.get("oauth_next")?.value,
      "/dashboard"
    );
    const redirectUrl = new URL(nextPath, request.url);
    const responseNext = NextResponse.redirect(redirectUrl);

    // Same cookie name the backend reads (COOKIE_NAME / consultaion_token).
    // sameSite=lax is correct for same-site web.consultaion.com → /api proxy.
    responseNext.cookies.set("consultaion_token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30, // 30 days
    });
    // Double-submit CSRF token. This one must remain readable by the browser
    // client so it can mirror the value in X-CSRF-Token on mutations.
    responseNext.cookies.set("csrf_token", crypto.randomUUID().replaceAll("-", ""), {
      httpOnly: false,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });

    // Clear the OAuth state and next cookies
    responseNext.cookies.set("oauth_state", "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    });
    responseNext.cookies.set("oauth_next", "", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 0,
    });

    return responseNext;
  } catch (err) {
    console.error("OAuth callback error:", err);
    return NextResponse.redirect(
      new URL("/login?error=server_error", request.url)
    );
  }
}
