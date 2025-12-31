"use client"

import { useState } from "react"
import { Switch } from "@/components/ui/switch"
import { apiRequest } from "@/lib/apiClient"
import { useRouter } from "next/navigation"

interface NotificationSettingsProps {
    initialEnabled: boolean
}

export function NotificationSettings({ initialEnabled }: NotificationSettingsProps) {
    const [enabled, setEnabled] = useState(initialEnabled)
    const [loading, setLoading] = useState(false)
    const router = useRouter()

    const handleToggle = async (checked: boolean) => {
        setEnabled(checked)
        setLoading(true)
        try {
            await apiRequest({
                method: "PUT",
                path: "/me/profile",
                body: { email_summaries_enabled: checked },
            })
            router.refresh()
        } catch (error) {
            console.error("Failed to update notification settings", error)
            setEnabled(!checked) // Revert
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="card-elevated max-w-2xl space-y-4 p-6">
            <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                    <h3 className="heading-serif text-lg font-semibold text-slate-900 dark:text-white">
                        Email Summaries
                    </h3>
                    <p className="text-sm text-slate-600 dark:text-slate-300">
                        Receive a summary email after each debate completes.
                    </p>
                </div>
                <Switch
                    checked={enabled}
                    onCheckedChange={handleToggle}
                    disabled={loading}
                />
            </div>
        </div>
    )
}
