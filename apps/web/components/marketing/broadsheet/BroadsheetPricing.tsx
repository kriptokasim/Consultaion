import Link from "next/link";
import { getBillingPlans, type BillingPlanSummary } from "@/lib/api";
import { getServerTranslations } from "@/lib/i18n/server";

/**
 * Section 5 of 5: pricing + one CTA. Fetches the real billing plans
 * (same getBillingPlans() the existing /pricing page uses) instead of
 * hardcoding tiers/prices. The enterprise card lists only capabilities
 * already described on /pricing (no SSO/SAML/SCIM — DECISIONS.md warns
 * against implying those unless shipped).
 */
async function fetchPlans(): Promise<BillingPlanSummary[]> {
  try {
    return await getBillingPlans();
  } catch {
    return [];
  }
}

export async function BroadsheetPricing() {
  const { t } = await getServerTranslations();
  const plans = await fetchPlans();

  return (
    <section className="new-ux-marketing__section" id="pricing" aria-labelledby="marketing-pricing-heading">
      <div className="new-ux-marketing__shell">
        <p className="new-ux-marketing__kicker">{t("pricing.kicker")}</p>
        <h2 id="marketing-pricing-heading" className="new-ux-marketing__section-title">
          {t("pricing.title")}
        </h2>
        <p className="new-ux-marketing__lede">{t("pricing.description")}</p>

        <div className="new-ux-marketing__pricing-grid">
          {plans.map((plan) => (
            <div key={plan.slug} className="new-ux-marketing__plan">
              <span className="new-ux-marketing__plan-name">
                {plan.is_default_free ? t("pricing.plan.starter") : t("pricing.plan.premium")}
              </span>
              <div className="new-ux-marketing__plan-price">
                {plan.price_monthly ? `$${plan.price_monthly.toFixed(2)}` : t("pricing.plan.free")}
                {plan.price_monthly ? <small>{t("pricing.plan.perMonth")}</small> : null}
              </div>
              <ul className="new-ux-marketing__plan-features">
                <li>{plan.limits?.max_debates_per_month ?? "—"} {t("pricing.plan.debates")}</li>
                <li>{plan.limits?.max_models_per_debate ?? 3} {t("pricing.plan.models")}</li>
                <li>{plan.limits?.exports_enabled ? t("pricing.plan.exportsEnabled") : t("pricing.plan.exportsDisabled")}</li>
              </ul>
              <div className="new-ux-marketing__plan-cta">
                <Link href={`/settings/billing?plan=${plan.slug}`} className="new-ux-marketing__secondary">
                  {t("pricing.plan.cta")} {plan.name}
                </Link>
              </div>
            </div>
          ))}

          <div className="new-ux-marketing__plan">
            <span className="new-ux-marketing__plan-name">{t("marketing.pricing.enterprise.kicker")}</span>
            <div className="new-ux-marketing__plan-price">{t("marketing.pricing.enterprise.price")}</div>
            <ul className="new-ux-marketing__plan-features">
              <li>{t("marketing.pricing.enterprise.feature1")}</li>
              <li>{t("marketing.pricing.enterprise.feature2")}</li>
              <li>{t("marketing.pricing.enterprise.feature3")}</li>
              <li>{t("marketing.pricing.enterprise.feature4")}</li>
            </ul>
            <div className="new-ux-marketing__plan-cta">
              <a href="mailto:info@consultaion.com?subject=Enterprise%20Plan%20Inquiry" className="new-ux-marketing__primary">
                {t("marketing.pricing.enterprise.cta")}
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
