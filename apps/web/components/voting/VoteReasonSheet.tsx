/**
 * Patchset 76: VoteReasonSheet component
 * 
 * Optional post-vote micro-sheet for structured feedback.
 * Shows reason buttons and confidence selector.
 * Dismissible with zero friction.
 */
"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { X, Lightbulb, CheckCircle, List, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export type VoteReasonType = "clarity" | "correctness" | "completeness" | "creativity";
export type ConfidenceLevel = 1 | 2 | 3;

interface VoteReasonSheetProps {
    /** Whether the sheet is open */
    open: boolean;
    /** Called when sheet is closed/dismissed */
    onClose: () => void;
    /** Called when reason is submitted */
    onSubmit?: (data: { reason?: VoteReasonType; confidence?: ConfidenceLevel }) => void;
    /** Additional class names */
    className?: string;
}

const REASONS: { id: VoteReasonType; label: string; labelTr: string; icon: React.ReactNode }[] = [
    { id: "clarity", label: "Clarity", labelTr: "Netlik", icon: <Lightbulb className="h-4 w-4" /> },
    { id: "correctness", label: "Correctness", labelTr: "Doğruluk", icon: <CheckCircle className="h-4 w-4" /> },
    { id: "completeness", label: "Completeness", labelTr: "Bütünlük", icon: <List className="h-4 w-4" /> },
    { id: "creativity", label: "Creativity", labelTr: "Yaratıcılık", icon: <Sparkles className="h-4 w-4" /> },
];

const CONFIDENCE_LEVELS: { value: ConfidenceLevel; label: string; labelTr: string }[] = [
    { value: 1, label: "Unsure", labelTr: "Emin değilim" },
    { value: 2, label: "Confident", labelTr: "Eminim" },
    { value: 3, label: "Very confident", labelTr: "Çok eminim" },
];

export function VoteReasonSheet({
    open,
    onClose,
    onSubmit,
    className,
}: VoteReasonSheetProps) {
    const [selectedReason, setSelectedReason] = useState<VoteReasonType | undefined>();
    const [confidence, setConfidence] = useState<ConfidenceLevel | undefined>();

    const handleSubmit = useCallback(() => {
        onSubmit?.({ reason: selectedReason, confidence });
        onClose();
    }, [selectedReason, confidence, onSubmit, onClose]);

    const handleSkip = useCallback(() => {
        onSubmit?.({});
        onClose();
    }, [onSubmit, onClose]);

    if (!open) return null;

    return (
        <div
            className={cn(
                "fixed inset-x-0 bottom-0 z-50 animate-in slide-in-from-bottom-4 duration-300",
                "bg-white/95 backdrop-blur-sm border-t border-slate-200 shadow-lg",
                "p-4 pb-6 rounded-t-2xl",
                className
            )}
            role="dialog"
            aria-modal="true"
            aria-labelledby="vote-reason-title"
        >
            {/* Close button */}
            <button
                onClick={onClose}
                className="absolute top-3 right-3 p-1 rounded-full hover:bg-slate-100 transition-colors"
                aria-label="Close"
            >
                <X className="h-5 w-5 text-slate-400" />
            </button>

            <div className="max-w-md mx-auto space-y-4">
                {/* Header */}
                <div className="text-center">
                    <h3 id="vote-reason-title" className="text-sm font-medium text-slate-900">
                        Oyunuzun nedenini paylaşmak ister misiniz?
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">
                        İsteğe bağlı - yanıtları iyileştirmemize yardımcı olur
                    </p>
                </div>

                {/* Reason buttons */}
                <div className="flex flex-wrap justify-center gap-2">
                    {REASONS.map((reason) => (
                        <button
                            key={reason.id}
                            onClick={() => setSelectedReason(
                                selectedReason === reason.id ? undefined : reason.id
                            )}
                            className={cn(
                                "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium",
                                "border transition-all",
                                selectedReason === reason.id
                                    ? "bg-amber-100 border-amber-300 text-amber-800"
                                    : "bg-white border-slate-200 text-slate-600 hover:border-slate-300"
                            )}
                            aria-pressed={selectedReason === reason.id}
                        >
                            {reason.icon}
                            <span>{reason.labelTr}</span>
                        </button>
                    ))}
                </div>

                {/* Confidence selector */}
                <div className="flex justify-center gap-1">
                    {CONFIDENCE_LEVELS.map((level) => (
                        <button
                            key={level.value}
                            onClick={() => setConfidence(
                                confidence === level.value ? undefined : level.value
                            )}
                            className={cn(
                                "px-3 py-1 rounded-full text-xs transition-all",
                                confidence === level.value
                                    ? "bg-slate-800 text-white"
                                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                            )}
                            aria-pressed={confidence === level.value}
                        >
                            {level.labelTr}
                        </button>
                    ))}
                </div>

                {/* Actions */}
                <div className="flex justify-center gap-2 pt-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleSkip}
                        className="text-slate-500"
                    >
                        Atla
                    </Button>
                    <Button
                        size="sm"
                        onClick={handleSubmit}
                        disabled={!selectedReason && !confidence}
                        className="bg-amber-500 hover:bg-amber-600 text-white"
                    >
                        Gönder
                    </Button>
                </div>
            </div>
        </div>
    );
}

export default VoteReasonSheet;
