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
      <VotingChamber scores={demoScores} members={demoMembers} />
    </main>
  );
}
