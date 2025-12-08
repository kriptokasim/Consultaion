"use client"

import { useState, useEffect } from "react"
import { useParams } from "next/navigation"
import { useI18n } from "@/lib/i18n/client"
import Link from "next/link"

interface UserSummary {
    user: {
        id: string
        email: string
        display_name: string | null
        plan: string
        created_at: string | null
        is_active: boolean
    }
    quota: {
        tokens_used_today: number
        daily_token_limit: number
        token_usage_pct: number
        exports_used_today: number
        daily_export_limit: number
        export_usage_pct: number
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
    recent_errors: any[]
}

interface Note {
    id: string
    note: string
    created_at: string | null
    author_email: string
}

export default function AdminUserDetailPage() {
    const params = useParams()
    const userId = params?.userId as string
    const { t } = useI18n()

    const [summary, setSummary] = useState<UserSummary | null>(null)
    const [notes, setNotes] = useState<Note[]>([])
    const [loading, setLoading] = useState(true)
    const [newNote, setNewNote] = useState("")
    const [saving, setSaving] = useState(false)

    const fetchData = async () => {
        setLoading(true)
        try {
            const [summaryRes, notesRes] = await Promise.all([
                fetch(`/api/admin/users/${userId}/summary`),
                fetch(`/api/admin/users/${userId}/notes`),
            ])
            const summaryData = await summaryRes.json()
            const notesData = await notesRes.json()
            setSummary(summaryData)
            setNotes(notesData.notes || [])
        } catch (error) {
            console.error("Failed to fetch user data:", error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (userId) {
            fetchData()
        }
    }, [userId])

    const handleAddNote = async () => {
        if (!newNote.trim()) return

        setSaving(true)
        try {
            const res = await fetch(`/api/admin/users/${userId}/notes`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ note: newNote }),
            })
            const data = await res.json()
            setNotes([data, ...notes])
            setNewNote("")
        } catch (error) {
            console.error("Failed to add note:", error)
        } finally {
            setSaving(false)
        }
    }

    const handleToggleStatus = async () => {
        if (!summary) return

        const newStatus = !summary.user.is_active
        try {
            await fetch(`/api/admin/users/${userId}/status`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_active: newStatus }),
            })
            setSummary({
                ...summary,
                user: { ...summary.user, is_active: newStatus },
            })
        } catch (error) {
            console.error("Failed to update status:", error)
        }
    }

    const handleChangePlan = async (newPlan: string) => {
        if (!summary || newPlan === summary.user.plan) return

        try {
            await fetch(`/api/admin/users/${userId}/plan`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ plan: newPlan }),
            })
            setSummary({
                ...summary,
                user: { ...summary.user, plan: newPlan },
            })
        } catch (error) {
            console.error("Failed to change plan:", error)
        }
    }

    if (loading) {
        return <div className="container mx-auto p-6 text-center text-stone-500">Loading...</div>
    }

    if (!summary) {
        return <div className="container mx-auto p-6 text-center text-stone-500">User not found</div>
    }

    const { user, quota, recent_debates, feedback_summary } = summary

    return (
        <div className="container mx-auto p-6">
            {/* Header */}
            <div className="mb-6">
                <Link href="/admin/users" className="text-sm text-amber-600 hover:text-amber-800">
                    ← Back to User Search
                </Link>
                <h1 className="mt-2 text-3xl font-bold text-stone-900">{user.email}</h1>
                <p className="text-sm text-stone-500">{user.id}</p>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
                {/* Left Column */}
                <div className="space-y-6">
                    {/* Identity & Plan Card */}
                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">User Info</h2>
                        <div className="space-y-3">
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
                                <div className="text-sm font-medium text-stone-500">Plan</div>
                                <div className="mt-1 flex items-center gap-2">
                                    <select
                                        value={user.plan}
                                        onChange={(e) => handleChangePlan(e.target.value)}
                                        className="rounded border border-stone-300 px-3 py-1.5 text-sm"
                                    >
                                        <option value="free">Free</option>
                                        <option value="pro">Pro</option>
                                        <option value="internal">Internal</option>
                                    </select>
                                </div>
                            </div>
                            <div>
                                <div className="text-sm font-medium text-stone-500">Account Status</div>
                                <div className="mt-2 flex items-center gap-3">
                                    <span
                                        className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${user.is_active
                                                ? "bg-green-100 text-green-800"
                                                : "bg-red-100 text-red-800"
                                            }`}
                                    >
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
                                    {user.created_at
                                        ? new Date(user.created_at).toLocaleDateString()
                                        : "N/A"}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Quota Card */}
                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">Quota Usage (Today)</h2>
                        <div className="space-y-4">
                            {/* Tokens */}
                            <div>
                                <div className="mb-1 flex items-center justify-between">
                                    <span className="text-sm font-medium text-stone-700">Tokens</span>
                                    <span className="text-sm text-stone-600">
                                        {quota.tokens_used_today.toLocaleString()} /{" "}
                                        {quota.daily_token_limit.toLocaleString()}
                                    </span>
                                </div>
                                <div className="h-3 overflow-hidden rounded-full bg-stone-200">
                                    <div
                                        className={`h-full transition-all ${quota.token_usage_pct >= 90
                                                ? "bg-red-500"
                                                : quota.token_usage_pct >= 70
                                                    ? "bg-amber-500"
                                                    : "bg-green-500"
                                            }`}
                                        style={{ width: `${Math.min(quota.token_usage_pct, 100)}%` }}
                                    />
                                </div>
                                <div className="mt-1 text-xs text-stone-500">
                                    {quota.token_usage_pct.toFixed(1)}% used
                                </div>
                            </div>

                            {/* Exports */}
                            <div>
                                <div className="mb-1 flex items-center justify-between">
                                    <span className="text-sm font-medium text-stone-700">Exports</span>
                                    <span className="text-sm text-stone-600">
                                        {quota.exports_used_today} / {quota.daily_export_limit}
                                    </span>
                                </div>
                                <div className="h-3 overflow-hidden rounded-full bg-stone-200">
                                    <div
                                        className={`h-full transition-all ${quota.export_usage_pct >= 90
                                                ? "bg-red-500"
                                                : quota.export_usage_pct >= 70
                                                    ? "bg-amber-500"
                                                    : "bg-green-500"
                                            }`}
                                        style={{ width: `${Math.min(quota.export_usage_pct, 100)}%` }}
                                    />
                                </div>
                                <div className="mt-1 text-xs text-stone-500">
                                    {quota.export_usage_pct.toFixed(1)}% used
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Right Column */}
                <div className="space-y-6">
                    {/* Recent Debates */}
                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">Recent Debates</h2>
                        {recent_debates.length === 0 ? (
                            <p className="text-sm text-stone-500">No debates yet</p>
                        ) : (
                            <div className="space-y-3">
                                {recent_debates.map((debate) => (
                                    <div
                                        key={debate.id}
                                        className="rounded border border-stone-200 p-3 hover:bg-stone-50"
                                    >
                                        <div className="mb-1 flex items-start justify-between">
                                            <span className="text-sm font-medium text-stone-900">
                                                {debate.prompt}
                                            </span>
                                            <span
                                                className={`ml-2 rounded px-2 py-0.5 text-xs font-semibold ${debate.status === "completed"
                                                        ? "bg-green-100 text-green-800"
                                                        : debate.status === "failed"
                                                            ? "bg-red-100 text-red-800"
                                                            : "bg-amber-100 text-amber-800"
                                                    }`}
                                            >
                                                {debate.status}
                                            </span>
                                        </div>
                                        <div className="flex items-center gap-3 text-xs text-stone-500">
                                            <span>
                                                {debate.created_at
                                                    ? new Date(debate.created_at).toLocaleString()
                                                    : "N/A"}
                                            </span>
                                            <span>•</span>
                                            <span className="capitalize">{debate.mode}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Support Notes */}
                    <div className="rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
                        <h2 className="mb-4 text-xl font-bold text-stone-900">Support Notes</h2>

                        {/* Add Note */}
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

                        {/* Notes List */}
                        {notes.length === 0 ? (
                            <p className="text-sm text-stone-500">
                                No notes yet. Add a note to track support actions.
                            </p>
                        ) : (
                            <div className="space-y-3">
                                {notes.map((note) => (
                                    <div key={note.id} className="rounded border border-stone-200 p-3">
                                        <p className="mb-2 text-sm text-stone-900">{note.note}</p>
                                        <div className="text-xs text-stone-500">
                                            by {note.author_email} •{" "}
                                            {note.created_at
                                                ? new Date(note.created_at).toLocaleString()
                                                : "N/A"}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
