/**
 * FH112: Server-side Google OAuth callback.
 *
 * Exchanges the authorization code server-side, sets HttpOnly/Secure/SameSite
 * cookie, and redirects to the dashboard. Replaces client-side ?token= reading.
 */

import { NextRequest, NextResponse } from "next/server";

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
    const response = await fetch(`${API_BASE}/auth/google/callback`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "x-internal-secret": internalSecret
      },
      body: JSON.stringify({ code, state }),
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      console.error("OAuth callback exchange failed:", errBody);
      return NextResponse.redirect(
        new URL(`/login?error=${encodeURIComponent(errBody.detail || "exchange_failed")}`, request.url)
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
    const nextParam = request.cookies.get("oauth_next")?.value || "/dashboard";
    let nextPath = "/dashboard";
    try {
      const base = new URL(request.url).origin;
      const resolved = new URL(nextParam, base);
      if (resolved.origin === base && !resolved.pathname.includes("\\")) {
        nextPath = resolved.pathname + resolved.search + resolved.hash;
      }
    } catch {
      nextPath = "/dashboard";
    }
    const redirectUrl = new URL(nextPath, request.url);
    const responseNext = NextResponse.redirect(redirectUrl);

    responseNext.cookies.set("consultaion_token", token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 24 * 30, // 30 days
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
