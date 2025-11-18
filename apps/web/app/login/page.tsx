"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import GoogleButton from "@/components/auth/GoogleButton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { login } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push(nextPath);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-amber-50 via-[#fff7eb] to-[#f8e6c2] px-4 py-10">
      <div className="w-full max-w-xl space-y-6 rounded-2xl border border-amber-100/80 bg-white/90 p-8 shadow-[0_24px_60px_rgba(112,73,28,0.12)] backdrop-blur">
        <div className="space-y-2 text-left">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700">Welcome back</p>
          <h1 className="heading-serif text-3xl font-semibold text-[#3a2a1a]">Sign in to Consultaion</h1>
          <p className="text-sm text-[#5a4a3a]">Use Google for a quick start or continue with email and password.</p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <GoogleButton nextPath={nextPath} className="w-full sm:w-auto" />
          <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">or</span>
          <div className="flex-1 text-right text-sm text-stone-600">Use your workspace credentials</div>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[#3a2a1a]" htmlFor="email">
              Email
            </label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              aria-label="Email address"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-semibold text-[#3a2a1a]" htmlFor="password">
              Password
            </label>
            <Input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              aria-label="Password"
            />
          </div>
          {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}
          <Button type="submit" disabled={loading} className="w-full rounded-xl py-2 text-base shadow-[0_14px_32px_rgba(255,190,92,0.35)]">
            {loading ? "Signing in…" : "Sign In"}
          </Button>
        </form>
      </div>
    </main>
  );
}
