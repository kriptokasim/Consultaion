"use client"

import { useState } from "react"
import { useI18n } from "@/lib/i18n/client"
import { API_ORIGIN } from "@/lib/config/runtime"

const API_BASE = API_ORIGIN

type AdminUser = {
  id: string
  email: string
  display_name?: string | null
  is_admin?: boolean
  created_at?: string | null
  plan?: { slug: string | null } | null
  debate_count?: number
}

type AdminUserDetail = {
  user: { email: string; display_name?: string | null }
  plan?: { slug: string | null; name?: string | null }
  usage?: { debates_created?: number; tokens_used?: number; period?: string }
  subscriptions?: Array<{ id: string; status: string; current_period_end: string }>
}

type AdminUserBilling = {
  plan?: { slug: string | null }
  usage?: { debates_created?: number; tokens_used?: number; period?: string }
}

export default function AdminUsersClient({ initialItems }: { initialItems: AdminUser[] }) {
  const { t } = useI18n()
  const [users, setUsers] = useState<AdminUser[]>(initialItems)
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<{ profile: AdminUserDetail | null; billing: AdminUserBilling | null }>({
    profile: null,
    billing: null,
  })
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchUsers = async (search?: string) => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams()
      if (search) {
        params.set("q", search)
      }
      const res = await fetch(`${API_BASE}/admin/users${params.toString() ? `?${params}` : ""}`, { credentials: "include" })
      if (!res.ok) {
        throw new Error("Request failed")
      }
      const payload = await res.json()
      setUsers(payload.items || [])
    } catch (err) {
      setError("Unable to load users.")
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (event: React.FormEvent) => {
    event.preventDefault()
    fetchUsers(query.trim())
  }

  const loadDetail = async (userId: string) => {
    setDetailLoading(true)
    setError(null)
    try {
      const [profileRes, billingRes] = await Promise.all([
        fetch(`${API_BASE}/admin/users/${userId}`, { credentials: "include" }),
        fetch(`${API_BASE}/admin/users/${userId}/billing`, { credentials: "include" }),
      ])
      if (!profileRes.ok || !billingRes.ok) {
        throw new Error("detail request failed")
      }
      const profilePayload = (await profileRes.json()) as AdminUserDetail
      const billingPayload = (await billingRes.json()) as AdminUserBilling
      setDetail({ profile: profilePayload, billing: billingPayload })
    } catch (err) {
      setError("Unable to load user detail.")
    } finally {
      setDetailLoading(false)
    }
  }

  const handleSelect = (userId: string) => {
    setSelectedId(userId)
    loadDetail(userId)
  }

  return (
    <div className="space-y-6">
      <div className="glass-card p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Users</p>
            <h2 className="text-xl font-semibold text-stone-900 dark:text-stone-100">Accounts &amp; plans</h2>
          </div>
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search email or name"
              className="rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm shadow-inner focus-visible:ring-amber-500 dark:border-stone-700 dark:bg-stone-950 dark:text-stone-100"
            />
            <button
              type="submit"
              className="rounded-2xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-amber-500 focus-visible:ring-2 focus-visible:ring-amber-500"
            >
              Search
            </button>
          </form>
        </div>
        {error ? <p className="mt-2 text-sm text-red-600">{error}</p> : null}
        <div className="mt-4 overflow-x-auto rounded-2xl border border-amber-100 bg-white/70 dark:border-amber-200/20 dark:bg-white/5">
          <table className="min-w-full divide-y divide-amber-100 text-sm">
            <thead className="bg-amber-50 text-left text-xs font-semibold uppercase tracking-wide text-amber-800">
              <tr>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Display name</th>
                <th className="px-4 py-3">Plan</th>
                <th className="px-4 py-3">Admin</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-amber-50 text-stone-700">
              {users.map((user) => {
                const active = selectedId === user.id
                return (
                  <tr
                    key={user.id}
                    className={active ? "bg-amber-50/70" : "cursor-pointer hover:bg-amber-50/40"}
                    onClick={() => handleSelect(user.id)}
                  >
                    <td className="px-4 py-3 font-semibold text-stone-900">{user.email}</td>
                    <td className="px-4 py-3">{user.display_name || "—"}</td>
                    <td className="px-4 py-3 text-stone-600">{user.plan?.slug || "—"}</td>
                    <td className="px-4 py-3">
                      {user.is_admin ? (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">Admin</span>
                      ) : (
                        <span className="text-xs text-stone-400">User</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-stone-500">{user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}</td>
                  </tr>
                )
              })}
              {!users.length ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-stone-500">
                    {loading ? t("processing") : query ? t("admin.users.emptySearch") : "No users yet."}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="glass-card p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">User detail</p>
        {detailLoading ? <p className="text-sm text-stone-500">Loading detail…</p> : null}
        {!detail.profile && !detailLoading ? <p className="text-sm text-stone-500">Select a user to inspect billing.</p> : null}
        {detail.profile ? (
          <div className="mt-4 space-y-4">
            <div>
              <p className="text-lg font-semibold text-stone-900 dark:text-stone-100">{detail.profile.user.display_name || detail.profile.user.email}</p>
              <p className="text-sm text-stone-500">{detail.profile.user.email}</p>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-2xl border border-amber-100 bg-amber-50/40 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Plan</p>
                <p className="text-sm text-stone-800">{detail.profile.plan?.slug || "unassigned"}</p>
                <p className="text-xs text-stone-500">{detail.profile.plan?.name || ""}</p>
              </div>
              <div className="rounded-2xl border border-amber-100 bg-amber-50/40 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Usage ({detail.profile.usage?.period || detail.billing?.usage?.period || "-"})</p>
                <p className="text-sm text-stone-800">
                  Debates: {detail.profile.usage?.debates_created ?? detail.billing?.usage?.debates_created ?? 0}
                </p>
                <p className="text-sm text-stone-800">
                  Tokens: {Intl.NumberFormat().format(detail.profile.usage?.tokens_used ?? detail.billing?.usage?.tokens_used ?? 0)}
                </p>
              </div>
            </div>
            {detail.profile.subscriptions && detail.profile.subscriptions.length ? (
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Subscriptions</p>
                <ul className="mt-2 space-y-2 text-sm text-stone-700">
                  {detail.profile.subscriptions.map((sub) => (
                    <li key={sub.id} className="rounded-2xl border border-amber-100 bg-white px-3 py-2 shadow-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold">{sub.status}</span>
                        <span className="text-xs text-stone-500">
                          Renews {new Date(sub.current_period_end).toLocaleDateString()}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
