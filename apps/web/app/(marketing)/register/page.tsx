"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { AuthShell } from "@/components/auth/AuthShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PasswordInput } from "@/components/ui/PasswordInput"
import { Label } from "@/components/ui/label"
import { SkeletonLoader } from "@/components/ui/SkeletonLoader"
import { apiRequest } from "@/lib/apiClient"
import { useI18n } from "@/lib/i18n/client"

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [hydrating, setHydrating] = useState(true)
  const { t } = useI18n()

  useEffect(() => {
    const timer = window.setTimeout(() => setHydrating(false), 150)
    return () => window.clearTimeout(timer)
  }, [])

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)

    if (password !== confirm) {
      setError(t("auth.register.errorMismatch"))
      return
    }

    setLoading(true)
    try {
      await apiRequest({
        method: "POST",
        path: "/auth/register",
        body: { email, password },
      })
      router.push("/login")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign up")
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title={t("auth.register.title")}
      subtitle={t("auth.register.subtitle")}
      footer={
        <span>
          {t("auth.register.footer")} {" "}
          <Link href="/login" className="underline underline-offset-4 text-slate-800 dark:text-blue-400">
            {t("auth.register.footerLink")}
          </Link>
        </span>
      }
    >
      {hydrating ? (
        <div className="space-y-3 rounded-2xl border border-slate-100 bg-blue-50/80 p-5 shadow-lg dark:border-slate-700 dark:bg-slate-800">
          <SkeletonLoader className="h-4 w-3/4 bg-white/60 dark:bg-slate-700" />
          <SkeletonLoader lines={3} className="h-10 bg-white/60 dark:bg-slate-700" />
          <SkeletonLoader className="h-10 w-full rounded-xl bg-white/60 dark:bg-slate-700" />
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">{t("auth.register.email")}</Label>
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="border-slate-200 bg-white/90 text-slate-900 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-white"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">{t("auth.register.password")}</Label>
            <PasswordInput
              id="password"
              required
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="border-slate-200 bg-white/90 text-slate-900 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-white"
            />
            <p className="text-xs text-slate-600 dark:text-slate-400">{t("auth.register.passwordHelp")}</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-password">{t("auth.register.confirm")}</Label>
            <PasswordInput
              id="confirm-password"
              required
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="border-slate-200 bg-white/90 text-slate-900 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-slate-600 dark:bg-slate-800 dark:text-white"
            />
          </div>
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <Button type="submit" className="mt-2 w-full" disabled={loading}>
            {loading ? t("auth.register.ctaLoading") : t("auth.register.cta")}
          </Button>
          <p className="text-xs text-center text-slate-600 dark:text-slate-400">
            By creating an account, you agree to our{" "}
            <Link href="/terms" className="underline underline-offset-2 hover:text-primary">
              {t("auth.register.termsLink")}
            </Link>{" "}
            and{" "}
            <Link href="/privacy" className="underline underline-offset-2 hover:text-primary">
              {t("auth.register.privacyLink")}
            </Link>.
          </p>
        </form>
      )}
    </AuthShell>
  )
}
