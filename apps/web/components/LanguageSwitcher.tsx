'use client'

import { useRouter } from "next/navigation";
import type { Locale } from "@/lib/i18n/dictionaries";
import { useI18n } from "@/lib/i18n/client";

const OPTIONS: { label: string; value: Locale }[] = [
  { label: "TR", value: "tr" },
  { label: "EN", value: "en" },
];

export default function LanguageSwitcher() {
  const router = useRouter();
  const { locale, t } = useI18n();

  const handleSelect = (value: Locale) => {
    if (typeof document === "undefined") return;
    document.cookie = `consultaion_locale=${value}; path=/; max-age=31536000`;
    router.refresh();
  };

  return (
    <div className="mt-3 space-y-1 text-xs font-semibold text-amber-800">
      <span className="uppercase tracking-wide text-amber-500">{t("nav.language.label")}</span>
      <div className="inline-flex rounded-full border border-amber-200/70 bg-white/70 p-1 shadow-sm">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => handleSelect(option.value)}
            className={`rounded-full px-3 py-1 text-xs transition ${
              locale === option.value
                ? "bg-amber-500 text-white shadow"
                : "text-amber-800 hover:bg-amber-100"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}
