import { BroadsheetHero } from "./BroadsheetHero";
import { BroadsheetReportShowcase } from "./BroadsheetReportShowcase";
import { BroadsheetHowItWorks } from "./BroadsheetHowItWorks";
import { BroadsheetTrust } from "./BroadsheetTrust";
import { BroadsheetPricing } from "./BroadsheetPricing";

/**
 * PS07: the five-section Broadsheet homepage (DESIGN-SPEC "Marketing") —
 * hero + one CTA, full decision report, how the panel works + chamber,
 * trust/security, pricing + one CTA. Server-rendered where the section
 * allows it (pricing); hash-navigable via each section's id.
 */
export default function BroadsheetHomeContent() {
  return (
    <main id="main">
      <BroadsheetHero />
      <BroadsheetReportShowcase />
      <BroadsheetHowItWorks />
      <BroadsheetTrust />
      <BroadsheetPricing />
    </main>
  );
}
