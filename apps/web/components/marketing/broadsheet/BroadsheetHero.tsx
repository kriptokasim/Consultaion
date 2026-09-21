"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n/client";
import { Reveal } from "@/components/landing/Reveal";

/**
 * Section 1 of 5 (DESIGN-SPEC "Marketing"): hero + one primary CTA. Copy
 * reuses the existing, already-approved landing.hero.* i18n keys instead of
 * inventing new marketing claims.
 */
export function BroadsheetHero() {
  const { t } = useI18n();

  return (
    <section className="new-ux-marketing__section new-ux-marketing__hero-section" id="hero">
      <div className="new-ux-marketing__shell new-ux-marketing__hero">
        <Reveal>
          <p className="new-ux-marketing__kicker">{t("landing.hero.accent")}</p>
          <h1>{t("landing.hero.title")}</h1>
          <p className="new-ux-marketing__lede">{t("landing.hero.subtitle")}</p>
          <div className="new-ux-marketing__hero-actions">
            <Link href="/login?next=/new" className="new-ux-marketing__primary">
              {t("landing.hero.primaryCta")}
            </Link>
          </div>
          <p className="new-ux-marketing__hero-hint">{t("landing.hero.secondaryHint")}</p>
        </Reveal>
      </div>
    </section>
  );
}
