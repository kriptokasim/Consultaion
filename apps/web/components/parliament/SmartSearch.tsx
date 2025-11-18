"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type SearchItem = { id: string; prompt: string };

type SmartSearchProps = {
  items: SearchItem[];
  initialQuery?: string;
};

export default function SmartSearch({ items, initialQuery = "" }: SmartSearchProps) {
  const [query, setQuery] = useState(initialQuery);
  const router = useRouter();

  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return items
      .filter((item) => item.prompt && item.prompt.toLowerCase().includes(q))
      .slice(0, 6);
  }, [items, query]);

  return (
    <div className="rounded-2xl border border-amber-200/70 bg-white/80 p-4 shadow-sm dark:border-amber-700/60 dark:bg-stone-900/60">
      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-200" htmlFor="smart-search">
          Smart search
        </label>
        <input
          id="smart-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search your runs…"
          className="w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm text-stone-900 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 dark:border-amber-800 dark:bg-stone-900 dark:text-amber-50"
          aria-label="Search runs"
        />
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
                  <span className="line-clamp-2">{item.prompt}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-stone-500 dark:text-stone-400">Search results will appear here.</p>
        )}
      </div>
    </div>
  );
}
