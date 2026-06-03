"use client";

import { useI18n } from "@/lib/i18n/client";

type DashboardTemplatesSectionProps = {
  onTemplateUse: (templateId: string) => void;
};

export function DashboardTemplatesSection({ onTemplateUse }: DashboardTemplatesSectionProps) {
  const { t } = useI18n();

  return (
    <section id="templates-section" className="rounded-3xl border border-border bg-gradient-to-br from-card to-blue-50/30 p-8 shadow-md dark:to-secondary">
      <div className="mb-6 text-center">
        <h2 className="text-2xl font-semibold text-foreground">{t("dashboard.onboarding.title")}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{t("dashboard.onboarding.subtitle")}</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <TemplateCard
          title={t("dashboard.templates.strategy.title")}
          description={t("dashboard.templates.strategy.description")}
          onClick={() => onTemplateUse("strategy-saas-rollout")}
        />
        <TemplateCard
          title={t("dashboard.templates.governance.title")}
          description={t("dashboard.templates.governance.description")}
          onClick={() => onTemplateUse("risk-bank-governance")}
        />
        <TemplateCard
          title={t("dashboard.templates.product.title")}
          description={t("dashboard.templates.product.description")}
          onClick={() => onTemplateUse("product-roadmap")}
        />
      </div>
    </section>
  );
}

function TemplateCard({ title, description, onClick }: { title: string; description: string; onClick: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col justify-between rounded-2xl border border-border bg-card p-5 shadow-sm">
      <div>
        <h3 className="text-lg font-semibold text-foreground mb-2">{title}</h3>
        <p className="text-sm text-muted-foreground mb-4">{description}</p>
      </div>
      <button
        type="button"
        onClick={onClick}
        className="w-full rounded-lg border-2 border-primary/30 bg-primary/5 px-4 py-2 text-sm font-semibold text-primary transition hover:bg-primary/10 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
      >
        {t("dashboard.templates.useTemplate")}
      </button>
    </div>
  );
}
