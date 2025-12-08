"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useI18n } from "@/lib/i18n/client"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/toast"
import { apiRequest } from "@/lib/apiClient"
import { setAnalyticsOptOut } from "@/lib/analytics"

interface PrivacySettingsProps {
    initialOptOut: boolean
}

export function PrivacySettings({ initialOptOut }: PrivacySettingsProps) {
    const { t } = useI18n()
    const router = useRouter()
    const { pushToast } = useToast()
    const [optOut, setOptOut] = useState(initialOptOut)
    const [isDeleting, setIsDeleting] = useState(false)
    const [showDeleteDialog, setShowDeleteDialog] = useState(false)

    const handleToggleAnalytics = async (checked: boolean) => {
        setOptOut(checked)
        // Update local state immediately for fast feedback
        setAnalyticsOptOut(checked)

        try {
            await apiRequest({
                method: "POST",
                path: "/me/privacy",
                body: { analytics_opt_out: checked }
            })
            pushToast({ title: t("settings.privacy.updated"), variant: "success" })
            router.refresh()
        } catch (error) {
            setOptOut(!checked) // Revert
            setAnalyticsOptOut(!checked)
            pushToast({ title: t("errors.generic"), variant: "error" })
        }
    }

    const handleDeleteAccount = async () => {
        setIsDeleting(true)
        try {
            await apiRequest({
                method: "POST",
                path: "/me/delete-account",
                body: {}
            })
            pushToast({ title: t("settings.privacy.deleteAccount.success"), variant: "success" })
            // Redirect to home/login after deletion
            window.location.href = "/"
        } catch (error) {
            setIsDeleting(false)
            setShowDeleteDialog(false)
            pushToast({ title: t("errors.generic"), variant: "error" })
        }
    }

    return (
        <div className="card-elevated space-y-6 p-6">
            <div>
                <h2 className="text-lg font-semibold text-amber-950 dark:text-amber-50">
                    {t("settings.privacy.title")}
                </h2>
                <p className="text-sm text-amber-900/70 dark:text-amber-100/70">
                    {t("settings.privacy.description")}
                </p>
            </div>

            <div className="space-y-4">
                {/* Analytics Toggle */}
                <div className="flex items-center justify-between">
                    <div className="space-y-0.5">
                        <label className="text-sm font-medium text-amber-900 dark:text-amber-100">
                            {t("settings.privacy.analyticsLabel")}
                        </label>
                        <p className="text-xs text-amber-900/60 dark:text-amber-100/60">
                            {t("settings.privacy.analyticsDescription")}
                        </p>
                    </div>
                    <Switch
                        checked={!optOut}
                        onCheckedChange={(checked) => handleToggleAnalytics(!checked)}
                    />
                </div>

                <div className="border-t border-amber-200/30 dark:border-amber-800/30 pt-4">
                    <div className="flex items-center justify-between">
                        <div className="space-y-0.5">
                            <label className="text-sm font-medium text-red-600 dark:text-red-400">
                                {t("settings.privacy.deleteAccount.title")}
                            </label>
                            <p className="text-xs text-amber-900/60 dark:text-amber-100/60">
                                {t("settings.privacy.deleteAccount.description")}
                            </p>
                        </div>

                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setShowDeleteDialog(true)}
                        >
                            {t("settings.privacy.deleteAccount.button")}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Custom Delete Confirmation Modal */}
            {showDeleteDialog && (
                <>
                    <div
                        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
                        onClick={() => !isDeleting && setShowDeleteDialog(false)}
                    />
                    <div className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-amber-200 bg-white p-6 shadow-xl dark:border-amber-800 dark:bg-stone-900">
                        <h3 className="text-lg font-semibold text-amber-950 dark:text-amber-50">
                            {t("settings.privacy.deleteAccount.title")}
                        </h3>
                        <p className="mt-2 text-sm text-amber-900/70 dark:text-amber-100/70">
                            {t("settings.privacy.deleteAccount.confirmation")}
                        </p>
                        <div className="mt-6 flex justify-end gap-3">
                            <Button
                                variant="outline"
                                onClick={() => setShowDeleteDialog(false)}
                                disabled={isDeleting}
                            >
                                {t("cancel")}
                            </Button>
                            <Button
                                variant="destructive"
                                onClick={handleDeleteAccount}
                                disabled={isDeleting}
                            >
                                {isDeleting ? t("processing") : t("confirm")}
                            </Button>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
