'use client';

import Link from 'next/link';
import { AlertCircle } from 'lucide-react';

type RateLimitBannerProps = {
    detail?: string;
    resetAt?: string;
    onClose?: () => void;
};

export default function RateLimitNotification({ detail, resetAt, onClose }: RateLimitBannerProps) {
    const formatResetTime = (isoString?: string) => {
        if (!isoString) return null;
        try {
            const date = new Date(isoString);
            return date.toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return null;
        }
    };

    const resetTime = formatResetTime(resetAt);

    return (
        <div className="rounded-2xl border border-red-200 bg-gradient-to-r from-red-50 to-orange-50 p-4 shadow-md">
            <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                    <h3 className="text-sm font-semibold text-red-900">Rate Limit Reached</h3>
                    <p className="mt-1 text-sm text-red-800">
                        {detail || "You've reached your usage limit for now."}
                        {resetTime && ` Your limit will reset at ${resetTime}.`}
                    </p>
                    <div className="mt-3 flex items-center gap-3">
                        <Link
                            href="/pricing"
                            className="inline-flex items-center rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-700 transition-colors"
                        >
                            Upgrade Plan
                        </Link>
                        {onClose && (
                            <button
                                onClick={onClose}
                                className="text-sm font-medium text-red-700 hover:text-red-900 transition-colors"
                            >
                                Dismiss
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
