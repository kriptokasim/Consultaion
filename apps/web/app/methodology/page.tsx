import Brand from "@/components/parliament/Brand";

export const dynamic = "force-dynamic";

export default function MethodologyPage() {
  return (
    <main id="main" className="space-y-6 p-4">
      <header className="rounded-3xl border border-stone-200 bg-gradient-to-br from-white via-amber-50 to-stone-50 p-6 shadow">
        <div className="flex items-center gap-3">
          <Brand variant="mark" height={28} />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Rosetta Chamber</p>
            <h1 className="text-3xl font-semibold text-stone-900">Methodology</h1>
          </div>
        </div>
        <p className="mt-3 max-w-3xl text-sm text-stone-600">
          Consultaion combines per-judge pairwise ballots, Elo-style updates, and Wilson confidence intervals to keep the
          leaderboard statistically honest.
        </p>
      </header>
      <section className="space-y-6 rounded-3xl border border-stone-200 bg-white p-6 shadow-sm">
        <article>
          <h2 className="text-xl font-semibold text-stone-900">Pairwise votes</h2>
          <p className="mt-2 text-sm text-stone-600">
            Each judge compares every persona head-to-head. Ties are dropped. We log the winner, loser, judge, optional
            category, and timestamp in <code className="rounded bg-stone-100 px-1">pairwise_vote</code>.
          </p>
        </article>
        <article>
          <h2 className="text-xl font-semibold text-stone-900">Elo + Bradley–Terry</h2>
          <p className="mt-2 text-sm text-stone-600">
            Ratings start at 1500. We apply Elo updates with <strong>K=32</strong> for the first 15 matches, then
            <strong> K=24</strong>. This mirrors the Bradley–Terry logistic model and is stable for live updates. Future
            releases will expose a full BT fit once enough matches accumulate.
          </p>
        </article>
        <article>
          <h2 className="text-xl font-semibold text-stone-900">Wilson confidence interval</h2>
          <p className="mt-2 text-sm text-stone-600">
            Win rate is shown with a 95% Wilson interval. New personas get a <span className="font-semibold">NEW</span>{" "}
            badge until they reach 15 matches. This guards against lucky streaks and makes it safe to highlight strong
            performers publicly.
          </p>
        </article>
        <article>
          <h2 className="text-xl font-semibold text-stone-900">Update cadence</h2>
          <p className="mt-2 text-sm text-stone-600">
            Ratings update immediately after each debate. Manual recomputes are available via{" "}
            <code className="rounded bg-stone-100 px-1">POST /ratings/update/&lt;debate_id&gt;</code> for admins.
          </p>
        </article>
        <article>
          <h2 className="text-xl font-semibold text-stone-900">Anti-gaming</h2>
          <p className="mt-2 text-sm text-stone-600">
            Runs inherit the creator’s scope (private or team). Public leaderboard rows ignore private debates unless
            shared. Abusive streaks can be zeroed by clearing pairwise rows for the offending debate.
          </p>
        </article>
      </section>
    </main>
  );
}
