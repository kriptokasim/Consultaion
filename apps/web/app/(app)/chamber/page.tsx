"use client";

import VotingChamber from "@/components/parliament/VotingChamber";
import type { ScoreItem, Member } from "@/components/parliament/types";

const demoScores: ScoreItem[] = [
  { persona: "Analyst", score: 8.2 },
  { persona: "Critic", score: 6.1 },
  { persona: "Builder", score: 7.4 },
  { persona: "Sage", score: 5.6 },
  { persona: "Oracle", score: 9.0 },
];

const demoMembers: Member[] = [
  { id: "analyst", name: "Analyst", role: "agent" },
  { id: "critic", name: "Critic", role: "critic" },
  { id: "builder", name: "Builder", role: "agent" },
  { id: "sage", name: "Sage", role: "agent" },
  { id: "oracle", name: "Oracle", role: "judge" },
];

export default function ChamberPage() {
  return (
    <main id="main" className="space-y-6 p-4">
      <section className="rounded-3xl border border-amber-100 bg-gradient-to-br from-amber-50 via-white to-stone-50 p-6 shadow-sm">
        <div className="flex flex-col gap-3">
          <h1 className="text-2xl font-semibold text-stone-900">Consultaion visualization</h1>
          <p className="text-sm text-stone-700">
            This chamber view shows how Aye and Nay votes flow for the latest debates. When a model wins clearly, its
            seat glows as the Consultaion champion. Load a debate to see live flows, or explore the demo below.
          </p>
        </div>
        <div className="mt-4 rounded-2xl border border-amber-100 bg-white/80 px-3 py-2 text-sm text-stone-600">
          Latest debate on deck: Bring a prompt to the <a className="text-amber-700 underline" href="/">live page</a>{" "}
          and summon a session to watch the chamber animate in real time.
        </div>
      </section>
      <VotingChamber scores={demoScores} members={demoMembers} />
    </main>
  );
}
