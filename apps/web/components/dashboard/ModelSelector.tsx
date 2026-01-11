"use client";

import { cn } from "@/lib/utils";
import { Bot, Zap, Brain, Sparkles } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";
import { ModelSelectorSkeleton } from "@/components/ui/skeleton";

type ModelOption = {
    id: string;
    display_name: string;
    provider: string;
    tags: string[];
    recommended: boolean;
    tier?: "standard" | "advanced";
};

// Map providers/tags to icons
function getModelIcon(model: ModelOption) {
    const iconClass = "h-5 w-5";
    if (model.tags?.includes("fast")) return <Zap className={iconClass} />;
    if (model.tags?.includes("reasoning")) return <Brain className={iconClass} />;
    if (model.provider === "openai") return <Sparkles className={iconClass} />;
    return <Bot className={iconClass} />;
}

// Derive capability label from tags
function getCapabilityLabel(model: ModelOption, t: (key: string) => string): string {
    if (model.tags?.includes("reasoning")) return t("dashboard.model.reasoning");
    if (model.tags?.includes("fast")) return t("dashboard.model.fast");
    if (model.tags?.includes("balanced")) return t("dashboard.model.balanced");
    return t("dashboard.model.general");
}

interface ModelSelectorProps {
    models: ModelOption[];
    selectedModel: string | null;
    onSelect: (modelId: string) => void;
    allowedTiers: string[];
}

export function ModelSelector({ models, selectedModel, onSelect, allowedTiers }: ModelSelectorProps) {
    const { t } = useI18n();

    if (models.length === 0) {
        return <ModelSelectorSkeleton />;
    }

    if (models.length === 1) {
        return (
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-900">
                {getModelIcon(models[0])}
                {models[0].display_name}
            </div>
        );
    }

    return (
        <div className="grid gap-2 sm:grid-cols-2">
            {models.map((model) => {
                const isAllowed = allowedTiers.includes(model.tier || "standard");
                const isSelected = model.id === selectedModel;

                return (
                    <button
                        key={model.id}
                        type="button"
                        onClick={() => isAllowed && onSelect(model.id)}
                        disabled={!isAllowed}
                        className={cn(
                            "group relative flex items-start gap-3 rounded-xl border-2 p-3 text-left transition-all duration-200",
                            isSelected
                                ? "border-amber-500 bg-amber-50 shadow-[0_4px_12px_rgba(255,190,92,0.25)]"
                                : "border-amber-100 bg-white hover:border-amber-300 hover:bg-amber-50/50",
                            !isAllowed && "cursor-not-allowed opacity-50"
                        )}
                    >
                        {/* Selection indicator */}
                        <div
                            className={cn(
                                "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all",
                                isSelected
                                    ? "border-amber-500 bg-amber-500"
                                    : "border-amber-200 bg-white group-hover:border-amber-400"
                            )}
                        >
                            {isSelected && (
                                <div className="h-2 w-2 rounded-full bg-white" />
                            )}
                        </div>

                        {/* Icon */}
                        <span
                            className={cn(
                                "rounded-lg p-2 transition-colors",
                                isSelected
                                    ? "bg-amber-100 text-amber-700"
                                    : "bg-stone-100 text-stone-600 group-hover:bg-amber-100 group-hover:text-amber-700"
                            )}
                        >
                            {getModelIcon(model)}
                        </span>

                        {/* Content */}
                        <div className="flex-1 min-w-0 text-left">
                            <p
                                className={cn(
                                    "text-sm font-semibold leading-tight mb-1.5",
                                    isSelected ? "text-amber-900" : "text-[#3a2a1a]"
                                )}
                            >
                                {model.display_name}
                            </p>
                            <div className="flex flex-wrap items-center gap-2 mb-1">
                                {model.recommended && (
                                    <span className="shrink-0 rounded-full bg-amber-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
                                        {t("dashboard.modal.recommendedTag")}
                                    </span>
                                )}
                                {!isAllowed && (
                                    <span className="shrink-0 rounded-full bg-stone-200 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-stone-600">
                                        Pro
                                    </span>
                                )}
                            </div>
                            <p className="text-xs text-stone-500">
                                {getCapabilityLabel(model, t)}
                            </p>
                        </div>
                    </button>
                );
            })}
        </div>
    );
}
