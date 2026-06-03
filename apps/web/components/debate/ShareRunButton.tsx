"use client";

import { useState } from "react";
import { Share2, Check, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { fetchWithAuth } from "@/lib/auth";

export function ShareRunButton({ debateId, initiallyPublic = false }: { debateId: string; initiallyPublic?: boolean }) {
    const [isShared, setIsShared] = useState(initiallyPublic);
    const [isSharing, setIsSharing] = useState(false);
    const [copied, setCopied] = useState(false);
    const { pushToast } = useToast();

    const handleShare = async () => {
        if (isShared) {
            // Already shared, just copy link
            navigator.clipboard.writeText(window.location.href);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
            pushToast({
                title: "Link copied!",
                message: "Anyone with the link can view this run.",
                type: "success"
            });
            return;
        }

        setIsSharing(true);
        try {
            const res = await fetchWithAuth(`/debates/${debateId}/share`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_public: true }),
            });

            if (!res.ok) throw new Error("Failed to share run");
            
            setIsShared(true);
            navigator.clipboard.writeText(window.location.href);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
            
            pushToast({
                title: "Run is now public!",
                message: "Link copied to clipboard.",
                type: "success"
            });
        } catch (err) {
            pushToast({
                title: "Error",
                message: "Could not share this run.",
                type: "error"
            });
        } finally {
            setIsSharing(false);
        }
    };

    return (
        <Button
            variant="outline"
            size="sm"
            onClick={handleShare}
            disabled={isSharing}
            className={`flex items-center gap-2 ${isShared ? 'bg-primary/10 border-primary/20 text-primary hover:bg-primary/20' : ''}`}
        >
            {copied ? (
                <Check className="h-4 w-4" />
            ) : isShared ? (
                <Globe className="h-4 w-4" />
            ) : (
                <Share2 className="h-4 w-4" />
            )}
            {copied ? "Copied" : isShared ? "Public Link" : "Share"}
        </Button>
    );
}
