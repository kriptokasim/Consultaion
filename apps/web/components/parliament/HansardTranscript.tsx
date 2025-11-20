"use client";

import { useMemo, useState } from "react";
import { FixedSizeList, type ListChildComponentProps } from "react-window";
import { Search, Filter, Download, Users } from "lucide-react";
import type { DebateEvent, Member } from "./types";

interface HansardTranscriptProps {
  events: DebateEvent[];
  members: Member[];
  title?: string;
}

interface FilterState {
  persona: string;
  round: string;
  search: string;
}

const filterButtonClasses =
  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500";

export default function HansardTranscript({
  events,
  members,
  title = "Hansard Transcript",
}: HansardTranscriptProps) {
  const [filters, setFilters] = useState<FilterState>({
    persona: "all",
    round: "all",
    search: "",
  });

  const rounds = useMemo(() => {
    const set = new Set<number>();
    events.forEach((event) => {
      if ("round" in event && typeof event.round === "number") {
        set.add(event.round);
      }
    });
    return Array.from(set).sort((a, b) => a - b);
  }, [events]);

  const personas = useMemo(() => {
    const set = new Set<string>();
    events.forEach((event) => {
      if ("actor" in event && event.actor) set.add(event.actor);
      if (event.type === "score") set.add(event.judge);
    });
    members.forEach((member) => set.add(member.name));
    return Array.from(set).sort();
  }, [events, members]);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      if (
        filters.round !== "all" &&
        ("round" in event ? String(event.round ?? "") !== filters.round : true)
      ) {
        return false;
      }
      if (filters.persona !== "all") {
        const actor = "actor" in event ? event.actor : null;
        const persona =
          event.type === "score" ? event.persona ?? actor : actor;
        if (persona && persona !== filters.persona) {
          return false;
        }
      }
      if (filters.search.trim()) {
        const text = (
          ("text" in event && event.text) ||
          (event.type === "score" ? event.rationale : "") ||
          ""
        ).toLowerCase();
        if (!text.includes(filters.search.toLowerCase())) {
          return false;
        }
      }
      return true;
    });
  }, [events, filters]);

  const exportText = () => {
    const lines = events.map((event) => {
      if (event.type === "score") {
        return `[SCORE] ${event.judge} → ${event.persona}: ${event.score} – ${
          event.rationale ?? ""
        }`;
      }
      if (event.type === "message") {
        return `[ROUND ${event.round ?? "-"}] ${event.actor}: ${event.text ?? ""}`;
      }
      if (event.type === "final") {
        return `[FINAL] ${event.text ?? ""}`;
      }
      return `[NOTICE] ${"text" in event ? event.text ?? "" : ""}`;
    });
    const blob = new Blob([lines.join("\n")], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `hansard-${Date.now()}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const listMetrics = useMemo(() => {
    const itemSize = 148;
    const baseHeight = Math.max(itemSize, filteredEvents.length * itemSize);
    const height = Math.min(720, baseHeight);
    return { itemSize, height };
  }, [filteredEvents.length]);

  const listData = useMemo(
    () => ({ items: filteredEvents, members }),
    [filteredEvents, members]
  );

  function renderRow({
    index,
    style,
    data,
  }: ListChildComponentProps<{ items: DebateEvent[]; members: Member[] }>) {
    const event = data.items[index];
    return (
      <div style={style} className="px-0 py-2">
        <TranscriptRow event={event} members={data.members} />
      </div>
    );
  }

  return (
    <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-[0_10px_30px_rgba(120,113,108,0.08)]">
      <header className="flex flex-col gap-4 border-b border-stone-100 pb-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-600">
            Official record
          </p>
          <h2 className="text-2xl font-semibold text-stone-900">{title}</h2>
          <p className="text-sm text-stone-500">
            Filter by member, round, or keyword to inspect deliberations.
          </p>
        </div>
        <button
          type="button"
          onClick={exportText}
          className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 transition hover:border-amber-300 hover:bg-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500"
          aria-label="Export transcript as text file"
        >
          <Download className="h-4 w-4" />
          Export .txt
        </button>
      </header>

      <div className="mt-6 grid gap-4 rounded-2xl border border-stone-100 bg-stone-50/60 p-4 md:grid-cols-3">
        <FilterSelect
          label="Member"
          value={filters.persona}
          onChange={(value) => setFilters((prev) => ({ ...prev, persona: value }))}
          options={[{ label: "All members", value: "all" }, ...personas.map((name) => ({ label: name, value: name }))]}
        />
        <FilterSelect
          label="Round"
          value={filters.round}
          onChange={(value) => setFilters((prev) => ({ ...prev, round: value }))}
          options={[
            { label: "All rounds", value: "all" },
            ...rounds.map((round) => ({ label: `Round ${round}`, value: String(round) })),
          ]}
        />
        <label className="text-xs font-semibold uppercase tracking-wide text-stone-500">
          Search
          <div className="mt-2 flex items-center gap-2 rounded-full border border-stone-200 bg-white px-3 py-2 text-sm shadow-inner">
            <Search className="h-4 w-4 text-stone-400" />
            <input
              type="text"
              value={filters.search}
              onChange={(event) => setFilters((prev) => ({ ...prev, search: event.target.value }))}
              placeholder="Find keywords…"
              className="w-full bg-transparent text-stone-800 placeholder:text-stone-400 focus:outline-none"
            />
          </div>
        </label>
      </div>

      <div className="mt-6" aria-live="polite" role="log">
        {filteredEvents.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/70 p-6 text-center text-sm text-stone-500">
            No entries match your filters.
          </div>
        ) : (
          <FixedSizeList
            height={listMetrics.height}
            itemCount={filteredEvents.length}
            itemSize={listMetrics.itemSize}
            width="100%"
            itemData={listData}
          >
            {renderRow}
          </FixedSizeList>
        )}
      </div>
    </section>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { label: string; value: string }[];
}) {
  return (
    <label className="text-xs font-semibold uppercase tracking-wide text-stone-500">
      {label}
      <div className="mt-2 flex items-center gap-2 rounded-full border border-stone-200 bg-white px-3 py-2 text-sm shadow-inner">
        <Filter className="h-4 w-4 text-stone-400" />
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full bg-transparent text-stone-800 focus:outline-none"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </label>
  );
}

function TranscriptRow({
  event,
  members,
}: {
  event: DebateEvent;
  members: Member[];
}) {
  const personaLabel =
    event.type === "score"
      ? event.persona
      : "actor" in event
        ? event.actor
        : undefined;
  const memberRole = members.find((member) => member.name === personaLabel)?.role;
  return (
    <article className="rounded-2xl border border-stone-100 bg-white/80 p-4 shadow-sm transition hover:shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100 text-sm font-semibold text-amber-700">
            {personaLabel?.charAt(0) ?? "?"}
          </div>
          <div>
            <p className="text-sm font-semibold text-stone-800">
              {personaLabel ?? "Parliament"}
            </p>
            {memberRole && (
              <p className="text-xs uppercase tracking-wide text-stone-400">
                {memberRole}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-stone-400">
          {event.type === "message" && (
            <>
              <span className="rounded-full bg-stone-100 px-2 py-0.5 font-semibold text-stone-600">
                Round {event.round ?? "-"}
              </span>
            </>
          )}
          {event.type === "score" && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-700">
              Judge {event.judge}
            </span>
          )}
        </div>
      </div>
      <div className="mt-3 space-y-1 text-sm leading-relaxed text-stone-700">
        {event.type === "score" ? (
          <>
            <p className="font-semibold text-stone-900">
              Score: {event.score.toFixed(2)}
            </p>
            <p>{event.rationale ?? "No rationale provided."}</p>
          </>
        ) : (
          <p>{("text" in event && event.text) || "—"}</p>
        )}
      </div>
    </article>
  );
}
