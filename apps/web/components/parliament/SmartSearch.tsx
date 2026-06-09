"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useI18n } from "@/lib/i18n/client";

export type SearchItem = {
  id: string;
  prompt?: string | null;
  mode?: string | null;
  status?: string | null;
  title?: string | null;
  createdAt?: string | null;
};

function getSearchableText(item: SearchItem): string {
  return [
    item.id,
    item.prompt,
    item.mode,
    item.status,
    item.title,
    item.createdAt,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

type SmartSearchProps = {
  items: SearchItem[];
  initialQuery?: string;
};

export default function SmartSearch({ items, initialQuery = "" }: SmartSearchProps) {
  const [query, setQuery] = useState(initialQuery);
  const router = useRouter();
  const { t } = useI18n();

  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return items
      .filter((item) => getSearchableText(item).includes(q))
      .slice(0, 8);
  }, [items, query]);

  return (
    <div className="rounded-2xl border border-amber-200/70 bg-white/80 p-4 shadow-sm dark:border-amber-700/60 dark:bg-stone-900/60">
      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-200" htmlFor="smart-search">
          {t("runs.smartSearch.label")}
        </label>
        <input
          id="smart-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setQuery("");
          }}
          placeholder={t("runs.smartSearch.placeholder")}
          className="w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm text-stone-900 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 dark:border-amber-800 dark:bg-stone-900 dark:text-amber-50"
          aria-label={t("runs.smartSearch.aria")}
        />
        <div aria-live="polite" className="sr-only">
          {query ? `${results.length} results found` : ""}
        </div>
        {results.length ? (
          <ul className="divide-y divide-amber-100 rounded-xl border border-amber-100 bg-amber-50/60 text-sm text-stone-800 dark:divide-amber-900/40 dark:border-amber-900/40 dark:bg-stone-900/60">
            {results.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  onClick={() => router.push(`/runs/${item.id}`)}
                  className="flex w-full items-start gap-2 px-3 py-2 text-left transition hover:bg-amber-100/70 dark:hover:bg-amber-900/40"
                >
                  <span className="mt-0.5 h-2 w-2 rounded-full bg-amber-500" aria-hidden="true" />
                  <div className="flex-1 min-w-0">
                    <span className="line-clamp-2 block">{item.prompt || item.title || item.id}</span>
                    <span className="mt-0.5 flex gap-2 text-[10px] text-stone-500 dark:text-stone-400">
                      {item.mode && <span className="uppercase tracking-wider">{item.mode}</span>}
                      {item.status && <span>{item.status}</span>}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        ) : query ? (
          <p className="text-xs text-stone-500 dark:text-stone-400">{t("runs.smartSearch.empty")}</p>
        ) : (
          <p className="text-xs text-stone-500 dark:text-stone-400">{t("runs.smartSearch.hint")}</p>
        )}
      </div>
    </div>
  );
}
