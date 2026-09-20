export type ModeId = "arena" | "debate" | "compare" | "oracle" | "redteam";

export type ModeDescriptor = {
  id: ModeId;
  name: string;
  blurb: string;
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
    panelSize: [2, 6],
    crossTalk: false,
    rounds: 1,
    synthesis: true,
  },
  {
    id: "debate",
    name: "Debate",
    blurb: "Models challenge one another through structured rounds.",
    panelSize: [2, 6],
    crossTalk: true,
    rounds: 3,
    synthesis: true,
  },
  {
    id: "compare",
    name: "Compare",
    blurb: "Side-by-side answers with no synthesized verdict.",
    panelSize: [2, 6],
    crossTalk: false,
    rounds: 1,
    synthesis: false,
  },
  {
    id: "oracle",
    name: "Oracle",
    blurb: "One deep-reasoning model for a focused answer.",
    panelSize: [1, 1],
    crossTalk: false,
    rounds: 1,
    synthesis: true,
  },
  {
    id: "redteam",
    name: "RedTeam",
    blurb: "An adversarial pass against a draft decision.",
    panelSize: [1, 2],
    crossTalk: true,
    rounds: 1,
    synthesis: true,
  },
];

export function getMode(id: string | null | undefined): ModeDescriptor {
  return MODES.find((mode) => mode.id === id) ?? MODES[0];
}
