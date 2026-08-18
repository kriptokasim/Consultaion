"use client"

import { useState, useEffect, useCallback } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"
import { fetchWithAuth } from "@/lib/auth"

interface UserSummary {
    user: {
        id: string
        email: string
        display_name: string | null
        plan: string
        created_at: string | null
        is_active: boolean
    }
    recent_debates: Array<{
        id: string
        prompt: string
        created_at: string | null
        status: string
        mode: string
    }>
    feedback_summary: {
        total: number
        helpful: number
        not_helpful: number
    }
    recent_errors: unknown[]
}

interface CanonicalUserDetail {
    user: {
        id: string
        email: string
        display_name: string | null
        plan?: string
        created_at: string | null
        is_active: boolean
    }
    plan: {
        slug: string
        name: string
        price_monthly: number | null
        currency: string
        is_default_free: boolean
    } | null
    subscriptions: Array<{
        id: string
        plan_id: string
        status: string
        current_period_start: string
        current_period_end: string
        provider: string
        cancel_at_period_end: boolean
    }>
}

interface CanonicalQuotaRow {
    user_id: string
    email: string
    plan: string
    legacy_plan_marker?: string
    tokens_used_today: number
    daily_token_limit: number
    token_usage_pct: number
    exports_used_today: number
    daily_export_limit: number
    export_usage_pct: number
    created_at: string | null
}

interface Note {
    id: string
    note: string
    created_at: string | null
    author_email: string
}

async function jsonOrThrow<T>(response: Response): Promise<T> {
    if (!response.ok) {
        const payload = await response.json().catch(() => null)
        const detail = payload?.detail?.message || payload?.detail || payload?.message
        throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`)
    }
    return response.json() as Promise<T>
}

export default function AdminUserDetailPage() {
    const params = useParams()
    const userId = params?.userId as string

    const [summary, setSummary] = useState<UserSummary | null>(null)
    const [detail, setDetail] = useState<CanonicalUserDetail | null>(null)
    const [quota, setQuota] = useState<CanonicalQuotaRow | null>(null)
    const [notes, setNotes] = useState<Note[]>([])
    const [loading, setLoading] = useState(true)
    const [newNote, setNewNote] = useState("")
    const [saving, setSaving] = useState(false)
    const [entitlementSaving, setEntitlementSaving] = useState(false)
    const [entitlementError, setEntitlementError] = useState<string | null>(null)

    const fetchData = useCallback(async () => {
        setLoading(true)
        try {
            const [summaryRes, detailRes, quotaRes, notesRes] = await Promise.all([
                fetchWithAuth(`/admin/users/${userId}/summary`),
                fetchWithAuth(`/admin/users/${userId}`),
                fetchWithAuth(`/admin/usage/quota?user_id=${encodeURIComponent(userId)}&limit=1`),
                fetchWithAuth(`/admin/users/${userId}/notes`),
            ])

            const [summaryData, detailData, quotaData, notesData] = await Promise.all([
                jsonOrThrow<UserSummary>(summaryRes),
                jsonOrThrow<CanonicalUserDetail>(detailRes),
                jsonOrThrow<{ users: CanonicalQuotaRow[] }>(quotaRes),
                jsonOrThrow<{ notes: Note[] }>(notesRes),
            ])

            setSummary(summaryData)
            setDetail(detailData)
            setQuota(quotaData.users[0] || null)
            setNotes(notesData.notes || [])
        } catch (error) {
            console.error("Failed to fetch user data:", error)
            setSummary(null)
            setDetail(null)
            setQuota(null)
        } finally {
            setLoading(false)
        }
    }, [userId])

    useEffect(() => {
        if (userId) {
            void fetchData()
        }
    }, [userId, fetchData])

    const handleAddNote = async () => {
        if (!newNote.trim()) return

        setSaving(true)
        try {
            const res = await fetchWithAuth(`/admin/users/${userId}/notes`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ note: newNote }),
            })
            const data = await jsonOrThrow<Note>(res)
            setNotes((current) => [data, ...current])
            setNewNote("")
        } catch (error) {
            console.error("Failed to add note:", error)
        } finally {
            setSaving(false)
        }
    }

    const handleToggleStatus = async () => {
        if (!detail) return

        const newStatus = !detail.user.is_active
        try {
            const res = await fetchWithAuth(`/admin/users/${userId}/status`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: newStatus }),
            })
            await jsonOrThrow(res)
            await fetchData()
        } catch (error) {
            console.error("Failed to update status:", error)
        }
    }

    const handleGrantPro = async () => {
        setEntitlementSaving(true)
        setEntitlementError(null)
        try {
            const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
            const res = await fetchWithAuth(`/admin/users/${userId}/entitlement`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    plan: "pro",
                    expires_at: expiresAt,
                    reason: "Admin console 30-day Pro access grant",
                }),
            })
            await jsonOrThrow(res)
            await fetchData()
        } catch (error) {
            setEntitlementError(error instanceof Error ? error.message : "Unable to grant entitlement")
        } finally {
            setEntitlementSaving(false)
        }
    }

    const handleRevokeManualEntitlement = async () => {
        setEntitlementSaving(true)
        setEntitlementError(null)
        try {
            const res = await fetchWithAuth(`/admin/users/${userId}/entitlement`, {
                method: "DELETE",
            })
            await jsonOrThrow(res)
            await fetchData()
        } catch (error) {
            setEntitlementError(error instanceof Error ? error.message : "Unable to revoke entitlement")
        } finally {
            setEntitlementSaving(false)
        }
    }

    if (loading) {
        return <div className="container mx-auto p-6 text-center text-stone-500">Loading...</div>
    }

    if (!summary || !detail || !quota) {
        return <div className="container mx-auto p-6 text-center text-stone-500">User not found</div>
    }

    const user = detail.user
    const effectivePlan = detail.plan?.slug || quota.plan || "free"
    const activeManualGrant = detail.subscriptions.find((subscription) =>
        subscription.provider === "manual"
        && ["active", "trialing"].includes(subscription.status)
        && new Date(subscription.current_period_end).getTime() > Date.now()
    )
    const activeProviderEntitlement = detail.subscriptions.find((subscription) =>
        subscription.provider !== "manual"
        && ["active", "trialing"].includes(subscription.status)
        && new Date(subscription.current_period_start).getTime() <= Date.now()
        && new Date(subscription.current_period_end).getTime() > Date.now()
    )
    const { recent_debates, feedback_summary } = summary

    return (
        <div className="container mx-auto p-6">
            <div className="mb-6">
                <Link href="/admin/users" className="text-sm text-amber-600 hover:text-amber-800">
                    ← Back to User Search
                </Link>
                <h1 className="mt-2 text-3xl font-bold text-stone-900">{user.email}</h1>
                <p className="text-sm text-stone-500">{user.id}</p>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
                <div className="space-y-6">
                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">User Info</h2>
                        <div className="space-y-4">
                            <div>
                                <div className="text-sm font-medium text-stone-500">Email</div>
                                <div className="text-stone-900">{user.email}</div>
                            </div>
                            {user.display_name && (
                                <div>
                                    <div className="text-sm font-medium text-stone-500">Display Name</div>
                                    <div className="text-stone-900">{user.display_name}</div>
                                </div>
                            )}
                            <div>
                                <div className="text-sm font-medium text-stone-500">Effective Plan</div>
                                <div className="mt-1 flex flex-wrap items-center gap-2">
                                    <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold capitalize text-amber-900">
                                        {effectivePlan}
                                    </span>
                                    {activeProviderEntitlement && (
                                        <span className="text-xs text-stone-500">
                                            {activeProviderEntitlement.provider} entitlement
                                        </span>
                                    )}
                                    {activeManualGrant && (
                                        <span className="text-xs text-stone-500">
                                            manual grant until {new Date(activeManualGrant.current_period_end).toLocaleDateString()}
                                        </span>
                                    )}
                                </div>
                                {quota.legacy_plan_marker && quota.legacy_plan_marker !== effectivePlan && (
                                    <p className="mt-1 text-xs text-amber-700">
                                        Legacy marker: {quota.legacy_plan_marker} — authorization uses {effectivePlan}.
                                    </p>
                                )}
                                <div className="mt-3 flex flex-wrap gap-2">
                                    {!activeProviderEntitlement && effectivePlan === "free" && (
                                        <button
                                            onClick={handleGrantPro}
                                            disabled={entitlementSaving}
                                            className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                                        >
                                            {entitlementSaving ? "Updating..." : "Grant Pro for 30 days"}
                                        </button>
                                    )}
                                    {activeManualGrant && (
                                        <button
                                            onClick={handleRevokeManualEntitlement}
                                            disabled={entitlementSaving}
                                            className="rounded border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50"
                                        >
                                            {entitlementSaving ? "Updating..." : "Revoke manual grant"}
                                        </button>
                                    )}
                                </div>
                                {entitlementError && (
                                    <p className="mt-2 text-sm text-red-600">{entitlementError}</p>
                                )}
                            </div>
                            <div>
                                <div className="text-sm font-medium text-stone-500">Account Status</div>
                                <div className="mt-2 flex items-center gap-3">
                                    <span className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${user.is_active ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
                                        {user.is_active ? "Active" : "Disabled"}
                                    </span>
                                    <button
                                        onClick={handleToggleStatus}
                                        className="rounded bg-stone-200 px-3 py-1 text-sm font-medium text-stone-700 hover:bg-stone-300"
                                    >
                                        {user.is_active ? "Disable" : "Enable"}
                                    </button>
                                </div>
                            </div>
                            <div>
                                <div className="text-sm font-medium text-stone-500">Member Since</div>
                                <div className="text-stone-900">
                                    {user.created_at ? new Date(user.created_at).toLocaleDateString() : "N/A"}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">Quota Usage (Today)</h2>
                        <div className="space-y-4">
                            <div>
                                <div className="mb-1 flex items-center justify-between">
                                    <span className="text-sm font-medium text-stone-700">Tokens</span>
                                    <span className="text-sm text-stone-600">
                                        {quota.tokens_used_today.toLocaleString()} / {quota.daily_token_limit.toLocaleString()}
                                    </span>
                                </div>
                                <div className="h-3 overflow-hidden rounded-full bg-stone-200">
                                    <div
                                        className={`h-full transition-all ${quota.token_usage_pct >= 90 ? "bg-red-500" : quota.token_usage_pct >= 70 ? "bg-amber-500" : "bg-green-500"}`}
                                        style={{ width: `${Math.min(quota.token_usage_pct, 100)}%` }}
                                    />
                                </div>
                                <div className="mt-1 text-xs text-stone-500">{quota.token_usage_pct.toFixed(1)}% used</div>
                            </div>
                            <div>
                                <div className="mb-1 flex items-center justify-between">
                                    <span className="text-sm font-medium text-stone-700">Exports</span>
                                    <span className="text-sm text-stone-600">
                                        {quota.exports_used_today} / {quota.daily_export_limit}
                                    </span>
                                </div>
                                <div className="h-3 overflow-hidden rounded-full bg-stone-200">
                                    <div
                                        className={`h-full transition-all ${quota.export_usage_pct >= 90 ? "bg-red-500" : quota.export_usage_pct >= 70 ? "bg-amber-500" : "bg-green-500"}`}
                                        style={{ width: `${Math.min(quota.export_usage_pct, 100)}%` }}
                                    />
                                </div>
                                <div className="mt-1 text-xs text-stone-500">{quota.export_usage_pct.toFixed(1)}% used</div>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="space-y-6">
                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">Recent Runs</h2>
                        {recent_debates.length === 0 ? (
                            <p className="text-sm text-stone-500">No runs yet</p>
                        ) : (
                            <div className="space-y-3">
                                {recent_debates.map((debate) => (
                                    <div key={debate.id} className="rounded border border-stone-200 p-3 hover:bg-stone-50">
                                        <div className="mb-1 flex items-start justify-between">
                                            <span className="text-sm font-medium text-stone-900">{debate.prompt}</span>
                                            <span className={`ml-2 rounded px-2 py-0.5 text-xs font-semibold ${debate.status === "completed" ? "bg-green-100 text-green-800" : debate.status === "failed" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-800"}`}>
                                                {debate.status}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-3 text-xs text-stone-500">
                                            <span>{debate.created_at ? new Date(debate.created_at).toLocaleString() : "N/A"}</span>
                                            <span>•</span>
                                            <span className="capitalize">{debate.mode}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">Support Notes</h2>
                        <div className="mb-4">
                            <textarea
                                value={newNote}
                                onChange={(e) => setNewNote(e.target.value)}
                                placeholder="Add an internal note..."
                                className="w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none"
                                rows={3}
                            />
                            <button
                                onClick={handleAddNote}
                                disabled={!newNote.trim() || saving}
                                className="mt-2 rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                            >
                                {saving ? "Adding..." : "Add Note"}
                            </button>
                        </div>

                        {notes.length === 0 ? (
                            <p className="text-sm text-stone-500">No notes yet. Add a note to track support actions.</p>
                        ) : (
                            <div className="space-y-3">
                                {notes.map((note) => (
                                    <div key={note.id} className="rounded border border-stone-200 p-3">
                                        <p className="mb-2 text-sm text-stone-900">{note.note}</p>
                                        <div className="text-xs text-stone-500">
                                            by {note.author_email} • {note.created_at ? new Date(note.created_at).toLocaleString() : "N/A"}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-2 text-xl font-bold text-stone-900">Feedback</h2>
                        <p className="text-sm text-stone-600">
                            {feedback_summary.total} total · {feedback_summary.helpful} helpful · {feedback_summary.not_helpful} not helpful
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
}
