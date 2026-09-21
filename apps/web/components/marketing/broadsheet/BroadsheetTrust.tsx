"use client";

import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "@/components/landing/Reveal";

/**
 * Section 4 of 5: trust/security. Copy is grounded in
 * docs/trust-and-security.md's shipped capabilities only — no SOC2/GDPR/SSO
 * claims, since that doc explicitly marks compliance certifications as not
 * yet available ("as we approach enterprise general availability").
 */
export function BroadsheetTrust() {
  const { t } = useI18n();

  const items = ["byok", "encryption", "audit", "routing"];

  return (
    <section className="new-ux-marketing__section" id="trust" aria-labelledby="marketing-trust-heading">
      <div className="new-ux-marketing__shell">
        <Reveal>
          <p className="new-ux-marketing__kicker">{t("marketing.trust.kicker")}</p>
          <h2 id="marketing-trust-heading" className="new-ux-marketing__section-title">
            {t("marketing.trust.title")}
          </h2>
        </Reveal>
        <div className="new-ux-marketing__trust-grid">
          {items.map((item, i) => (
            <Reveal key={item} delay={i * 60}>
              <div className="new-ux-marketing__trust-item">
                <h3>{t(`marketing.trust.${item}.title`)}</h3>
                <p>{t(`marketing.trust.${item}.body`)}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
