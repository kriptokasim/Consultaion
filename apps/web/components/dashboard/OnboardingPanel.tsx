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
            className={`relative mb-8 overflow-hidden rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-6 shadow-sm transition-all duration-300 ${isVisible ? "translate-y-0 opacity-100" : "-translate-y-4 opacity-0"
                }`}
        >
            <button
                onClick={handleDismiss}
                className="absolute right-4 top-4 rounded-full p-1 text-amber-900/40 hover:bg-amber-100 hover:text-amber-900"
                title={t("onboarding.dashboard.dismiss")}
            >
                <X className="h-4 w-4" />
            </button>

            <div className="mb-6">
                <h2 className="text-xl font-bold text-[#3a2a1a]">{t("onboarding.dashboard.title")}</h2>
                <p className="text-[#5a4a3a]">{t("onboarding.dashboard.subtitle")}</p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
                {/* Step 1: Templates */}
                <div className="rounded-xl border border-amber-100 bg-white/80 p-4 transition hover:border-amber-200 hover:shadow-md">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
                        <LayoutTemplate className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-[#3a2a1a]">{t("onboarding.dashboard.step1.title")}</h3>
                    <p className="mb-4 text-sm text-[#5a4a3a]">{t("onboarding.dashboard.step1.description")}</p>
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full border-amber-200 text-amber-800 hover:bg-amber-50 hover:text-amber-900"
                        onClick={() => handleStepClick("template", onOpenTemplates)}
                    >
                        {t("onboarding.dashboard.step1.cta")}
                    </Button>
                </div>

                {/* Step 2: Demo */}
                <div className="rounded-xl border border-amber-100 bg-white/80 p-4 transition hover:border-amber-200 hover:shadow-md">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
                        <Play className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-[#3a2a1a]">{t("onboarding.dashboard.step2.title")}</h3>
                    <p className="mb-4 text-sm text-[#5a4a3a]">{t("onboarding.dashboard.step2.description")}</p>
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-full border-amber-200 text-amber-800 hover:bg-amber-50 hover:text-amber-900"
                        asChild
                        onClick={() => trackEvent("onboarding_step_clicked", { location: "dashboard", step: "demo" })}
                    >
                        <Link href="/demo">{t("onboarding.dashboard.step2.cta")}</Link>
                    </Button>
                </div>

                {/* Step 3: Custom */}
                <div className="rounded-xl border border-amber-100 bg-white/80 p-4 transition hover:border-amber-200 hover:shadow-md">
                    <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
                        <Plus className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-[#3a2a1a]">{t("onboarding.dashboard.step3.title")}</h3>
                    <p className="mb-4 text-sm text-[#5a4a3a]">{t("onboarding.dashboard.step3.description")}</p>
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
