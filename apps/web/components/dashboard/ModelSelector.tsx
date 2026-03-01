"use client";

import { cn } from "@/lib/utils";
import { Bot, Zap, Brain, Sparkles } from "lucide-react";
import { useI18n } from "@/lib/i18n/client";
import { ModelSelectorSkeleton } from "@/components/ui/skeleton";
import { getModelAvatarUrl } from "@/lib/avatar";

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
    const iconClass = "h-5 w-5 object-contain";
    const logoUrl = getModelAvatarUrl(model.display_name) || getModelAvatarUrl(model.provider);

    // If it maps to one of our static brand logos, use it
    if (logoUrl && logoUrl.startsWith('/logos/')) {
        return <img src={logoUrl} alt={model.provider} className={iconClass} />;
    }

    if (model.tags?.includes("fast")) return <Zap className="h-5 w-5" />;
    if (model.tags?.includes("reasoning")) return <Brain className="h-5 w-5" />;
    if (model.provider === "openai") return <Sparkles className="h-5 w-5" />;
    return <Bot className="h-5 w-5" />;
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
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-semibold text-primary">
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
                            "group relative flex items-start gap-3 rounded-xl border-2 p-3 text-left transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2",
                            isSelected
                                ? "border-primary bg-primary/5 shadow-smooth"
                                : "border-border bg-card hover:border-primary/50 hover:bg-primary/5",
                            !isAllowed && "cursor-not-allowed opacity-50"
                        )}
                    >
                        {/* Selection indicator */}
                        <div
                            className={cn(
                                "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all",
                                isSelected
                                    ? "border-primary bg-primary"
                                    : "border-border bg-card group-hover:border-primary/50"
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
                                    ? "bg-primary/10 text-primary"
                                    : "bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary"
                            )}
                        >
                            {getModelIcon(model)}
                        </span>

                        {/* Content */}
                        <div className="flex-1 min-w-0 text-left">
                            <p
                                className={cn(
                                    "text-sm font-semibold leading-tight mb-1.5",
                                    isSelected ? "text-primary" : "text-foreground"
                                )}
                            >
                                {model.display_name}
                            </p>
                            <div className="flex flex-wrap items-center gap-2 mb-1">
                                {model.recommended && (
                                    <span className="shrink-0 rounded-full bg-accent-secondary/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-accent-secondary">
                                        {t("dashboard.modal.recommendedTag")}
                                    </span>
                                )}
                                {!isAllowed && (
                                    <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                                        Pro
                                    </span>
                                )}
                            </div>
                            <p className="text-xs text-muted-foreground">
                                {getCapabilityLabel(model, t)}
                            </p>
                        </div>
                    </button>
                );
            })}
        </div>
    );
}
