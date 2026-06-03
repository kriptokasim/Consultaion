"use client";

import { useState } from "react";
import { Share2, Check, Globe, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { fetchWithAuth } from "@/lib/auth";
import { trackEvent } from "@/lib/analytics";

export function ShareRunButton({ debateId, initiallyPublic = false, modelCount = 0, hasSynthesis = false }: { debateId: string; initiallyPublic?: boolean; modelCount?: number; hasSynthesis?: boolean }) {
    const [isShared, setIsShared] = useState(initiallyPublic);
    const [isSharing, setIsSharing] = useState(false);
    const [copied, setCopied] = useState(false);
    const [showModal, setShowModal] = useState(false);
    const { pushToast } = useToast();

    const handleCopy = () => {
        navigator.clipboard.writeText(window.location.href);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        pushToast({
            title: "Link copied!",
            message: "Anyone with the link can view this run.",
            type: "success"
        });
        trackEvent("arena_share_link_copied", { debate_id: debateId, is_public: isShared });
    };

    const toggleShare = async (makePublic: boolean) => {
        setIsSharing(true);
        try {
            const res = await fetchWithAuth(`/debates/${debateId}/share`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ is_public: makePublic }),
            });

            if (!res.ok) throw new Error("Failed to update share state");
            
            setIsShared(makePublic);
            setShowModal(false);

            if (makePublic) {
                handleCopy();
                trackEvent("arena_share_enabled", { debate_id: debateId, model_count: modelCount, has_synthesis: hasSynthesis, source: "arena_run_view" });
            } else {
                pushToast({
                    title: "Run is now private",
                    message: "This run is private again.",
                    type: "success"
                });
                trackEvent("arena_share_disabled", { debate_id: debateId });
            }
        } catch (err) {
            pushToast({
                title: "Error",
                message: "Could not update share status.",
                type: "error"
            });
        } finally {
            setIsSharing(false);
        }
    };

    return (
        <>
            <Button
                variant="outline"
                size="sm"
                onClick={() => setShowModal(true)}
                disabled={isSharing}
                className={`flex items-center gap-2 ${isShared ? 'bg-primary/10 border-primary/20 text-primary hover:bg-primary/20' : ''}`}
            >
                {isShared ? <Globe className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
                {isShared ? "Public link" : "Share"}
            </Button>

            {showModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4 backdrop-blur-sm">
                    <div className="flex flex-col w-full max-w-sm rounded-2xl border border-border bg-card shadow-smooth-xl p-6">
                        <h3 className="heading-serif text-xl font-semibold text-foreground mb-2">
                            {isShared ? "Manage sharing" : "Make this run public?"}
                        </h3>
                        <p className="text-sm text-muted-foreground mb-6">
                            {isShared 
                                ? "Anyone with this link can view this run." 
                                : "Anyone with the link will be able to view this run. Make sure the prompt and responses do not contain sensitive information."}
                        </p>
                        
                        <div className="flex flex-col gap-3">
                            {isShared ? (
                                <>
                                    <Button onClick={() => { handleCopy(); setShowModal(false); }} className="w-full flex items-center gap-2">
                                        {copied ? <Check className="h-4 w-4" /> : <Globe className="h-4 w-4" />}
                                        {copied ? "Copied" : "Copy public link"}
                                    </Button>
                                    <Button variant="outline" onClick={() => toggleShare(false)} disabled={isSharing} className="w-full text-error hover:text-error hover:bg-error/10 border-error/20 flex items-center gap-2">
                                        <Lock className="h-4 w-4" />
                                        Make private
                                    </Button>
                                </>
                            ) : (
                                <>
                                    <Button onClick={() => toggleShare(true)} disabled={isSharing} className="w-full flex items-center gap-2">
                                        <Globe className="h-4 w-4" />
                                        {isSharing ? "Sharing..." : "Make public and copy link"}
                                    </Button>
                                    <Button variant="ghost" onClick={() => setShowModal(false)} disabled={isSharing} className="w-full">
                                        Cancel
                                    </Button>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
