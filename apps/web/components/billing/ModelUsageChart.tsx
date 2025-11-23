"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { getModelUsage } from "@/lib/api";
import { useI18n } from "@/lib/i18n/client";

interface UsageRow {
  model_id: string;
  display_name: string;
  tokens_used: number;
  approx_cost_usd: number | null;
}

export function ModelUsageChart() {
  const [rows, setRows] = useState<UsageRow[]>([]);
  const { t } = useI18n();

  useEffect(() => {
    getModelUsage()
      .then((items) => setRows(items))
      .catch(() => setRows([]));
  }, []);

  if (!rows.length) {
    return (
      <Card className="border-amber-200 bg-white/80 p-4 text-sm text-[#5a4a3a]">
        {t("settings.billing.usagePlaceholder")}
      </Card>
    );
  }

  const maxTokens = Math.max(...rows.map((row) => row.tokens_used));

  return (
    <Card className="space-y-3 border-amber-200 bg-white/80 p-4">
      <h4 className="font-semibold text-sm text-[#3a2a1a]">{t("settings.billing.usageHeading")}</h4>
      <div className="space-y-3">
        {rows.map((row) => {
          const width = maxTokens ? Math.max(6, Math.round((row.tokens_used / maxTokens) * 100)) : 0;
          return (
            <div key={row.model_id}>
              <div className="flex items-center justify-between text-xs text-[#5a4a3a]">
                <span>{row.display_name}</span>
                <span>
                  {row.tokens_used.toLocaleString()} {t("settings.billing.tokensLabel")}
                </span>
              </div>
              <div className="mt-1 h-2 w-full rounded-full bg-amber-100">
                <div className="h-full rounded-full bg-amber-500" style={{ width: `${width}%` }} />
              </div>
              {row.approx_cost_usd != null ? (
                <p className="mt-1 text-[10px] text-stone-500">
                  ≈ ${row.approx_cost_usd.toFixed(2)} {t("settings.billing.costLabel")}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
