"use client"

import { useState, useEffect } from "react"
import { useI18n } from "@/lib/i18n/client"

interface User {
    user_id: string
    email: string
    plan: string
    tokens_used_today: number
    daily_token_limit: number
    token_usage_pct: number
    exports_used_today: number
    daily_export_limit: number
    export_usage_pct: number
    created_at: string | null
}

export default function AdminQuotaUsagePage() {
    const { t } = useI18n()
    const [users, setUsers] = useState<User[]>([])
    const [loading, setLoading] = useState(true)
    const [emailFilter, setEmailFilter] = useState("")
    const [planFilter, setPlanFilter] = useState("")

    const fetchUsage = async () => {
        setLoading(true)
        const params = new URLSearchParams()
        if (emailFilter) params.set("email", emailFilter)
        if (planFilter) params.set("plan", planFilter)

        const res = await fetch(`/api/admin/usage/quota?${params}`)
        const data = await res.json()
        setUsers(data.users || [])
        setLoading(false)
    }

    useEffect(() => {
        fetchUsage()
    }, [emailFilter, planFilter])

    return (
        <div className="container mx-auto p-6">
            <h1 className="mb-6 text-3xl font-bold text-stone-900">
                Usage & Plan Management
            </h1>

            {/* Filters */}
            <div className="mb-6 flex gap-4">
                <input
                    type="text"
                    placeholder="Filter by email..."
                    value={emailFilter}
                    onChange={(e) => setEmailFilter(e.target.value)}
                    className="rounded-lg border border-stone-300 px-4 py-2 focus:border-amber-500 focus:outline-none"
                />
                <select
                    value={planFilter}
                    onChange={(e) => setPlanFilter(e.target.value)}
                    className="rounded-lg border border-stone-300 px-4 py-2 focus:border-amber-500 focus:outline-none"
                >
                    <option value="">All plans</option>
                    <option value="free">Free</option>
                    <option value="pro">Pro</option>
                    <option value="internal">Internal</option>
                </select>
                <button
                    onClick={fetchUsage}
                    className="rounded-lg bg-amber-600 px-4 py-2 text-white transition hover:bg-amber-700"
                >
                    Refresh
                </button>
            </div>

            {/* Results */}
            {loading ? (
                <div className="text-center text-stone-500">Loading...</div>
            ) : (
                <div className="overflow-x-auto rounded-lg border border-stone-200">
                    <table className="w-full">
                        <thead className="bg-stone-100">
                            <tr>
                                <th className="p-3 text-left text-sm font-semibold text-stone-700">Email</th>
                                <th className="p-3 text-left text-sm font-semibold text-stone-700">Plan</th>
                                <th className="p-3 text-right text-sm font-semibold text-stone-700">Tokens (today)</th>
                                <th className="p-3 text-right text-sm font-semibold text-stone-700">Exports (today)</th>
                                <th className="p-3 text-center text-sm font-semibold text-stone-700">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-stone-200">
                            {users.length === 0 ? (
                                <tr>
                                    <td colSpan={5} className="p-6 text-center text-stone-500">
                                        No users found
                                    </td>
                                </tr>
                            ) : (
                                users.map((user) => (
                                    <UserRow key={user.user_id} user={user} onUpdate={fetchUsage} />
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="mt-4 text-sm text-stone-600">
                Showing {users.length} user{users.length !== 1 ? "s" : ""}
            </div>
        </div>
    )
}

function UserRow({ user, onUpdate }: { user: User; onUpdate: () => void }) {
    const [changing, setChanging] = useState(false)
    const [saving, setSaving] = useState(false)

    const changePlan = async (newPlan: string) => {
        if (newPlan === user.plan) {
            setChanging(false)
            return
        }

        setSaving(true)
        try {
            const res = await fetch(`/api/admin/users/${user.user_id}/plan`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ plan: newPlan }),
            })

            if (res.ok) {
                onUpdate()
                setChanging(false)
            } else {
                alert("Failed to change plan")
            }
        } catch (error) {
            alert("Error changing plan")
        } finally {
            setSaving(false)
        }
    }

    const tokensPct = user.token_usage_pct || 0
    const exportsPct = user.export_usage_pct || 0

    return (
        <tr className="hover:bg-stone-50">
            <td className="p-3 text-sm text-stone-900">{user.email}</td>
            <td className="p-3">
                {changing ? (
                    <select
                        onChange={(e) => changePlan(e.target.value)}
                        defaultValue={user.plan}
                        disabled={saving}
                        className="rounded border border-stone-300 px-2 py-1 text-sm"
                    >
                        <option value="free">Free</option>
                        <option value="pro">Pro</option>
                        <option value="internal">Internal</option>
                    </select>
                ) : (
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase text-amber-900">
                        {user.plan}
                    </span>
                )}
            </td>
            <td className="p-3 text-right">
                <div className="text-sm text-stone-900">
                    {user.tokens_used_today.toLocaleString()} / {user.daily_token_limit.toLocaleString()}
                </div>
                <div className="text-xs text-stone-500">{tokensPct.toFixed(1)}% used</div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-stone-200">
                    <div
                        className={`h-full transition-all ${tokensPct >= 90 ? "bg-red-500" : tokensPct >= 70 ? "bg-amber-500" : "bg-green-500"
                            }`}
                        style={{ width: `${Math.min(tokensPct, 100)}%` }}
                    />
                </div>
            </td>
            <td className="p-3 text-right">
                <div className="text-sm text-stone-900">
                    {user.exports_used_today} / {user.daily_export_limit}
                </div>
                <div className="text-xs text-stone-500">{exportsPct.toFixed(1)}% used</div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-stone-200">
                    <div
                        className={`h-full transition-all ${exportsPct >= 90 ? "bg-red-500" : exportsPct >= 70 ? "bg-amber-500" : "bg-green-500"
                            }`}
                        style={{ width: `${Math.min(exportsPct, 100)}%` }}
                    />
                </div>
            </td>
            <td className="p-3 text-center">
                <button
                    onClick={() => setChanging(!changing)}
                    className="text-sm text-amber-600 hover:text-amber-800"
                    disabled={saving}
                >
                    {changing ? "Cancel" : "Change Plan"}
                </button>
            </td>
        </tr>
    )
}
