"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n/client";
import { trackEvent } from "@/lib/analytics";
import { X, LayoutTemplate, Play, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";

interface OnboardingPanelProps {
    onDismiss: () => void;
    onOpenTemplates: () => void;
    onNewDebate: () => void;
}

export function OnboardingPanel({ onDismiss, onOpenTemplates, onNewDebate }: OnboardingPanelProps) {
    const { t } = useI18n();
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        // Small delay for animation
        const timer = setTimeout(() => setIsVisible(true), 100);
        trackEvent("onboarding_panel_shown", { location: "dashboard" });
        return () => clearTimeout(timer);
    }, []);

    const handleDismiss = () => {
        setIsVisible(false);
        trackEvent("onboarding_panel_dismissed", { location: "dashboard" });
        setTimeout(onDismiss, 300); // Wait for animation
    };

    const handleStepClick = (step: string, action: () => void) => {
        trackEvent("onboarding_step_clicked", { location: "dashboard", step });
        action();
    };

    return (
        <div
            className={`relative mb-8 overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-6 shadow-sm transition-all duration-300 dark:border-slate-700 dark:from-slate-800 dark:to-slate-900 ${isVisible ? "translate-y-0 opacity-100" : "-translate-y-4 opacity-0"
                }`}
        >
            <button
                onClick={handleDismiss}
                className="absolute right-4 top-4 rounded-full p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-white"
                title={t("onboarding.dashboard.dismiss")}
            >
                <X className="h-4 w-4" />
            </button>

            <div className="mb-6">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">{t("onboarding.dashboard.title")}</h2>
                <p className="text-slate-600 dark:text-slate-300">{t("onboarding.dashboard.subtitle")}</p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
                {/* Step 1: Templates */}
                <div className="rounded-xl border border-slate-200 bg-white/80 p-4 transition hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">
                        <LayoutTemplate className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">{t("onboarding.dashboard.step1.title")}</h3>
                    <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">{t("onboarding.dashboard.step1.description")}</p>
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full"
                        onClick={() => handleStepClick("template", onOpenTemplates)}
                    >
                        {t("onboarding.dashboard.step1.cta")}
                    </Button>
                </div>

                {/* Step 2: Demo */}
                <div className="rounded-xl border border-slate-200 bg-white/80 p-4 transition hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">
                        <Play className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">{t("onboarding.dashboard.step2.title")}</h3>
                    <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">{t("onboarding.dashboard.step2.description")}</p>
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full"
                        asChild
                        onClick={() => trackEvent("onboarding_step_clicked", { location: "dashboard", step: "demo" })}
                    >
                        <Link href="/demo">{t("onboarding.dashboard.step2.cta")}</Link>
                    </Button>
                </div>

                {/* Step 3: Custom */}
                <div className="rounded-xl border border-slate-200 bg-white/80 p-4 transition hover:border-slate-300 hover:shadow-md dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-600">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300">
                        <Plus className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">{t("onboarding.dashboard.step3.title")}</h3>
                    <p className="mb-4 text-sm text-slate-600 dark:text-slate-300">{t("onboarding.dashboard.step3.description")}</p>
                    <Button
                        variant="amber"
                        size="sm"
                        className="w-full"
                        onClick={() => handleStepClick("custom", onNewDebate)}
                    >
                        {t("onboarding.dashboard.step3.cta")}
                    </Button>
                </div>
            </div>
        </div>
    );
}
