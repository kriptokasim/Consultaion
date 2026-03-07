"use client";

import { useMemo, useState } from "react";
import { Search, Filter, Download } from "lucide-react";
import type { DebateEvent, Member } from "./types";
import { formatModelLabel } from "@/lib/ui/formatters";

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

/** Build a stable string key for a debate event so React can reconcile correctly. */
function stableKey(event: DebateEvent, index: number): string {
  const at = "at" in event ? (event.at ?? "") : "";
  const actor =
    event.type === "score"
      ? `score-${event.judge}-${event.persona}`
      : event.type === "message"
        ? `msg-${(event as any).actor ?? ""}`
        : event.type === "seat_message"
          ? `seat-${(event as any).seat_id ?? ""}`
          : event.type;
  return `${event.type}-${at}-${actor}-${index}`;
}

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
      if (event.type === "seat_message" && event.seat_name) set.add(event.seat_name);
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
        const actor =
          event.type === "seat_message"
            ? event.seat_name
            : "actor" in event
              ? event.actor
              : null;
        const persona =
          event.type === "score" ? event.persona ?? actor : actor;
        if (persona && persona !== filters.persona) {
          return false;
        }
      }
      if (filters.search.trim()) {
        const text = (
          ("text" in event && event.text) ||
          ("content" in event && (event as any).content) ||
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
        return `[SCORE] ${event.judge} → ${event.persona}: ${event.score} – ${event.rationale ?? ""
          }`;
      }
      if (event.type === "seat_message") {
        return `[SEAT] ${event.seat_name ?? "?"}: ${event.content ?? ""}`;
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

  return (
    <section
      id="transcript"
      className="rounded-3xl border border-stone-200 bg-white p-6 shadow-[0_10px_30px_rgba(120,113,108,0.08)] dark:border-border dark:bg-card"
    >
      <header className="flex flex-col gap-4 border-b border-stone-100 pb-6 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
            Official record
          </p>
          <h2 className="text-2xl font-semibold text-stone-900 dark:text-foreground">{title}</h2>
          <p className="text-sm text-stone-500 dark:text-muted-foreground">
            Filter by member, round, or keyword to inspect deliberations.
          </p>
        </div>
        <button
          type="button"
          onClick={exportText}
          className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-700 transition hover:border-amber-300 hover:bg-amber-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-400 dark:hover:border-amber-700 dark:hover:bg-amber-950/60"
          aria-label="Export transcript as text file"
        >
          <Download className="h-4 w-4" />
          Export .txt
        </button>
      </header>

      <div className="mt-6 grid gap-4 rounded-2xl border border-stone-100 bg-stone-50/60 p-4 md:grid-cols-3 dark:border-border dark:bg-muted/30">
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
        <label className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-muted-foreground">
          Search
          <div className="mt-2 flex items-center gap-2 rounded-full border border-stone-200 bg-white px-3 py-2 text-sm shadow-inner dark:border-border dark:bg-card">
            <Search className="h-4 w-4 text-stone-400 dark:text-muted-foreground" />
            <input
              type="text"
              value={filters.search}
              onChange={(event) => setFilters((prev) => ({ ...prev, search: event.target.value }))}
              placeholder="Find keywords…"
              className="w-full bg-transparent text-stone-800 placeholder:text-stone-400 focus:outline-none dark:text-foreground dark:placeholder:text-muted-foreground"
            />
          </div>
        </label>
      </div>

      {/* Transcript list — plain scrollable div, no virtualization with fixed row heights */}
      <div className="mt-6" aria-live="polite" role="log">
        {filteredEvents.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/70 p-6 text-center text-sm text-stone-500 dark:border-border dark:bg-muted/30 dark:text-muted-foreground">
            No entries match your filters.
          </div>
        ) : (
          <div className="max-h-[720px] overflow-y-auto space-y-3 pr-1">
            {filteredEvents.map((event, index) => (
              <TranscriptRow
                key={stableKey(event, index)}
                event={event}
                members={members}
              />
            ))}
          </div>
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
    <label className="text-xs font-semibold uppercase tracking-wide text-stone-500 dark:text-muted-foreground">
      {label}
      <div className="mt-2 flex items-center gap-2 rounded-full border border-stone-200 bg-white px-3 py-2 text-sm shadow-inner dark:border-border dark:bg-card">
        <Filter className="h-4 w-4 text-stone-400 dark:text-muted-foreground" />
        <select
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="w-full bg-transparent text-stone-800 focus:outline-none dark:text-foreground"
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
  // Resolve display name and provider metadata
  let personaLabel: string | undefined;
  let providerModel: string | undefined;

  if (event.type === "seat_message") {
    personaLabel = event.seat_name ?? "Parliament";
    providerModel = event.provider ?? (event as any).model;
  } else if (event.type === "score") {
    personaLabel = event.persona;
  } else if ("actor" in event && event.actor) {
    personaLabel = event.actor;
    providerModel = (event as any).provider ?? (event as any).model;
  }

  const memberRole = members.find((member) => member.name === personaLabel)?.role;
  const providerLabel = formatModelLabel(providerModel);

  // Content to display
  let content: React.ReactNode;
  if (event.type === "score") {
    content = (
      <>
        <p className="font-semibold text-stone-900">
          Score: {event.score.toFixed(2)}
        </p>
        <p>{event.rationale ?? "No rationale provided."}</p>
      </>
    );
  } else if (event.type === "seat_message") {
    content = <p>{event.content || "—"}</p>;
  } else {
    content = <p>{("text" in event && event.text) || "—"}</p>;
  }

  return (
    <article className="rounded-2xl border border-stone-100 bg-white/80 p-4 shadow-sm transition hover:shadow-lg dark:border-border dark:bg-card/80">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100 text-sm font-semibold text-amber-700 dark:bg-amber-950/60 dark:text-amber-400">
            {personaLabel?.charAt(0) ?? "?"}
          </div>
          <div>
            <p className="text-sm font-semibold text-stone-800 dark:text-foreground">
              {personaLabel ?? "Parliament"}
            </p>
            {memberRole && (
              <p className="text-xs uppercase tracking-wide text-stone-400 dark:text-muted-foreground">
                {memberRole}
              </p>
            )}
            {providerLabel && (
              <p className="text-[0.68rem] text-stone-400 dark:text-muted-foreground">{providerLabel}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-stone-400 dark:text-muted-foreground">
          {event.type === "message" && (
            <>
              <span className="rounded-full bg-stone-100 px-2 py-0.5 font-semibold text-stone-600 dark:bg-muted dark:text-muted-foreground">
                Round {event.round ?? "-"}
              </span>
            </>
          )}
          {event.type === "seat_message" && (
            <span className="rounded-full bg-stone-100 px-2 py-0.5 font-semibold text-stone-600 dark:bg-muted dark:text-muted-foreground">
              Seat statement
            </span>
          )}
          {event.type === "score" && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold text-amber-700 dark:bg-amber-950/60 dark:text-amber-400">
              Judge {event.judge}
            </span>
          )}
          {event.type === "final" && (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400">
              Final synthesis
            </span>
          )}
        </div>
      </div>
      <div className="mt-3 space-y-1 text-sm leading-relaxed text-stone-700 dark:text-foreground/80">
        {content}
      </div>
    </article>
  );
}
