"use client";

import { useEffect, useMemo, useState } from "react";
import { Play, PauseCircle } from "lucide-react";
import { DebateTimelineEvent } from "@/lib/api/debates";
import { useDebateTimeline } from "@/lib/hooks/useDebateTimeline";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n/client";

type Props = {
  debateId: string;
};

export function DebateReplay({ debateId }: Props) {
  const { t } = useI18n();
  const { data, loading, error } = useDebateTimeline(debateId);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  const events = data ?? [];

  useEffect(() => {
    if (events.length === 0) {
      setIndex(0);
      return;
    }
    if (index > events.length - 1) {
      setIndex(events.length - 1);
    }
  }, [events.length, index]);

  useEffect(() => {
    if (!playing || events.length === 0) return;
    const id = setInterval(() => {
      setIndex((prev) => {
        if (prev >= events.length - 1) {
          return prev;
        }
        return prev + 1;
      });
    }, 1200);
    return () => clearInterval(id);
  }, [playing, events.length]);

  const current: DebateTimelineEvent | null = useMemo(() => {
    if (!events.length) return null;
    return events[Math.min(index, events.length - 1)];
  }, [events, index]);

  if (loading) {
    return (
      <div className="glass-card space-y-2 rounded-2xl border border-amber-200/70 bg-white/70 p-6 shadow-lg">
        <p className="text-sm text-stone-600">{t("replay.loading")}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card space-y-2 rounded-2xl border border-amber-200/70 bg-white/70 p-6 shadow-lg">
        <p className="text-sm text-red-700">{t("replay.errorGeneric")}</p>
      </div>
    );
  }

  if (!current) {
    return (
      <div className="glass-card space-y-2 rounded-2xl border border-amber-200/70 bg-white/70 p-6 shadow-lg">
        <p className="text-sm text-stone-600">{t("replay.noEvents")}</p>
      </div>
    );
  }

  const isSystemNotice = current.type === "system_notice";

  return (
    <div className="glass-card space-y-6 rounded-3xl border border-amber-200/70 bg-white/80 p-6 shadow-lg">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700">{t("replay.title")}</p>
          <p className="text-sm text-stone-600">{t("replay.subtitle")}</p>
        </div>
        <Button variant="amber" size="sm" onClick={() => setPlaying((p) => !p)}>
          {playing ? (
            <>
              <PauseCircle className="mr-2 h-4 w-4" />
              {t("replay.pause")}
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              {t("replay.play")}
            </>
          )}
        </Button>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-stone-600">
          <span>{t("replay.position").replace("{{current}}", String(index + 1)).replace("{{total}}", String(events.length))}</span>
          <button
            type="button"
            className="text-amber-700 underline"
            onClick={() => {
              setIndex(0);
              setPlaying(true);
            }}
          >
            {t("replay.fromStart")}
          </button>
        </div>
        <input
          type="range"
          min={0}
          max={Math.max(events.length - 1, 0)}
          value={index}
          onChange={(e) => setIndex(Number(e.target.value))}
          className="w-full accent-amber-600"
        />
      </div>

      <div className="space-y-3 rounded-2xl border border-amber-200/70 bg-white/80 p-4 shadow-inner shadow-amber-900/5">
        <div className="flex flex-wrap items-center gap-2 text-xs text-stone-600">
          <span>{t("replay.currentRound").replace("{{round}}", String(current.round_index || 1)).replace("{{phase}}", current.type)}</span>
          <span>·</span>
          <span>{t("replay.currentSeat").replace("{{role}}", current.role ?? "—").replace("{{provider}}", current.provider ?? "—").replace("{{model}}", current.model ?? "—")}</span>
        </div>

        {isSystemNotice ? (
          <div className="rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="font-semibold">{t("replay.systemNotice")}</p>
            <p className="mt-1 text-amber-800">{current.content ?? t("replay.systemNoticeDefault")}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {current.stance ? <p className="text-sm font-semibold text-amber-900">{current.stance}</p> : null}
            {current.content ? <p className="text-sm leading-relaxed text-stone-800">{current.content}</p> : null}
          </div>
        )}
      </div>
    </div>
  );
}
