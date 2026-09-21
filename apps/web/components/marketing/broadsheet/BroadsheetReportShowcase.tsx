"use client";

import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "@/components/landing/Reveal";
import { DecisionReport } from "@/components/report/DecisionReport";
import type { DecisionReport as DecisionReportData } from "@/components/report/DecisionReportView";

/**
 * Illustrative only — explicitly labeled as an example in the UI, never
 * presented as a real run. There is no real curated-public-run data source
 * yet (see PS05 commit notes); building one is backend work outside this
 * pass. Final Rule: mock content must read as illustrative, not real.
 */
const EXAMPLE_REPORT: DecisionReportData = {
  title: "Market entry decision",
  executive_summary:
    "Demand appears plausible, but channel risk remains high. Models disagree most on pricing and timing.",
  verdict: {
    recommendation: "Proceed with a narrow pilot",
    confidence: 0.78,
    decision_type: "proceed",
    rationale:
      "A limited pilot reduces downside while preserving learning speed on the open questions the panel disagreed about.",
  },
  key_findings: [
    { title: "Channel risk dominates", summary: "Distribution signal is the weakest input across all models.", importance: "high" },
    { title: "Pricing is contested", summary: "Panel splits between penetration and premium pricing.", importance: "high" },
    { title: "Timing has a narrow window", summary: "Two of three models flag a seasonal entry window.", importance: "medium" },
  ],
  model_positions: [
    { model: "Arena seat A", stance: "supportive", distinct_contribution: "Sizes the addressable segment", blind_spot: "Optimistic on channel access" },
    { model: "Arena seat B", stance: "cautious", distinct_contribution: "Flags distribution risk early", blind_spot: "Underweights the seasonal window" },
  ],
  risks_and_assumptions: [
    { item: "Weak distribution signal", type: "risk", severity: "high", mitigation: "Validate with 2 pilot channel partners before scaling." },
    { item: "Unclear willingness to pay", type: "assumption", severity: "medium" },
  ],
  next_actions: [
    { action: "Interview 10 target users", priority: "now" },
    { action: "Test a pricing page", priority: "next" },
    { action: "Expand to a second segment", priority: "later" },
  ],
  caveats: ["Illustrative example — not a real run. Your own reports are generated from your panel's actual responses."],
};

export function BroadsheetReportShowcase() {
  const { t } = useI18n();

  return (
    <section className="new-ux-marketing__section" id="report" aria-labelledby="marketing-report-heading">
      <div className="new-ux-marketing__shell">
        <Reveal>
          <p className="new-ux-marketing__kicker">{t("marketing.report.kicker")}</p>
          <h2 id="marketing-report-heading" className="new-ux-marketing__section-title">
            {t("marketing.report.title")}
          </h2>
          <p className="new-ux-marketing__lede">{t("marketing.report.lede")}</p>
        </Reveal>
        <Reveal delay={100}>
          <div style={{ marginTop: 28 }}>
            <DecisionReport run={{ report: EXAMPLE_REPORT, variant: "arena" }} audience="record" />
          </div>
        </Reveal>
      </div>
    </section>
  );
}
