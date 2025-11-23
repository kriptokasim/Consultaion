"use client"

import { useEffect, useState } from "react"

import { apiRequest } from "@/lib/apiClient"
import { cn } from "@/lib/utils"
import { useI18n } from "@/lib/i18n/client"

type ProfileResponse = {
  id: string
  email: string
  display_name?: string | null
  avatar_url?: string | null
  bio?: string | null
  timezone?: string | null
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

const TIMEZONES = ["UTC", "Europe/Istanbul", "Europe/Brussels", "America/New_York", "Asia/Singapore", "Australia/Sydney"]

export default function ProfileSettings() {
  const [profile, setProfile] = useState<ProfileResponse | null>(null)
  const [form, setForm] = useState({
    display_name: "",
    avatar_url: "",
    bio: "",
    timezone: "",
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { t } = useI18n()

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/me/profile`, { credentials: "include", cache: "no-store" })
        if (!res.ok) {
          throw new Error("Profile request failed")
        }
        const data: ProfileResponse = await res.json()
        if (!cancelled) {
          setProfile(data)
          setForm({
            display_name: data.display_name ?? "",
            avatar_url: data.avatar_url ?? "",
            bio: data.bio ?? "",
            timezone: data.timezone ?? "",
          })
        }
      } catch (err) {
        if (!cancelled) {
          setError(t("settings.profile.loadError"))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const handleChange =
    (field: keyof typeof form) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setForm((prev) => ({ ...prev, [field]: event.target.value }))
    }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    setMessage(null)
    const payload = {
      display_name: form.display_name.trim() || null,
      avatar_url: form.avatar_url.trim() || null,
      bio: form.bio.trim() || null,
      timezone: form.timezone || null,
    }
    try {
      const updated = (await apiRequest<ProfileResponse, typeof payload>({
        method: "PUT",
        path: "/me/profile",
        body: payload,
      })) as ProfileResponse
      setProfile(updated)
      setMessage(t("settings.profile.saved"))
      setForm({
        display_name: updated.display_name ?? "",
        avatar_url: updated.avatar_url ?? "",
        bio: updated.bio ?? "",
        timezone: updated.timezone ?? "",
      })
    } catch (err) {
      setError(t("settings.profile.saveError"))
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(null), 4000)
    }
  }

  if (loading) {
    return (
      <div className="card-elevated p-6">
        <p className="text-sm text-stone-500">{t("settings.profile.loading")}</p>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="card-elevated border border-red-200/70 p-6">
        <p className="text-sm text-red-600">{error || t("settings.profile.signInRequired")}</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="card-elevated p-6">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">{t("settings.profile.section.kicker")}</p>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t("settings.profile.section.title")}</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">{t("settings.profile.section.description")}</p>
      </div>
      <div className="mt-6 space-y-4">
        <div>
          <label className="text-sm font-semibold text-stone-700 dark:text-stone-200">{t("settings.profile.emailLabel")}</label>
          <p className="text-sm text-stone-500">{profile.email}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <label htmlFor="display_name" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
              {t("settings.profile.displayName")}
            </label>
            <input
              id="display_name"
              name="display_name"
              maxLength={80}
              value={form.display_name}
              onChange={handleChange("display_name")}
              className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
              placeholder={t("settings.profile.displayPlaceholder")}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label htmlFor="avatar_url" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
              {t("settings.profile.avatarUrl")}
            </label>
            <input
              id="avatar_url"
              name="avatar_url"
              value={form.avatar_url}
              onChange={handleChange("avatar_url")}
              className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
              placeholder={t("settings.profile.avatarPlaceholder")}
            />
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="bio" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
            {t("settings.profile.bio")}
          </label>
          <textarea
            id="bio"
            name="bio"
            maxLength={1000}
            rows={4}
            value={form.bio}
            onChange={handleChange("bio")}
            className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
            placeholder={t("settings.profile.bioPlaceholder")}
          />
          <p className="text-xs text-stone-400">
            {t("settings.profile.bioCountLabel")} {form.bio.length}/1000
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="timezone" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
            {t("settings.profile.timezone")}
          </label>
          <select
            id="timezone"
            name="timezone"
            value={form.timezone}
            onChange={handleChange("timezone")}
            className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
          >
            <option value="">{t("settings.profile.timezonePlaceholder")}</option>
            {TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="mt-6 flex items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className={cn(
            "inline-flex items-center rounded-2xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow-md transition hover:bg-amber-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500",
            saving && "opacity-70",
          )}
        >
          {saving ? t("settings.profile.saving") : t("settings.profile.save")}
        </button>
        {message ? <span className="text-sm text-emerald-600">{message}</span> : null}
        {error ? <span className="text-sm text-red-600">{error}</span> : null}
      </div>
    </form>
  )
}
