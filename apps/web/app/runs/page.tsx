import RunsTable from "@/components/consultaion/consultaion/runs-table";
import RateLimitBanner from "@/components/parliament/RateLimitBanner";
import SmartSearch from "@/components/parliament/SmartSearch";
import RunsShowcase from "@/components/parliament/RunsShowcase";
import { getMe } from "@/lib/auth";
import { ApiError, getMyDebates, getRateLimitInfo, getTeams, isAuthError } from "@/lib/api";
import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type RunsPageProps = {
  searchParams: Promise<{ q?: string; status?: string }>;
};

export default async function RunsPage({ searchParams }: RunsPageProps) {
  const params = await searchParams;
  const query = params?.q ?? "";
  const status = params?.status ?? "";
  const profile = await getMe();
  if (!profile) {
    return (
      <main id="main" className="flex h-full items-center justify-center py-6">
        <div className="rounded-lg border border-border bg-card p-6 text-center">
          <p className="text-sm text-muted-foreground">Please sign in to view your runs.</p>
          <a href="/login" className="mt-3 inline-flex items-center rounded bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
            Go to Login
          </a>
        </div>
      </main>
    );
  }

  let rateLimitNotice: { detail: string; resetAt?: string } | null = null;
  let debateResponse: Awaited<ReturnType<typeof getMyDebates>> | null = null;
  try {
    debateResponse = await getMyDebates({
      limit: 100,
      offset: 0,
      q: query || undefined,
      status: status || undefined,
    });
  } catch (error) {
    if (error instanceof ApiError) {
      const info = getRateLimitInfo(error);
      if (info) {
        rateLimitNotice = info;
      } else if (isAuthError(error)) {
        redirect("/login");
      } else {
        throw error;
      }
    } else {
      throw error;
    }
  }
  const teamList = await getTeams().catch((error) => {
    if (error instanceof ApiError && isAuthError(error)) {
      redirect("/login");
    }
    return [];
  });
  const items = rateLimitNotice ? [] : debateResponse?.items ?? [];
  const searchItems = items.map((item) => ({ id: item.id, prompt: item.prompt ?? "" }));

  return (
    <main id="main" className="h-full space-y-8 py-6">
      <header className="rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-amber-50/70 p-6 shadow-[0_24px_60px_rgba(112,73,28,0.14)] dark:border-amber-900/50 dark:from-stone-900 dark:via-stone-900 dark:to-amber-950/20">
        <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-700">Your archive</p>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="heading-serif text-3xl font-semibold text-amber-900 dark:text-amber-50">Saved runs</h1>
          <span className="rounded-full border border-amber-200/70 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-amber-800 shadow-inner shadow-amber-900/5 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
            Parliament UI
          </span>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-stone-700 dark:text-amber-50/80">
          Filter personal, shared, or global debates, switch scopes, and jump straight to an amber-tinted run card. Keyboard-friendly and WCAG-safe.
        </p>
      </header>

      <section className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <SmartSearch items={searchItems} initialQuery={query} />
        <div className="rounded-2xl border border-amber-200/70 bg-white/85 p-4 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/40 dark:bg-stone-900/70">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-amber-800 dark:text-amber-200">Status overview</p>
          <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-stone-700 dark:text-amber-50/80">
            <div className="rounded-xl border border-amber-100/80 bg-amber-50/80 p-3 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-200">Total runs</p>
              <p className="mt-1 text-2xl font-semibold text-amber-900 dark:text-amber-50">{items.length}</p>
            </div>
            <div className="rounded-xl border border-amber-100/80 bg-amber-50/80 p-3 shadow-inner shadow-amber-900/5 dark:border-amber-900/40 dark:bg-amber-950/30">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-200">In progress</p>
              <p className="mt-1 text-2xl font-semibold text-amber-900 dark:text-amber-50">
                {items.filter((item) => item.status === "running").length}
              </p>
            </div>
          </div>
          <p className="mt-3 text-xs text-stone-600 dark:text-amber-100/70">
            Quick glance at your chamber. Hover cards lift gently; focus states glow amber for keyboard users.
          </p>
        </div>
      </section>

      {rateLimitNotice ? (
        <RateLimitBanner detail={rateLimitNotice.detail} resetAt={rateLimitNotice.resetAt} />
      ) : null}

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-700">Runs list</p>
            <h2 className="heading-serif text-xl font-semibold text-amber-900 dark:text-amber-50">Amber cards</h2>
          </div>
          <span className="text-xs text-stone-600 dark:text-amber-100/70">Hover to feel the micro-interactions.</span>
        </div>
        <RunsShowcase runs={items} />
      </section>

      <section className="rounded-3xl border border-amber-200/70 bg-white/90 p-6 shadow-[0_18px_40px_rgba(112,73,28,0.12)] dark:border-amber-900/50 dark:bg-stone-900/70">
        <RunsTable
          items={items}
          teams={teamList}
          profile={profile}
          initialQuery={query}
          initialStatus={status || null}
        />
      </section>
    </main>
  );
}
