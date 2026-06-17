/**
 * FH112: Server-side Google OAuth initiation.
 *
 * Generates a nonce, stores it in an HttpOnly cookie,
 * and redirects to Google's OAuth consent screen.
 */

import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID || "";
const GOOGLE_REDIRECT_URI = process.env.GOOGLE_REDIRECT_URL || `${process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"}/api/auth/google/callback`;

export async function GET(request: NextRequest) {
  if (!GOOGLE_CLIENT_ID) {
    return NextResponse.redirect(
      new URL("/login?error=google_not_configured", request.url)
    );
  }

  const { searchParams } = new URL(request.url);
  const nextPath = searchParams.get("next") || "/live";

  // 1. Generate cryptographically random state nonce
  const state = crypto.randomBytes(32).toString("hex");

  // 2. Build Google OAuth consent URL
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: GOOGLE_REDIRECT_URI,
    response_type: "code",
    scope: "openid email profile",
    state,
    access_type: "offline",
    prompt: "consent",
  });

  const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;

  // 3. Redirect to Google with state cookie set
  const response = NextResponse.redirect(googleAuthUrl);

  response.cookies.set("oauth_state", state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 600, // 10 minutes
  });

  // Also store the intended destination so callback can redirect there
  response.cookies.set("oauth_next", nextPath, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });

  return response;
}
