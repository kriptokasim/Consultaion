"use client"

import Link from "next/link"
import { useState } from "react"
import { useRouter } from "next/navigation"

import { AuthShell } from "@/components/auth/AuthShell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiRequest } from "@/lib/apiClient"
import { useI18n } from "@/lib/i18n/client"

export default function RegisterPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { t } = useI18n()

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
          <Link href="/login" className="underline underline-offset-4 text-[#3a2a1a] dark:text-amber-200">
            {t("auth.register.footerLink")}
          </Link>
        </span>
      }
    >
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
            className="border-amber-200/70 bg-white/80 focus-visible:ring-amber-500 dark:border-amber-200/30 dark:bg-white/5"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">{t("auth.register.password")}</Label>
          <Input
            id="password"
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="border-amber-200/70 bg-white/80 focus-visible:ring-amber-500 dark:border-amber-200/30 dark:bg-white/5"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm-password">{t("auth.register.confirm")}</Label>
          <Input
            id="confirm-password"
            type="password"
            required
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            className="border-amber-200/70 bg-white/80 focus-visible:ring-amber-500 dark:border-amber-200/30 dark:bg-white/5"
          />
        </div>
        {error ? <p className="text-sm text-red-600">{error}</p> : null}
        <Button type="submit" variant="amber" className="mt-2 w-full" disabled={loading}>
          {loading ? t("auth.register.ctaLoading") : t("auth.register.cta")}
        </Button>
      </form>
    </AuthShell>
  )
}
