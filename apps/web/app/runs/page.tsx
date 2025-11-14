import RunsTable from "@/components/consultaion/consultaion/runs-table";
import { getMe } from "@/lib/auth";
import { getMyDebates, getTeams } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
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

  const [debateResponse, teamList] = await Promise.all([
    getMyDebates({ limit: 100, offset: 0 }).catch(() => []),
    getTeams().catch(() => []),
  ]);
  const items = Array.isArray(debateResponse) ? debateResponse : Array.isArray(debateResponse?.items) ? debateResponse.items : [];

  return (
    <main id="main" className="h-full space-y-6 py-6">
      <header className="rounded-3xl border border-stone-200 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 shadow">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Your archive</p>
        <h1 className="mt-1 text-3xl font-semibold text-stone-900">Saved runs</h1>
        <p className="text-sm text-stone-600">Filter personal, shared, or global (admin) debates and share new runs with a team.</p>
      </header>
      <section className="rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <RunsTable items={items} teams={teamList} profile={profile} />
      </section>
    </main>
  );
}
