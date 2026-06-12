"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { trackEvent } from "@/lib/analytics";
import { Shield, Sparkles, Building2, HelpCircle, Save, Check } from "lucide-react";

export default function DataRetentionPage() {
  const [retentionPeriod, setRetentionPeriod] = useState("indefinite");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const policies = [
    { id: "indefinite", name: "Indefinite", description: "Keep all debates, syntheses, and activity records until explicitly deleted by the user." },
    { id: "365", name: "1 Year (365 days)", description: "Automatically prune debate runs, timelines, and response data after 365 days." },
    { id: "30", name: "30 Days", description: "Short-term storage. Run details are purged 30 days after synthesis is completed." },
    { id: "7", name: "7 Days (Ephemeral)", description: "For highly sensitive evaluations. Debates are auto-purged weekly." }
  ];

  const handleSave = () => {
    setSaving(true);
    setSaved(false);
    trackEvent("data_retention_policy_updated", { policy: retentionPeriod });

    setTimeout(() => {
      setSaving(false);
      setSaved(true);
    }, 600);
  };

  return (
    <main className="container mx-auto max-w-4xl p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold text-amber-900 dark:text-amber-50">
          Data Retention Policy
        </h1>
        <p className="mt-2 text-sm text-stone-600 dark:text-stone-400 max-w-xl">
          Define storage lifetimes and purge policies for multi-agent synthesis reports and run histories.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          <div className="card-elevated border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-500">Storage Lifespan Policy</h3>
            
            <div className="space-y-3">
              {policies.map((p) => (
                <label
                  key={p.id}
                  className={`flex items-start gap-3.5 p-4 rounded-xl border cursor-pointer transition ${
                    retentionPeriod === p.id
                      ? "border-amber-500 bg-amber-50/25 dark:bg-amber-950/10"
                      : "border-slate-200 dark:border-slate-850 hover:bg-slate-50/50 dark:hover:bg-slate-900/10"
                  }`}
                >
                  <input
                    type="radio"
                    name="retention"
                    value={p.id}
                    checked={retentionPeriod === p.id}
                    onChange={(e) => setRetentionPeriod(e.target.value)}
                    className="mt-1 accent-amber-600"
                  />
                  <div>
                    <span className="block text-sm font-bold text-slate-900 dark:text-white">{p.name}</span>
                    <span className="block text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">{p.description}</span>
                  </div>
                </label>
              ))}
            </div>

            <div className="flex items-center gap-3 pt-2">
              <Button
                disabled={saving}
                onClick={handleSave}
                className="bg-amber-600 hover:bg-amber-700 text-white font-semibold flex items-center gap-1.5"
              >
                {saving ? "Saving..." : saved ? "Saved" : "Save Changes"}
                {saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </div>

        {/* Enterprise Upgrade callout */}
        <div className="space-y-6">
          <div className="relative overflow-hidden rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50/20 via-white to-white p-6 shadow-sm dark:border-amber-900/40 dark:from-slate-900/80 dark:to-slate-800/80 dark:shadow-none">
            <div className="absolute right-0 top-0 translate-x-1/3 -translate-y-1/3 w-32 h-32 rounded-full bg-amber-400/5 blur-2xl" />
            
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-900/50 mb-4">
              <Building2 className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>

            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
              Enterprise Compliance Features
              <Sparkles className="h-4 w-4 text-amber-500 animate-pulse" />
            </h3>
            
            <p className="mt-2.5 text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Need strict compliance guarantees? Our Enterprise tier supports:
            </p>

            <ul className="mt-3.5 space-y-2.5 text-[11px] font-medium text-slate-700 dark:text-slate-200">
              <li className="flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Custom duration policies (e.g., exactly 180 days)
              </li>
              <li className="flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Legal Hold exemptions for forensic audits
              </li>
              <li className="flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Automated logs routing to Datadog or S3
              </li>
              <li className="flex items-center gap-2">
                <Shield className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Sovereign self-hosted DB migrations
              </li>
            </ul>

            <button
              onClick={() => {
                trackEvent("retention_enterprise_cta_clicked");
                window.location.href = "mailto:enterprise@consultaion.com?subject=Enterprise%20Compliance%20Inquiry";
              }}
              className="mt-6 w-full rounded-xl bg-slate-900 py-2.5 text-xs font-semibold text-white shadow transition hover:bg-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700"
            >
              Contact Enterprise Sales
            </button>
          </div>

          <div className="rounded-xl border border-slate-200/60 dark:border-slate-800 p-4 bg-slate-50/50 dark:bg-slate-950/20 text-xs text-slate-500 leading-relaxed flex gap-2">
            <HelpCircle className="h-4.5 w-4.5 text-slate-400 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block mb-0.5 text-slate-700 dark:text-slate-350">How purging works</span>
              Purge tasks run daily at 00:00 UTC. When a run is purged, its prompt, timeline events, and syntheses are permanently scrubbed from all secondary caches and primary databases. This action is irreversible.
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
