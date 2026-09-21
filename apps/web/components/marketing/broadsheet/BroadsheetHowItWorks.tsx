"use client";

import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "@/components/landing/Reveal";
import { LazyChamberEmbed } from "./LazyChamberEmbed";

/**
 * Section 3 of 5: how the panel works + chamber. Reuses the exact copy
 * already used by the pre-existing HowItWorks.tsx (landing.howItWorks.steps.*)
 * instead of writing new marketing claims, and the untouched chamber embed
 * (D3/D4 — never reimplemented), mounted lazily via LazyChamberEmbed.
 */
export function BroadsheetHowItWorks() {
  const { t } = useI18n();

  const steps = [
    { key: "ask", index: "01" },
    { key: "compare", index: "02" },
    { key: "divergence", index: "03" },
    { key: "report", index: "04" },
  ];

  return (
    <section className="new-ux-marketing__section" id="how-it-works" aria-labelledby="marketing-how-heading">
      <div className="new-ux-marketing__shell">
        <div className="new-ux-marketing__hero" style={{ paddingTop: 0, paddingBottom: 0, alignItems: "center" }}>
          <Reveal>
            <p className="new-ux-marketing__kicker">{t("landing.howItWorks.subtitle")}</p>
            <h2 id="marketing-how-heading" className="new-ux-marketing__section-title">
              {t("landing.howItWorks.title")}
            </h2>
          </Reveal>
          <Reveal delay={100} direction="right">
            <LazyChamberEmbed />
          </Reveal>
        </div>

        <div className="new-ux-marketing__steps">
          {steps.map((step, i) => (
            <Reveal key={step.key} delay={i * 80}>
              <div className="new-ux-marketing__step">
                <div className="new-ux-marketing__step-index">{step.index}</div>
                <h3>{t(`landing.howItWorks.steps.${step.key}.title`)}</h3>
                <p>{t(`landing.howItWorks.steps.${step.key}.description`)}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
