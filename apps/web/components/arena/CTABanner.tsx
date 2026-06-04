"use client";

import React from "react";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { trackEvent } from "@/lib/analytics";

interface CTABannerProps {
    debateId: string;
    variant: "top" | "footer";
}

/**
 * Top CTA banner for public runs — compact inline.
 */
export function PublicRunCTATop({ debateId }: { debateId: string }) {
    return (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>
                <h3 className="font-semibold text-foreground text-sm">Want to compare models yourself?</h3>
                <p className="text-muted-foreground text-sm mt-0.5">Run prompts across multiple models and get a synthesized answer.</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
                <Button asChild variant="outline" size="sm" onClick={() => trackEvent("public_run_cta_clicked", { debate_id: debateId, cta_location: "top_banner_run_same", is_authenticated: false, intent: "run_same_prompt" })}>
                    <Link href={`/login?next=${encodeURIComponent(`/live?prefill_prompt_from=${debateId}&source=public_run`)}`}>
                        <Play className="h-3.5 w-3.5 mr-1.5" />
                        Run this prompt yourself
                    </Link>
                </Button>
                <Button asChild size="sm" onClick={() => trackEvent("public_run_cta_clicked", { debate_id: debateId, cta_location: "top_banner", is_authenticated: false, intent: "create_own_run" })}>
                    <Link href={`/login?next=${encodeURIComponent(`/live?source=public_run`)}`}>
                        Create your own run
                    </Link>
                </Button>
            </div>
        </div>
    );
}

/**
 * Footer CTA banner for public runs — prominent dark card.
 */
export function PublicRunCTAFooter({ debateId }: { debateId: string }) {
    return (
        <div className="mt-8 rounded-2xl bg-slate-900 px-6 py-10 text-center flex flex-col items-center justify-center">
            <h3 className="text-xl font-semibold text-white mb-2">Want to compare AI models on your own question?</h3>
            <p className="text-slate-400 max-w-md mb-6">
                Run the same prompt across multiple models, compare the answers, and get one synthesized result.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
                <Button asChild size="lg" className="bg-primary text-primary-foreground hover:bg-primary/90" onClick={() => trackEvent("public_run_cta_clicked", { debate_id: debateId, cta_location: "footer", is_authenticated: false, intent: "create_own_run" })}>
                    <Link href={`/login?next=${encodeURIComponent(`/live?source=public_run`)}`}>
                        Start your own Arena run
                    </Link>
                </Button>
                <Button asChild size="lg" variant="outline" className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white bg-transparent" onClick={() => trackEvent("public_run_cta_clicked", { debate_id: debateId, cta_location: "footer_run_same", is_authenticated: false, intent: "run_same_prompt" })}>
                    <Link href={`/login?next=${encodeURIComponent(`/live?prefill_prompt_from=${debateId}&source=public_run`)}`}>
                        <Play className="h-4 w-4 mr-2" />
                        Run this prompt yourself
                    </Link>
                </Button>
                <Button asChild variant="ghost" size="lg" className="text-slate-400 hover:text-white">
                    <Link href="/">
                        See how it works
                    </Link>
                </Button>
            </div>
        </div>
    );
}
