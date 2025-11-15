"use client";

import { Search } from "lucide-react";
import { useId } from "react";
import { cn } from "@/lib/utils";

type FilterChip = {
  value: string;
  label: string;
};

type SearchFilterProps = {
  value: string;
  onValueChange: (value: string) => void;
  status?: string | null;
  onStatusChange?: (value: string | null) => void;
  statuses?: FilterChip[];
  placeholder?: string;
};

export default function SearchFilter({
  value,
  onValueChange,
  status,
  onStatusChange,
  statuses = [],
  placeholder = "Search by prompt or ID…",
}: SearchFilterProps) {
  const inputId = useId();
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <label className="relative w-full md:max-w-sm" htmlFor={inputId}>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
        <input
          id={inputId}
          type="search"
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
          placeholder={placeholder}
          className="w-full rounded-full border border-stone-200 bg-white/80 px-10 py-2 text-sm text-stone-800 shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-amber-500"
        />
      </label>
      {statuses.length ? (
        <div className="flex flex-wrap items-center gap-2">
          {statuses.map((chip) => (
            <button
              key={chip.value}
              type="button"
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide transition",
                status === chip.value
                  ? "border-amber-200 bg-amber-50 text-amber-800 shadow"
                  : "border-stone-200 text-stone-500 hover:text-stone-800",
              )}
              aria-pressed={status === chip.value}
              onClick={() => onStatusChange?.(status === chip.value ? null : chip.value)}
            >
              {chip.label}
            </button>
          ))}
          {status ? (
            <button
              type="button"
              className="text-xs font-semibold uppercase tracking-wide text-amber-600"
              onClick={() => onStatusChange?.(null)}
            >
              Clear
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
