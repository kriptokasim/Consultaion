"use client";

import { PromotionArea } from "@/components/PromotionArea";
import { Button } from "@/components/ui/button";

interface BillingLimitModalProps {
  open: boolean;
  code?: string;
  onClose: () => void;
}

const copy: Record<string, { title: string; message: string }> = {
  BILLING_LIMIT_DEBATES: {
    title: "Monthly debates reached",
    message: "You have used all debates included in your current plan. Upgrade to unlock more instant runs.",
  },
  BILLING_LIMIT_EXPORTS: {
    title: "Exports disabled",
    message: "Exports require the Pro plan. Upgrade to download transcripts and reports.",
  },
};

export function BillingLimitModal({ open, code, onClose }: BillingLimitModalProps) {
  if (!open) return null;
  const content = code && copy[code] ? copy[code] : copy.BILLING_LIMIT_DEBATES;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-2xl border border-amber-200 bg-white p-6 shadow-xl">
        <h3 className="heading-serif text-2xl text-[#3a2a1a]">{content.title}</h3>
        <p className="mt-2 text-sm text-[#5a4a3a]">{content.message}</p>
        <div className="mt-4 space-x-2">
          <Button asChild variant="secondary" className="bg-stone-100 text-stone-900">
            <a href="/pricing">View pricing</a>
          </Button>
          <Button asChild className="bg-amber-600 text-white hover:bg-amber-700">
            <a href="/settings/billing">Manage plan</a>
          </Button>
        </div>
        <div className="mt-5">
          <PromotionArea location="debate_limit_modal" />
        </div>
        <button type="button" className="mt-4 text-xs text-stone-500" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
