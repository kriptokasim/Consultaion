"use client"

import { useState, useEffect } from "react"
import { useI18n } from "@/lib/i18n/client"
import Link from "next/link"

interface User {
    id: string
    email: string
    display_name: string | null
    plan: string
    created_at: string | null
    is_active: boolean
}

export default function AdminUsersPage() {
    const { t } = useI18n()
    const [users, setUsers] = useState<User[]>([])
    const [loading, setLoading] = useState(false)
    const [searchQuery, setSearchQuery] = useState("")

    const fetchUsers = async () => {
        if (!searchQuery.trim()) {
            setUsers([])
            return
        }

        setLoading(true)
        try {
            const params = new URLSearchParams({ email: searchQuery })
            const res = await fetch(`/api/admin/users?${params}`)
            const data = await res.json()
            setUsers(data.users || [])
        } catch (error) {
            console.error("Failed to fetch users:", error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        const timer = setTimeout(() => {
            if (searchQuery.length >= 2) {
                fetchUsers()
            }
        }, 300)
        return () => clearTimeout(timer)
    }, [searchQuery])

    return (
        <div className="container mx-auto p-6">
            {/* Header */}
            <div className="mb-8">
                <h1 className="mb-2 text-3xl font-bold text-stone-900">User Management</h1>
                <p className="text-stone-600">Search and manage user accounts</p>
            </div>

            {/* Search */}
            <div className="mb-6">
                <input
                    type="text"
                    placeholder="Search by email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full max-w-md rounded-lg border border-stone-300 px-4 py-3 focus:border-amber-500 focus:outline-none"
                />
            </div>

            {/* Results */}
            {loading ? (
                <div className="text-center text-stone-500">Searching...</div>
            ) : users.length === 0 ? (
                <div className="rounded-lg border border-stone-200 bg-stone-50 p-8 text-center text-stone-500">
                    {searchQuery.length >= 2
                        ? "No users found. Try a different search."
                        : "Enter at least 2 characters to search"}
                </div>
            ) : (
                <div className="overflow-hidden rounded-lg border border-stone-200 shadow-sm">
                    <table className="w-full">
                        <thead className="bg-stone-100">
                            <tr>
                                <th className="p-4 text-left text-sm font-semibold text-stone-700">Email</th>
                                <th className="p-4 text-left text-sm font-semibold text-stone-700">Plan</th>
                                <th className="p-4 text-left text-sm font-semibold text-stone-700">Status</th>
                                <th className="p-4 text-left text-sm font-semibold text-stone-700">Created</th>
                                <th className="p-4 text-center text-sm font-semibold text-stone-700">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-stone-200">
                            {users.map((user) => (
                                <tr key={user.id} className="hover:bg-stone-50">
                                    <td className="p-4">
                                        <div className="font-medium text-stone-900">{user.email}</div>
                                        {user.display_name && (
                                            <div className="text-sm text-stone-500">{user.display_name}</div>
                                        )}
                                    </td>
                                    <td className="p-4">
                                        <span className="inline-block rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase text-amber-900">
                                            {user.plan}
                                        </span>
                                    </td>
                                    <td className="p-4">
                                        <span
                                            className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${user.is_active
                                                    ? "bg-green-100 text-green-800"
                                                    : "bg-red-100 text-red-800"
                                                }`}
                                        >
                                            {user.is_active ? "Active" : "Disabled"}
                                        </span>
                                    </td>
                                    <td className="p-4 text-sm text-stone-600">
                                        {user.created_at
                                            ? new Date(user.created_at).toLocaleDateString()
                                            : "N/A"}
                                    </td>
                                    <td className="p-4 text-center">
                                        <Link
                                            href={`/admin/users/${user.id}`}
                                            className="inline-block rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-700"
                                        >
                                            View Details
                                        </Link>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="mt-4 text-sm text-stone-600">
                {users.length > 0 && `Showing ${users.length} result${users.length !== 1 ? "s" : ""}`}
            </div>
        </div>
    )
}
