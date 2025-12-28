"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"

import GoogleButton from "@/components/auth/GoogleButton"
import { AuthShell } from "@/components/auth/AuthShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SkeletonLoader } from "@/components/ui/SkeletonLoader"
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
  const [hydrating, setHydrating] = useState(true)
  const { t } = useI18n()

  useEffect(() => {
    const timer = window.setTimeout(() => setHydrating(false), 150)
    return () => window.clearTimeout(timer)
  }, [])

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
          <Link href="/register" className="underline underline-offset-4 text-slate-800 dark:text-blue-400">
            {t("auth.login.footerLink")}
          </Link>
        </span>
      }
    >
      {hydrating ? (
        <div className="space-y-3 rounded-2xl border border-slate-100 bg-blue-50/80 p-5 shadow-lg dark:border-slate-700 dark:bg-slate-800">
          <SkeletonLoader className="h-10 w-full rounded-xl bg-white/60 dark:bg-slate-700" />
          <SkeletonLoader className="h-3 w-20 bg-white/60 dark:bg-slate-700" />
          <SkeletonLoader lines={2} className="h-3 bg-white/60 dark:bg-slate-700" />
        </div>
      ) : (
        <div className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-blue-50/80 p-5 text-center shadow-lg text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-white">
          <GoogleButton nextPath={nextPath} label={t("auth.login.google")} className="w-full justify-center focus-ring" />
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-primary dark:text-blue-400">{t("auth.login.or")}</div>
          <p className="text-sm auth-muted">{t("auth.login.credentials")}</p>
        </div>
      )}

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
            className="border-slate-200 bg-white/90 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-800"
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
            className="border-slate-200 bg-white/90 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-800"
          />
        </div>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <Button type="submit" disabled={loading} className="mt-2 w-full">
          {loading ? t("auth.login.ctaLoading") : t("auth.login.cta")}
        </Button>
      </form>
    </AuthShell>
  )
}
