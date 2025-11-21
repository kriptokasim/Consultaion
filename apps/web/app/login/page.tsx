"use client"

import Link from "next/link"
import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

import GoogleButton from "@/components/auth/GoogleButton"
import { AuthShell } from "@/components/auth/AuthShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { login } from "@/lib/auth"
import { useI18n } from "@/lib/i18n/client"

export default function LoginPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const nextPath = searchParams.get("next") || "/dashboard"
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { t } = useI18n()

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      router.push(nextPath)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title={t("auth.login.title")}
      subtitle={t("auth.login.subtitle")}
      footer={
        <span>
          {t("auth.login.footer")} {" "}
          <Link href="/register" className="underline underline-offset-4 text-[#3a2a1a] dark:text-amber-200">
            {t("auth.login.footerLink")}
          </Link>
        </span>
      }
    >
      <div className="flex flex-col gap-3 rounded-2xl border border-amber-100/60 bg-amber-50/80 p-5 text-center shadow-lg text-amber-950 dark:bg-stone-700/60 dark:text-amber-50">
        <GoogleButton nextPath={nextPath} label={t("auth.login.google")} className="w-full justify-center" />
        <div className="text-xs font-semibold uppercase tracking-[0.2em] text-amber-600">{t("auth.login.or")}</div>
        <p className="text-sm auth-muted">{t("auth.login.credentials")}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">{t("auth.login.email")}</Label>
          <Input
            id="email"
            type="email"
            required
            value={email}
            autoComplete="email"
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="border-amber-200/70 bg-white/80 focus-visible:ring-amber-500 dark:border-amber-200/30 dark:bg-white/5"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">{t("auth.login.password")}</Label>
          <Input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="border-amber-200/70 bg-white/80 focus-visible:ring-amber-500 dark:border-amber-200/30 dark:bg-white/5"
          />
        </div>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <Button type="submit" variant="amber" disabled={loading} className="mt-2 w-full">
          {loading ? t("auth.login.ctaLoading") : t("auth.login.cta")}
        </Button>
      </form>
    </AuthShell>
  )
}
