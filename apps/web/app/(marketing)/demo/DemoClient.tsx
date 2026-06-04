"use client";

import ArenaRunView from "@/components/arena/ArenaRunView";
import type { DebateDetail, DebateEvent } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/client";

const DEMO_DEBATE: any = {
  id: "demo-run-investor",
  prompt: "Should a B2B SaaS startup prioritize growth or profitability in its first 12 months?",
  status: "completed",
  is_public: true,
  created_at: new Date().toISOString(),
  final_meta: {
    models: [
      {
        model_id: "gpt-4o",
        display_name: "GPT-4o",
        provider: "openai",
        logo_url: "https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg",
        success: true,
      },
      {
        model_id: "claude-3-opus",
        display_name: "Claude 3 Opus",
        provider: "anthropic",
        logo_url: "https://upload.wikimedia.org/wikipedia/commons/7/78/Anthropic_logo.svg",
        success: true,
      },
      {
        model_id: "gemini-1.5-pro",
        display_name: "Gemini 1.5 Pro",
        provider: "google",
        logo_url: "https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg",
        success: true,
      },
      {
        model_id: "deepseek-chat",
        display_name: "DeepSeek V3",
        provider: "deepseek",
        success: true,
      }
    ]
  }
};

const DEMO_EVENTS: any[] = [
  {
    type: "arena_response",
    model_id: "gpt-4o",
    display_name: "GPT-4o",
    provider: "openai",
    logo_url: "https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg",
    content: "Growth should be the primary focus. In the early stages, capturing market share and establishing brand presence creates a moat against competitors. Investors typically value top-line revenue growth over early profitability because it proves product-market fit. Profitability can be optimized later through economies of scale and pricing power once the customer base is locked in.",
    success: true
  },
  {
    type: "arena_response",
    model_id: "claude-3-opus",
    display_name: "Claude 3 Opus",
    provider: "anthropic",
    logo_url: "https://upload.wikimedia.org/wikipedia/commons/7/78/Anthropic_logo.svg",
    content: "This depends heavily on the funding environment. In a zero-interest-rate environment, growth at all costs was rewarded. Today, investors demand \"efficient growth.\" You shouldn't ignore growth, but you must prove your unit economics (LTV:CAC ratio) are sound. Burning cash on unprofitable marketing channels just to inflate top-line metrics is a recipe for disaster. Prioritize sustainable growth with a clear path to profitability.",
    success: true
  },
  {
    type: "arena_response",
    model_id: "gemini-1.5-pro",
    display_name: "Gemini 1.5 Pro",
    provider: "google",
    logo_url: "https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg",
    content: "Profitability is crucial for survival if you are bootstrapped. If you rely entirely on external funding, you are at the mercy of VC timelines. By achieving default-alive status (profitability), you gain leverage in negotiations and control your own destiny. Focus on finding a niche, serving them exceptionally well, and charging enough to cover your costs from day one.",
    success: true
  },
  {
    type: "arena_response",
    model_id: "deepseek-chat",
    display_name: "DeepSeek V3",
    provider: "deepseek",
    content: "A balanced approach is necessary. You need enough growth to attract talent and capital, but enough profitability (or strong margins) to survive downturns. The first 12 months should be about discovering a repeatable sales motion, not just maximizing revenue. Once the motion is repeatable and profitable on a per-customer basis, then you aggressively scale.",
    success: true
  },
  {
    type: "arena_synthesis",
    text: "While the models offer varying perspectives, a clear consensus emerges when adjusting for current market conditions:\n\n**1. The End of \"Growth at All Costs\"**\nClaude and DeepSeek highlight that the era of subsidizing growth with endless VC capital is over. While GPT-4o correctly notes that market share is a moat, all models agree that growth must now be *efficient*.\n\n**2. Unit Economics Over Pure Profit**\nIn the first 12 months, achieving absolute profitability is less critical than proving profitable unit economics (LTV:CAC). You don't need to be profitable, but every new customer you acquire must eventually be profitable.\n\n**3. Funding Dictates Strategy**\nGemini points out a crucial variable: your capital structure. Bootstrapped founders must prioritize profitability immediately to survive (\"default alive\"). Venture-backed founders should prioritize growth, but only *after* establishing a repeatable, efficient sales motion.\n\n**Final Verdict:** Do not prioritize absolute profitability in year one, but do not pursue reckless growth either. **Prioritize efficient, repeatable growth.** Spend your first 12 months proving that your unit economics work, which will give you the leverage to either raise capital or achieve profitability on your own terms."
  }
];

export default function DemoClient() {
  const { t } = useI18n();

  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="mb-8 text-center">
        <p className="text-sm font-semibold uppercase tracking-wider text-primary dark:text-blue-400 mb-2">Interactive Demo</p>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-4xl">
          Multi-Model AI in Action
        </h1>
        <p className="mt-4 text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto">
          Experience how Consultaion compares top AI models and synthesizes their insights into one definitive answer.
        </p>
      </div>

      <ArenaRunView 
        debate={DEMO_DEBATE as any} 
        events={DEMO_EVENTS as any} 
        profile={null} 
      />
    </div>
  );
}
