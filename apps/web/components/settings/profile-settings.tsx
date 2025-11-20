"use client"

import { useEffect, useState } from "react"

import { apiRequest } from "@/lib/apiClient"
import { cn } from "@/lib/utils"

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
          setError("Unable to load profile. Please check your session.")
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
      setMessage("Profile updated.")
      setForm({
        display_name: updated.display_name ?? "",
        avatar_url: updated.avatar_url ?? "",
        bio: updated.bio ?? "",
        timezone: updated.timezone ?? "",
      })
    } catch (err) {
      setError("Unable to save profile. Please try again.")
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(null), 4000)
    }
  }

  if (loading) {
    return (
      <div className="rounded-3xl border border-amber-100 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900">
        <p className="text-sm text-stone-500">Loading profile…</p>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="rounded-3xl border border-red-100 bg-white p-6 shadow-sm">
        <p className="text-sm text-red-600">{error || "You must be signed in to edit your profile."}</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-amber-100 bg-white p-6 shadow-[0_14px_30px_rgba(112,73,28,0.12)] dark:border-stone-800 dark:bg-stone-900">
      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Account profile</p>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">Amber-Mocha identity</h1>
        <p className="text-sm text-stone-600 dark:text-stone-300">Adjust your display name, avatar, and timezone so run receipts feel personal.</p>
      </div>
      <div className="mt-6 space-y-4">
        <div>
          <label className="text-sm font-semibold text-stone-700 dark:text-stone-200">Email</label>
          <p className="text-sm text-stone-500">{profile.email}</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <label htmlFor="display_name" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
              Display name
            </label>
            <input
              id="display_name"
              name="display_name"
              maxLength={80}
              value={form.display_name}
              onChange={handleChange("display_name")}
              className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
              placeholder="Amber Operative"
            />
          </div>
          <div className="flex flex-col gap-2">
            <label htmlFor="avatar_url" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
              Avatar URL
            </label>
            <input
              id="avatar_url"
              name="avatar_url"
              value={form.avatar_url}
              onChange={handleChange("avatar_url")}
              className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
              placeholder="https://example.com/avatar.png"
            />
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="bio" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
            Bio
          </label>
          <textarea
            id="bio"
            name="bio"
            maxLength={1000}
            rows={4}
            value={form.bio}
            onChange={handleChange("bio")}
            className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
            placeholder="AI parliament builder, policy tinkerer, midnight pilot."
          />
          <p className="text-xs text-stone-400">{form.bio.length}/1000</p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="timezone" className="text-sm font-semibold text-stone-700 dark:text-stone-200">
            Timezone
          </label>
          <select
            id="timezone"
            name="timezone"
            value={form.timezone}
            onChange={handleChange("timezone")}
            className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-800 shadow-inner focus-visible:ring-amber-500 dark:border-stone-600 dark:bg-stone-950 dark:text-stone-200"
          >
            <option value="">Select a timezone</option>
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
          {saving ? "Saving…" : "Save profile"}
        </button>
        {message ? <span className="text-sm text-emerald-600">{message}</span> : null}
        {error ? <span className="text-sm text-red-600">{error}</span> : null}
      </div>
    </form>
  )
}
