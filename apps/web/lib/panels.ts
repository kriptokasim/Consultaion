export type PanelSeatConfig = {
  seat_id: string;
  display_name: string;
  provider_key: string;
  model: string;
  role_profile: string;
  temperature?: number;
};

export type PanelConfigPayload = {
  engine_version: string;
  seats: PanelSeatConfig[];
};

export const ROLE_PROFILES = [
  { slug: "optimist", title: "Optimist", description: "Highlights upside and creative opportunities." },
  { slug: "risk_officer", title: "Risk Officer", description: "Surfaces risks and failure modes." },
  { slug: "architect", title: "Systems Architect", description: "Designs systems and trade-offs." },
];

export const PROVIDER_OPTIONS = [
  {
    key: "openai",
    label: "OpenAI",
    models: [
      { id: "gpt4o-mini", label: "GPT-4o Mini" },
      { id: "gpt4o-deep", label: "GPT-4o" },
    ],
  },
  {
    key: "anthropic",
    label: "Anthropic",
    models: [
      { id: "claude-sonnet", label: "Claude 3.5 Sonnet" },
      { id: "claude-haiku", label: "Claude 3 Haiku" },
    ],
  },
  {
    key: "google",
    label: "Google Gemini",
    models: [
      { id: "gemini-2-flash", label: "Gemini 2.0 Flash" },
      { id: "gemini-2-5-pro", label: "Gemini 2.5 Pro" },
    ],
  },
];

export const PANEL_PRESETS: Array<{ id: string; label: string; seats: PanelSeatConfig[] }> = [
  {
    id: "balanced",
    label: "Balanced Trio",
    seats: [
      {
        seat_id: "optimist",
        display_name: "Optimist",
        provider_key: "openai",
        model: "gpt4o-mini",
        role_profile: "optimist",
        temperature: 0.7,
      },
      {
        seat_id: "risk_officer",
        display_name: "Risk Officer",
        provider_key: "anthropic",
        model: "claude-sonnet",
        role_profile: "risk_officer",
        temperature: 0.4,
      },
      {
        seat_id: "architect",
        display_name: "Systems Architect",
        provider_key: "google",
        model: "gemini-2-flash",
        role_profile: "architect",
        temperature: 0.5,
      },
    ],
  },
  {
    id: "risk_heavy",
    label: "Risk Heavy",
    seats: [
      {
        seat_id: "risk_officer",
        display_name: "Risk Officer",
        provider_key: "anthropic",
        model: "claude-sonnet",
        role_profile: "risk_officer",
        temperature: 0.3,
      },
      {
        seat_id: "optimist",
        display_name: "Optimist",
        provider_key: "openai",
        model: "gpt4o-mini",
        role_profile: "optimist",
        temperature: 0.6,
      },
      {
        seat_id: "architect",
        display_name: "Systems Architect",
        provider_key: "google",
        model: "gemini-2-5-pro",
        role_profile: "architect",
        temperature: 0.4,
      },
    ],
  },
];

export function defaultPanelConfig(): PanelConfigPayload {
  return {
    engine_version: "parliament-v1",
    seats: PANEL_PRESETS[0].seats.map((seat) => ({ ...seat })),
  };
}
