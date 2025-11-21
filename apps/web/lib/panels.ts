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
      { id: "gpt-4o-mini", label: "GPT-4o Mini" },
      { id: "gpt-4.1-mini", label: "GPT-4.1 Mini" },
    ],
  },
  {
    key: "anthropic",
    label: "Anthropic",
    models: [
      { id: "claude-3-5-sonnet", label: "Claude 3.5 Sonnet" },
      { id: "claude-3-5-haiku", label: "Claude 3.5 Haiku" },
    ],
  },
  {
    key: "google",
    label: "Google Gemini",
    models: [
      { id: "gemini-1.5-flash", label: "Gemini 1.5 Flash" },
      { id: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
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
        model: "gpt-4o-mini",
        role_profile: "optimist",
        temperature: 0.7,
      },
      {
        seat_id: "risk_officer",
        display_name: "Risk Officer",
        provider_key: "anthropic",
        model: "claude-3-5-sonnet",
        role_profile: "risk_officer",
        temperature: 0.4,
      },
      {
        seat_id: "architect",
        display_name: "Systems Architect",
        provider_key: "openai",
        model: "gpt-4.1-mini",
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
        model: "claude-3-5-sonnet",
        role_profile: "risk_officer",
        temperature: 0.3,
      },
      {
        seat_id: "optimist",
        display_name: "Optimist",
        provider_key: "openai",
        model: "gpt-4o-mini",
        role_profile: "optimist",
        temperature: 0.6,
      },
      {
        seat_id: "architect",
        display_name: "Systems Architect",
        provider_key: "google",
        model: "gemini-1.5-pro",
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
