export type ModeId = "arena" | "debate" | "compare" | "oracle" | "redteam";

export type ModeDescriptor = {
  id: ModeId;
  /** English fallback name; UI must translate via nameKey through useI18n(). */
  name: string;
  /** English fallback blurb; UI must translate via blurbKey through useI18n(). */
  blurb: string;
  nameKey: string;
  blurbKey: string;
  panelSize: readonly [number, number];
  crossTalk: boolean;
  rounds: number;
  synthesis: boolean;
};

export const MODES: readonly ModeDescriptor[] = [
  {
    id: "arena",
    name: "Arena",
    blurb: "Independent model perspectives, then a synthesis.",
    nameKey: "mode.arena.name",
    blurbKey: "mode.arena.blurb",
    panelSize: [2, 6],
    crossTalk: false,
    rounds: 1,
    synthesis: true,
  },
  {
    id: "debate",
    name: "Debate",
    blurb: "Models challenge one another through structured rounds.",
    nameKey: "mode.debate.name",
    blurbKey: "mode.debate.blurb",
    panelSize: [2, 6],
    crossTalk: true,
    rounds: 3,
    synthesis: true,
  },
  {
    id: "compare",
    name: "Compare",
    blurb: "Side-by-side answers with no synthesized verdict.",
    nameKey: "mode.compare.name",
    blurbKey: "mode.compare.blurb",
    panelSize: [2, 6],
    crossTalk: false,
    rounds: 1,
    synthesis: false,
  },
  {
    id: "oracle",
    name: "Oracle",
    blurb: "One deep-reasoning model for a focused answer.",
    nameKey: "mode.oracle.name",
    blurbKey: "mode.oracle.blurb",
    panelSize: [1, 1],
    crossTalk: false,
    rounds: 1,
    synthesis: true,
  },
  {
    id: "redteam",
    name: "RedTeam",
    blurb: "An adversarial pass against a draft decision.",
    nameKey: "mode.redteam.name",
    blurbKey: "mode.redteam.blurb",
    panelSize: [1, 2],
    crossTalk: true,
    rounds: 1,
    synthesis: true,
  },
];

export function getMode(id: string | null | undefined): ModeDescriptor {
  return MODES.find((mode) => mode.id === id) ?? MODES[0];
}
