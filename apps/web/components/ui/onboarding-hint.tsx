"use client";

import { useState, useEffect } from "react";
import { X, Lightbulb } from "lucide-react";

interface OnboardingHintProps {
    id: string;
    text: string;
    className?: string;
}

export function OnboardingHint({ id, text, className = "" }: OnboardingHintProps) {
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        if (typeof window !== "undefined") {
            const dismissed = localStorage.getItem(`consultaion_hint_${id}_dismissed`);
            if (!dismissed) {
                setIsVisible(true);
            }
        }
    }, [id]);

    const handleDismiss = () => {
        setIsVisible(false);
        if (typeof window !== "undefined") {
            localStorage.setItem(`consultaion_hint_${id}_dismissed`, "true");
        }
    };

    if (!isVisible) return null;

    return (
        <div className={`relative flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-900 shadow-sm backdrop-blur-sm ${className}`}>
            <Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <p className="flex-1">{text}</p>
            <button
                onClick={handleDismiss}
                className="shrink-0 rounded-full p-1 text-amber-700 hover:bg-amber-100"
                aria-label="Dismiss hint"
            >
                <X className="h-3 w-3" />
            </button>
        </div>
    );
}
