"use client";

import { useState } from "react";
import { Share2, Check, Globe, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { fetchWithAuth } from "@/lib/auth";
import { trackEvent } from "@/lib/analytics";
import * as Dialog from "@radix-ui/react-dialog";

export function ShareRunButton({ debateId, initiallyPublic = false, modelCount = 0, hasSynthesis = false }: { debateId: string; initiallyPublic?: boolean; modelCount?: number; hasSynthesis?: boolean }) {
    const [isShared, setIsShared] = useState(initiallyPublic);
    const [isSharing, setIsSharing] = useState(false);
    const [copied, setCopied] = useState(false);
    const [open, setOpen] = useState(false);
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
            setOpen(false);

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

    const dialogTitle = isShared ? "Manage sharing" : "Make this run public?";
    const dialogDescription = isShared
        ? "Anyone with this link can view this run."
        : "Anyone with the link will be able to view this run. Make sure the prompt and responses do not contain sensitive information.";

    return (
        <Dialog.Root open={open} onOpenChange={setOpen}>
            <Dialog.Trigger asChild>
                <Button
                    variant="outline"
                    size="sm"
                    disabled={isSharing}
                    className={`flex items-center gap-2 ${isShared ? 'bg-primary/10 border-primary/20 text-primary hover:bg-primary/20' : ''}`}
                >
                    {isShared ? <Globe className="h-4 w-4" /> : <Share2 className="h-4 w-4" />}
                    {isShared ? "Public link" : "Share"}
                </Button>
            </Dialog.Trigger>

            <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
                <Dialog.Content
                    className="fixed left-[50%] top-[50%] z-50 w-full max-w-sm translate-x-[-50%] translate-y-[-50%] rounded-2xl border border-border bg-card shadow-smooth-xl p-6 focus:outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]"
                    aria-describedby="share-dialog-description"
                >
                    <Dialog.Title className="heading-serif text-xl font-semibold text-foreground mb-2">
                        {dialogTitle}
                    </Dialog.Title>
                    <Dialog.Description id="share-dialog-description" className="text-sm text-muted-foreground mb-6">
                        {dialogDescription}
                    </Dialog.Description>
                    
                    <div className="flex flex-col gap-3">
                        {isShared ? (
                            <>
                                <Button onClick={() => { handleCopy(); setOpen(false); }} className="w-full flex items-center gap-2">
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
                                <Dialog.Close asChild>
                                    <Button variant="ghost" disabled={isSharing} className="w-full">
                                        Cancel
                                    </Button>
                                </Dialog.Close>
                            </>
                        )}
                    </div>
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    );
}
