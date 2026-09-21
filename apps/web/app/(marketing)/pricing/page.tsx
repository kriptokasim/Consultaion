import { BroadsheetPricing } from "@/components/marketing/broadsheet/BroadsheetPricing";
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Pricing & Plans',
  description: 'Find the perfect plan for comparing LLM responses. Choose between our Starter and Premium tiers.',
};

export const revalidate = 3600;

export default function PricingPage() {
  return (
    <main id="main">
      <BroadsheetPricing />
    </main>
  );
}
