'use client'

import { useMemo, useState } from "react";
import type { PanelSeatConfig } from "@/lib/panels";
import { PANEL_PRESETS, PROVIDER_OPTIONS, ROLE_PROFILES } from "@/lib/panels";

type PanelConfiguratorProps = {
  seats: PanelSeatConfig[];
  onChange: (seats: PanelSeatConfig[]) => void;
};

export default function PanelConfigurator({ seats, onChange }: PanelConfiguratorProps) {
  const [selectedPreset, setSelectedPreset] = useState(PANEL_PRESETS[0]?.id ?? "balanced");

  const providerMap = useMemo(() => {
    const entries = new Map<string, typeof PROVIDER_OPTIONS[number]>();
    PROVIDER_OPTIONS.forEach((provider) => entries.set(provider.key, provider));
    return entries;
  }, []);

  const handleSeatChange = (index: number, patch: Partial<PanelSeatConfig>) => {
    const next = seats.map((seat, idx) => (idx === index ? { ...seat, ...patch } : seat));
    onChange(next);
  };

  const applyPreset = (presetId: string) => {
    const preset = PANEL_PRESETS.find((item) => item.id === presetId);
    if (!preset) return;
    setSelectedPreset(presetId);
    onChange(preset.seats.map((seat) => ({ ...seat })));
  };

  return (
    <div className="rounded-3xl border border-amber-200/70 bg-white/80 p-4 shadow-sm dark:border-amber-900/40 dark:bg-stone-950/40">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-600">Parliament seats</p>
          <p className="text-sm text-stone-600 dark:text-stone-200">Select providers, models, and role profiles.</p>
        </div>
        <select
          className="rounded-full border border-amber-200/70 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-900 dark:border-amber-800 dark:bg-stone-900 dark:text-amber-50"
          value={selectedPreset}
          onChange={(event) => applyPreset(event.target.value)}
        >
          {PANEL_PRESETS.map((preset) => (
            <option key={preset.id} value={preset.id}>
              {preset.label}
            </option>
          ))}
        </select>
      </div>
      <div className="mt-4 space-y-3">
        {seats.map((seat, index) => {
          const provider = providerMap.get(seat.provider_key) ?? PROVIDER_OPTIONS[0];
          const models = provider?.models ?? [];
          const currentModelValid = models.some((model) => model.id === seat.model);
          const displayModel = currentModelValid ? seat.model : models[0]?.id ?? seat.model;
          return (
            <div key={seat.seat_id} className="rounded-2xl border border-amber-100 bg-white/80 p-3 shadow-inner shadow-amber-100 dark:border-amber-900/50 dark:bg-stone-900/50">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-stone-900 dark:text-stone-100">{seat.display_name}</p>
                  <p className="text-xs uppercase tracking-wide text-stone-500">Seat #{index + 1}</p>
                </div>
                <input
                  className="rounded-full border border-amber-200 px-3 py-1 text-xs font-semibold text-amber-900 dark:border-amber-800 dark:bg-stone-900 dark:text-amber-50"
                  value={seat.display_name}
                  onChange={(event) =>
                    handleSeatChange(index, { display_name: event.target.value, seat_id: event.target.value.toLowerCase().replace(/\s+/g, "-") })
                  }
                />
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <label className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                  Role
                  <select
                    className="mt-1 w-full rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-900 dark:border-amber-900/60 dark:bg-stone-900 dark:text-amber-50"
                    value={seat.role_profile}
                    onChange={(event) => handleSeatChange(index, { role_profile: event.target.value })}
                  >
                    {ROLE_PROFILES.map((role) => (
                      <option key={role.slug} value={role.slug}>
                        {role.title}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                  Provider
                  <select
                    className="mt-1 w-full rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-900 dark:border-amber-900/60 dark:bg-stone-900 dark:text-amber-50"
                    value={seat.provider_key}
                    onChange={(event) => {
                      const nextProvider = providerMap.get(event.target.value) ?? PROVIDER_OPTIONS[0];
                      const fallbackModel = nextProvider?.models?.[0]?.id ?? seat.model;
                      handleSeatChange(index, { provider_key: event.target.value, model: fallbackModel });
                    }}
                  >
                    {PROVIDER_OPTIONS.map((providerOption) => (
                      <option key={providerOption.key} value={providerOption.key}>
                        {providerOption.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs font-semibold uppercase tracking-wide text-stone-500">
                  Model
                  <select
                    className="mt-1 w-full rounded-2xl border border-amber-200/70 bg-white px-3 py-2 text-sm text-stone-900 dark:border-amber-900/60 dark:bg-stone-900 dark:text-amber-50"
                    value={displayModel}
                    onChange={(event) => handleSeatChange(index, { model: event.target.value })}
                  >
                    {models.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
