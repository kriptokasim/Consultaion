"use client";

import { useI18n } from "@/lib/i18n/client";
import { useUserParticipation } from "@/lib/api/hooks/useUserParticipation";
import Link from "next/link";
import { 
  Activity, 
  Award, 
  Vote, 
  Compass, 
  TrendingUp, 
  MessageSquareCode, 
  GitFork, 
  ShieldAlert, 
  PlayCircle,
  Clock,
  ArrowRight,
  ExternalLink
} from "lucide-react";

type UserProfile = {
  email: string;
  role: string;
  display_name?: string | null;
};

export default function ParticipationClient({ profile }: { profile: UserProfile }) {
  const { t } = useI18n();
  const { data, isLoading, error } = useUserParticipation();

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse p-4">
        {/* Skeleton Header */}
        <div className="h-40 w-full rounded-3xl bg-slate-200 dark:bg-slate-800" />
        
        {/* Skeleton Stats Grid */}
        <div className="grid gap-4 grid-cols-2 md:grid-cols-4 lg:grid-cols-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-24 rounded-2xl bg-slate-200 dark:bg-slate-800" />
          ))}
        </div>

        {/* Skeleton Activity */}
        <div className="h-96 rounded-3xl bg-slate-200 dark:bg-slate-800" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center min-h-[50vh]">
        <div className="rounded-full bg-red-100 dark:bg-red-900/30 p-4 mb-4 text-red-600">
          <ShieldAlert className="h-8 w-8" />
        </div>
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
          {t("errors.generic")}
        </h2>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-2 max-w-sm">
          We couldn&apos;t fetch your participation records. Please try reloading the page.
        </p>
      </div>
    );
  }

  const { stats, recent_activity } = data;

  const statItems = [
    {
      label: t("participation.stats.arenaVotes"),
      value: stats.arena_votes,
      icon: Vote,
      colorClass: "text-amber-600 bg-amber-50 dark:bg-amber-950/30 dark:text-amber-400",
      borderColor: "hover:border-amber-400/50",
    },
    {
      label: t("participation.stats.debateSteers"),
      value: stats.debate_steers,
      icon: Compass,
      colorClass: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30 dark:text-emerald-400",
      borderColor: "hover:border-emerald-400/50",
    },
    {
      label: t("participation.stats.votingPredictions"),
      value: stats.voting_predictions,
      icon: TrendingUp,
      colorClass: "text-indigo-600 bg-indigo-50 dark:bg-indigo-950/30 dark:text-indigo-400",
      borderColor: "hover:border-indigo-400/50",
    },
    {
      label: t("participation.stats.redteamCritiques"),
      value: stats.redteam_critiques,
      icon: MessageSquareCode,
      colorClass: "text-purple-600 bg-purple-50 dark:bg-purple-950/30 dark:text-purple-400",
      borderColor: "hover:border-purple-400/50",
    },
    {
      label: t("participation.stats.oracleBranches"),
      value: stats.oracle_branches,
      icon: GitFork,
      colorClass: "text-rose-600 bg-rose-50 dark:bg-rose-950/30 dark:text-rose-400",
      borderColor: "hover:border-rose-400/50",
    },
    {
      label: t("participation.stats.challengePushbacks"),
      value: stats.challenge_pushbacks,
      icon: Activity,
      colorClass: "text-orange-600 bg-orange-50 dark:bg-orange-950/30 dark:text-orange-400",
      borderColor: "hover:border-orange-400/50",
    },
  ];

  const formatActivityType = (type: string) => {
    switch (type) {
      case "arena_vote": return t("participation.stats.arenaVotes");
      case "debate_moderation": return t("participation.stats.debateSteers");
      case "voting_prediction": return t("participation.stats.votingPredictions");
      case "redteam_critique": return t("participation.stats.redteamCritiques");
      case "oracle_branch": return t("participation.stats.oracleBranches");
      case "challenge_pushback": return t("participation.stats.challengePushbacks");
      default: return type.replace(/_/g, ' ');
    }
  };

  const getActivityColor = (type: string) => {
    switch (type) {
      case "arena_vote": return "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
      case "debate_moderation": return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300";
      case "voting_prediction": return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300";
      case "redteam_critique": return "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300";
      case "oracle_branch": return "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300";
      case "challenge_pushback": return "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300";
      default: return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300";
    }
  };

  const relativeTime = (ts: string): string => {
    const diffMs = Date.now() - new Date(ts).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return t("dashboard.time.justNow");
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    return new Date(ts).toLocaleDateString();
  };

  if (stats.total_interactions === 0) {
    return (
      <div className="space-y-8 p-4">
        {/* Header Banner */}
        <header className="relative overflow-hidden rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 md:p-8 shadow-[0_20px_45px_rgba(120,113,108,0.12)] dark:border-border dark:from-stone-900 dark:via-card dark:to-stone-900">
          <div className="relative z-10">
            <p className="text-xs font-semibold uppercase tracking-widest text-amber-600 dark:text-amber-400">
              {t("participation.hero.kicker")}
            </p>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
              <h1 className="heading-serif text-3xl md:text-4xl font-bold text-slate-900 dark:text-white">
                {t("participation.hero.title")}
              </h1>
            </div>
            <p className="mt-3 text-sm max-w-3xl text-slate-600 dark:text-muted-foreground leading-relaxed">
              {t("participation.hero.description")}
            </p>
          </div>
          <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-amber-200/30 blur-3xl dark:bg-amber-500/10 pointer-events-none" />
        </header>

        <div className="rounded-3xl border border-dashed border-slate-200 bg-white p-8 text-center dark:border-slate-800 dark:bg-slate-900/40">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Participation is not active yet. Prediction and forecaster scoring will appear here when the forecasting loop is enabled.
          </p>
          <div className="mt-6">
            <Link
              href="/live"
              className="inline-flex items-center gap-2 rounded-full bg-amber-600 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-amber-500 transition-colors"
            >
              Back to Arena
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-4">
      {/* Header Banner */}
      <header className="relative overflow-hidden rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 md:p-8 shadow-[0_20px_45px_rgba(120,113,108,0.12)] dark:border-border dark:from-stone-900 dark:via-card dark:to-stone-900">
        <div className="relative z-10">
          <p className="text-xs font-semibold uppercase tracking-widest text-amber-600 dark:text-amber-400">
            {t("participation.hero.kicker")}
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
            <h1 className="heading-serif text-3xl md:text-4xl font-bold text-slate-900 dark:text-white">
              {t("participation.hero.title")}
            </h1>
            {profile.email && (
              <div className="flex items-center gap-2 rounded-full border border-stone-200/60 bg-white/80 dark:bg-card/80 px-4 py-2 text-sm font-semibold text-slate-800 dark:text-white shadow-sm backdrop-blur">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 text-xs">
                  {profile.email.charAt(0).toUpperCase()}
                </span>
                <span className="truncate max-w-[200px]">{profile.display_name || profile.email}</span>
              </div>
            )}
          </div>
          <p className="mt-3 text-sm max-w-3xl text-slate-600 dark:text-muted-foreground leading-relaxed">
            {t("participation.hero.description")}
          </p>
        </div>
        
        {/* Glow decoration */}
        <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-amber-200/30 blur-3xl dark:bg-amber-500/10 pointer-events-none" />
      </header>

      {/* Main Stats Summary & Grid */}
      <div className="grid gap-6 lg:grid-cols-[1fr_2.5fr]">
        {/* Total contributions premium summary */}
        <div className="relative overflow-hidden rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-500 to-amber-600 p-6 text-white shadow-lg dark:border-amber-800/40">
          <div className="relative z-10 flex flex-col justify-between h-full min-h-[160px]">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-amber-100/80">
                {t("participation.stats.total")}
              </p>
              <h2 className="text-5xl font-black mt-2 tracking-tight">
                {stats.total_interactions}
              </h2>
            </div>
            
            <div className="mt-6">
              <Link 
                href="/live" 
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-xs font-bold text-amber-700 shadow-sm transition hover:bg-slate-50 active:scale-[0.98] w-full"
              >
                <PlayCircle className="h-4 w-4" />
                {t("participation.actions.backToArena")}
              </Link>
            </div>
          </div>
          
          {/* Subtle design circles */}
          <div className="absolute -right-10 -bottom-10 h-32 w-32 rounded-full border-4 border-white/10" />
          <div className="absolute right-1/4 -top-8 h-24 w-24 rounded-full bg-white/5" />
        </div>

        {/* Detailed Breakdown Grid */}
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
          {statItems.map((item, idx) => (
            <div 
              key={idx} 
              className={`flex items-center justify-between rounded-2xl border border-stone-200 bg-white/80 p-5 shadow-sm transition duration-200 ${item.borderColor} hover:-translate-y-[2px] dark:border-border dark:bg-card/85`}
            >
              <div className="space-y-1 pr-2">
                <span className="text-xs font-semibold text-slate-500 dark:text-muted-foreground block leading-tight">
                  {item.label}
                </span>
                <span className="text-2xl font-bold text-slate-900 dark:text-foreground block">
                  {item.value}
                </span>
              </div>
              <div className={`rounded-xl p-3 ${item.colorClass} flex-shrink-0`}>
                <item.icon className="h-5 w-5" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Activity Timeline */}
      <div className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm dark:border-border dark:bg-card">
        <div className="flex items-center justify-between border-b border-stone-100 pb-4 dark:border-border">
          <div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-foreground flex items-center gap-2">
              <Activity className="h-5 w-5 text-amber-500" />
              {t("participation.recentActivity.title")}
            </h3>
            <p className="text-xs text-slate-500 dark:text-muted-foreground">
              {t("participation.recentActivity.subtitle")}
            </p>
          </div>
        </div>

        <div className="mt-6 relative">
          {recent_activity.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-stone-200 bg-stone-50/70 p-10 text-center text-sm text-slate-500 dark:border-border dark:bg-muted/30 dark:text-muted-foreground">
              <Award className="h-10 w-10 text-stone-300 dark:text-stone-700 mx-auto mb-3" />
              {t("participation.recentActivity.empty")}
            </div>
          ) : (
            <div className="space-y-6 before:absolute before:left-4 before:top-2 before:bottom-2 before:w-[2px] before:bg-slate-100 dark:before:bg-slate-800">
              {recent_activity.map((item) => (
                <div key={item.id} className="relative pl-10 group">
                  {/* Timeline indicator node */}
                  <div className="absolute left-[9px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-amber-500 shadow-sm transition group-hover:scale-110 dark:border-card" />
                  
                  <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl border border-stone-100 bg-stone-50/50 p-4 transition hover:bg-stone-50 dark:border-border/60 dark:bg-muted/10 dark:hover:bg-muted/20">
                    <div className="space-y-2 max-w-xl">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${getActivityColor(item.type)}`}>
                          {formatActivityType(item.type)}
                        </span>
                        
                        <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          <time 
                            dateTime={item.created_at} 
                            title={new Date(item.created_at).toLocaleString()}
                          >
                            {relativeTime(item.created_at)}
                          </time>
                        </span>
                      </div>

                      {/* Display detail snippets cleanly */}
                      <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed font-medium">
                        {item.details && typeof item.details === "object" ? (
                          <div className="space-y-1">
                            {item.details.prediction && (
                              <p>
                                <span className="text-xs text-muted-foreground font-normal">Predicted Winner:</span>{" "}
                                <strong className="text-amber-600 dark:text-amber-400">{item.details.prediction}</strong>
                              </p>
                            )}
                            {item.details.model && (
                              <p>
                                <span className="text-xs text-muted-foreground font-normal">Target:</span>{" "}
                                <strong>{item.details.model}</strong>
                              </p>
                            )}
                            {item.details.critique && (
                              <p className="italic bg-card/60 rounded px-2 py-1 text-xs border border-border mt-1">
                                &ldquo;{item.details.critique.length > 150 ? item.details.critique.slice(0, 150) + "..." : item.details.critique}&rdquo;
                              </p>
                            )}
                            {item.details.directive && (
                              <p className="bg-card/60 rounded px-2 py-1 text-xs border border-border mt-1 font-mono">
                                Directive: {item.details.directive}
                              </p>
                            )}
                            {item.details.winner && item.details.loser && (
                              <p className="text-xs text-muted-foreground">
                                Voted <strong className="text-slate-800 dark:text-slate-200">{item.details.winner}</strong> over {item.details.loser}
                              </p>
                            )}
                          </div>
                        ) : (
                          <span>Performed interaction action</span>
                        )}
                      </div>
                    </div>

                    {item.debate_id && (
                      <Link 
                        href={`/runs/${item.debate_id}`} 
                        className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 hover:text-amber-600 dark:text-amber-400 dark:hover:text-amber-300 bg-white dark:bg-card border border-stone-200/60 dark:border-border/80 rounded-lg px-3 py-1.5 shadow-sm transition hover:shadow"
                      >
                        <span>{t("participation.actions.viewReplay")}</span>
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
