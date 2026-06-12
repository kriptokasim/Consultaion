"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import ArenaRunView from "@/components/arena/ArenaRunView";
import { useI18n } from "@/lib/i18n/client";
import { trackEvent } from "@/lib/analytics";
import { Button } from "@/components/ui/button";
import { Sparkles, Terminal, Play, CheckCircle, ArrowRight, ShieldCheck, Mail } from "lucide-react";

interface PromptPreset {
  id: string;
  title: string;
  prompt: string;
  models: any[];
  events: any[];
}

const PRESETS: PromptPreset[] = [
  {
    id: "growth-vs-profit",
    title: "SaaS: Growth vs Profitability",
    prompt: "Should a B2B SaaS startup prioritize growth or profitability in its first 12 months?",
    models: [
      { model_id: "gpt-4o", display_name: "GPT-4o", provider: "openai", success: true },
      { model_id: "claude-3-opus", display_name: "Claude 3 Opus", provider: "anthropic", success: true },
      { model_id: "gemini-1.5-pro", display_name: "Gemini 1.5 Pro", provider: "google", success: true },
      { model_id: "deepseek-chat", display_name: "DeepSeek V3", provider: "deepseek", success: true }
    ],
    events: [
      {
        type: "arena_response",
        model_id: "gpt-4o",
        display_name: "GPT-4o",
        provider: "openai",
        content: "Growth should be the primary focus. In the early stages, capturing market share and establishing brand presence creates a moat against competitors. Investors typically value top-line revenue growth over early profitability because it proves product-market fit. Profitability can be optimized later through economies of scale and pricing power once the customer base is locked in.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "claude-3-opus",
        display_name: "Claude 3 Opus",
        provider: "anthropic",
        content: "This depends heavily on the funding environment. In a zero-interest-rate environment, growth at all costs was rewarded. Today, investors demand \"efficient growth.\" You shouldn't ignore growth, but you must prove your unit economics (LTV:CAC ratio) are sound. Burning cash on unprofitable marketing channels just to inflate top-line metrics is a recipe for disaster. Prioritize sustainable growth with a clear path to profitability.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "gemini-1.5-pro",
        display_name: "Gemini 1.5 Pro",
        provider: "google",
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
    ]
  },
  {
    id: "monolith-vs-microservices",
    title: "Architecture: Monolith vs Microservices",
    prompt: "Should a new engineering team build a pre-product-market-fit app as a monolith or microservices?",
    models: [
      { model_id: "gpt-4o", display_name: "GPT-4o", provider: "openai", success: true },
      { model_id: "claude-3-opus", display_name: "Claude 3 Opus", provider: "anthropic", success: true },
      { model_id: "gemini-1.5-pro", display_name: "Gemini 1.5 Pro", provider: "google", success: true },
      { model_id: "deepseek-chat", display_name: "DeepSeek V3", provider: "deepseek", success: true }
    ],
    events: [
      {
        type: "arena_response",
        model_id: "gpt-4o",
        display_name: "GPT-4o",
        provider: "openai",
        content: "Build a monolith first. For pre-PMF startups, speed of iteration is the ultimate metric. A monolith allows developers to change business logic, database schemas, and data boundaries instantly without coordinating across network API contracts. Deploying, logging, and monitoring a single codebase is simple, which allows the engineering team to focus entirely on feature testing and customer feedback.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "claude-3-opus",
        display_name: "Claude 3 Opus",
        provider: "anthropic",
        content: "Start with a modular monolith. Avoid early microservices, as they introduce network latency, distributed transactions, data consistency hurdles, and heavy operational overhead (Kubernetes, service meshes, config syncing). However, write clean separation lines inside your monolith (like domains or namespaces). This gives you the speed of a monolith with a simple, painless migration path to microservices later when scaling requirements warrant it.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "gemini-1.5-pro",
        display_name: "Gemini 1.5 Pro",
        provider: "google",
        content: "Unless you have a specific technical reason (e.g. your application inherently deals with separate scaling nodes like media encoding or real-time streaming), microservices are a premature optimization. They dilute engineering focus. Start with a single deployable unit, keep the database schema unified, and defer architectural splits until you actually have load and organizational scaling challenges.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "deepseek-chat",
        display_name: "DeepSeek V3",
        provider: "deepseek",
        content: "Microservices require significant DevOps setup. In pre-PMF phase, team members wear many hats, and you cannot afford to dedicate valuable headcount to managing cloud infra and microservices communication issues. Use a monolith using cloud platform capabilities (like serverless or simple hosted containers) to minimize operation overhead.",
        success: true
      },
      {
        type: "arena_synthesis",
        text: "There is strong, unanimous consensus among all four models on the core architectural path:\n\n**1. Absolute Monolithic Preference**\nAll models emphatically state that building a microservices architecture for a pre-product-market-fit application is a premature optimization that leads to startup failure. Iteration speed, not scale, is your primary constraint.\n\n**2. Modular Monolith as the Moat**\nClaude introduces a key best practice: the *modular monolith*. Keep codebase boundaries logical and separated while keeping database schemas and deployment pipelines unified. This prevents spaghetti code without adding distributed systems overhead.\n\n**3. Operational Overhead**\nDeepSeek and Gemini highlight the drain on headcount: managing services takes time away from building features. \n\n**Final Verdict:** **Choose a modular monolith.** Keep your codebase simple, operations unified, and domain boundaries clean. Do not split into microservices until scaling or organizational demands make it impossible to continue within a single repository."
      }
    ]
  },
  {
    id: "agents-vs-copilots",
    title: "Market: AI Agents vs Copilots",
    prompt: "Will autonomous AI agents or assistive copilots dominate the enterprise developer tooling market by 2027?",
    models: [
      { model_id: "gpt-4o", display_name: "GPT-4o", provider: "openai", success: true },
      { model_id: "claude-3-opus", display_name: "Claude 3 Opus", provider: "anthropic", success: true },
      { model_id: "gemini-1.5-pro", display_name: "Gemini 1.5 Pro", provider: "google", success: true },
      { model_id: "deepseek-chat", display_name: "DeepSeek V3", provider: "deepseek", success: true }
    ],
    events: [
      {
        type: "arena_response",
        model_id: "gpt-4o",
        display_name: "GPT-4o",
        provider: "openai",
        content: "Autonomous AI agents will dominate. By 2027, LLM context windows, reasoning models, and agentic loop libraries will advance to a point where agents can independently resolve complex git issues, test regressions, and perform codebase migrations. Copilots will be seen as legacy tab-completion widgets, while agents will handle full software engineering lifecycle tasks.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "claude-3-opus",
        display_name: "Claude 3 Opus",
        provider: "anthropic",
        content: "Assistive copilots will remain dominant, but they will expand into \"interactive teammates.\" Full autonomy (agents) in codebases faces huge trust, safety, compliance, and hallucination barriers in enterprise settings. Developers want human-in-the-loop oversight to sign off on architectural choices and pull requests. The successful tools will be copilots with agentic sub-capabilities.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "gemini-1.5-pro",
        display_name: "Gemini 1.5 Pro",
        provider: "google",
        content: "The market will bifurcate. For repetitive, boilerplate tasks (e.g. generating API integrations, updating dependencies, basic refactoring), autonomous agents will handle the work. For core product architecture and complex algorithm designs, assistive copilots that interact closely with developers will be the standard. Autonomy will be a spectrum, not a binary dominance.",
        success: true
      },
      {
        type: "arena_response",
        model_id: "deepseek-chat",
        display_name: "DeepSeek V3",
        provider: "deepseek",
        content: "Copilots will dominate due to cost and latency. Agentic loops are extremely expensive and slow because they perform dozens of LLM calls to test and correct code. Until token costs drop significantly and latency is solved, enterprises will prefer real-time, low-latency copilots that provide instant productivity boosts.",
        success: true
      },
      {
        type: "arena_synthesis",
        text: "The models diverge on whether total autonomy is achievable or desired, but converge on a hybrid outlook:\n\n**1. Autonomy is a Spectrum, Not a Binary Choice**\nGemini and Claude highlight that tools will exist on a continuum. The idea of a completely hands-off agent replacing developers is unrealistic for enterprise compliance, but copilots will become highly agentic (running tests and editing multiple files under developer supervision).\n\n**2. The Cost and Trust Hurdles**\nDeepSeek (cost/latency) and Claude (trust/safety) outline the critical barriers to pure agent adoption. Enterprises cannot trust automated agents to commit directly to production code without developer validation.\n\n**3. Legacy Tab-Completion is Dead**\nGPT-4o is correct that simple line-completion copilots are outdated. The future belongs to tools that can execute full tasks autonomously but keep developers in control.\n\n**Final Verdict:** **Assistive copilots with advanced agentic workflows will dominate.** Enterprise developers will not be replaced by autonomous agents; instead, they will manage agent sub-tasks from their IDEs, ensuring continuous human-in-the-loop validation."
      }
    ]
  }
];

export default function DemoClient() {
  const [selectedPreset, setSelectedPreset] = useState<PromptPreset | null>(null);
  const [simulationState, setSimulationState] = useState<"idle" | "dispatching" | "typing" | "synthesizing" | "finished">("idle");
  const [visibleEvents, setVisibleEvents] = useState<any[]>([]);
  const [progressText, setProgressText] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [email, setEmail] = useState("");
  const [emailSubmitted, setEmailSubmitted] = useState(false);
  const [isSubmittingEmail, setIsSubmittingEmail] = useState(false);

  // Run simulation timeline
  useEffect(() => {
    if (!selectedPreset || simulationState === "idle") return;

    if (simulationState === "dispatching") {
      setProgressPercent(10);
      setProgressText("Initializing multi-agent session...");
      const t1 = setTimeout(() => {
        setProgressPercent(30);
        setProgressText("Dispatching prompt to GPT-4o, Claude, Gemini, and DeepSeek...");
      }, 700);

      const t2 = setTimeout(() => {
        setSimulationState("typing");
      }, 1500);

      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
      };
    }

    if (simulationState === "typing") {
      setProgressPercent(40);
      setProgressText("Awaiting response from OpenAI GPT-4o...");
      
      const t1 = setTimeout(() => {
        setVisibleEvents([selectedPreset.events[0]]);
        setProgressPercent(55);
        setProgressText("Awaiting response from Anthropic Claude...");
      }, 1200);

      const t2 = setTimeout(() => {
        setVisibleEvents([selectedPreset.events[0], selectedPreset.events[1]]);
        setProgressPercent(70);
        setProgressText("Awaiting response from Google Gemini...");
      }, 2400);

      const t3 = setTimeout(() => {
        setVisibleEvents([selectedPreset.events[0], selectedPreset.events[1], selectedPreset.events[2]]);
        setProgressPercent(85);
        setProgressText("Awaiting response from DeepSeek V3...");
      }, 3600);

      const t4 = setTimeout(() => {
        setVisibleEvents([selectedPreset.events[0], selectedPreset.events[1], selectedPreset.events[2], selectedPreset.events[3]]);
        setProgressPercent(95);
        setSimulationState("synthesizing");
      }, 4800);

      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
        clearTimeout(t4);
      };
    }

    if (simulationState === "synthesizing") {
      setProgressText("Synthesizing model responses and detecting consensus...");
      const t1 = setTimeout(() => {
        setVisibleEvents(selectedPreset.events);
        setProgressPercent(100);
        setSimulationState("finished");
        trackEvent("demo_simulation_finished", { presetId: selectedPreset.id });
      }, 1500);

      return () => clearTimeout(t1);
    }
  }, [selectedPreset, simulationState]);

  const handleStartDemo = (preset: PromptPreset) => {
    trackEvent("demo_simulation_started", { presetId: preset.id });
    setSelectedPreset(preset);
    setVisibleEvents([]);
    setSimulationState("dispatching");
    setProgressPercent(0);
    setProgressText("");
  };

  const handleReset = () => {
    setSelectedPreset(null);
    setSimulationState("idle");
    setVisibleEvents([]);
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes("@")) return;

    setIsSubmittingEmail(true);
    trackEvent("demo_signup_submitted", { email });
    
    // Simulate API request
    setTimeout(() => {
      setIsSubmittingEmail(false);
      setEmailSubmitted(true);
    }, 800);
  };

  // Build the mock debate container object
  const currentDebate = selectedPreset
    ? {
        id: selectedPreset.id,
        prompt: selectedPreset.prompt,
        status: simulationState === "finished" ? "completed" : "running",
        is_public: true,
        created_at: new Date().toISOString(),
        final_meta: {
          models: selectedPreset.models,
        },
      }
    : null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-10 text-center">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200/50 dark:border-amber-900/30 mb-3">
          <Sparkles className="h-3.5 w-3.5 text-amber-500 animate-pulse" />
          Interactive 60-Second Demo
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-4xl lg:text-5xl">
          Multi-Model AI in Action
        </h1>
        <p className="mt-4 text-base sm:text-lg text-slate-600 dark:text-slate-300 max-w-2xl mx-auto leading-relaxed">
          See how Consultaion orchestrates multiple LLMs to debate a complex question, identify points of consensus, and synthesize a definitive decision report.
        </p>
      </div>

      {simulationState === "idle" && (
        <div className="grid gap-6 md:grid-cols-3">
          {PRESETS.map((preset) => (
            <div
              key={preset.id}
              className="group flex flex-col justify-between rounded-2xl border border-slate-200 bg-white/80 p-6 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:border-amber-300 hover:shadow-md dark:border-slate-800 dark:bg-slate-900/50"
            >
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">Preset Scenario</span>
                <h3 className="mt-1.5 text-lg font-bold text-slate-900 dark:text-white group-hover:text-amber-700 dark:group-hover:text-amber-400">
                  {preset.title}
                </h3>
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-400 line-clamp-3 leading-relaxed italic">
                  &ldquo;{preset.prompt}&rdquo;
                </p>
              </div>
              
              <Button
                variant="default"
                onClick={() => handleStartDemo(preset)}
                className="mt-6 w-full bg-amber-600 hover:bg-amber-700 text-white font-semibold flex items-center justify-center gap-2"
              >
                <Play className="h-4 w-4 fill-current" />
                Run Simulation
              </Button>
            </div>
          ))}
        </div>
      )}

      {simulationState !== "idle" && (
        <div className="space-y-6">
          {/* Simulation status bar */}
          <div className="card-elevated p-5 border border-amber-200/50 dark:border-amber-900/30">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
              <div className="flex items-center gap-2.5">
                <Terminal className="h-4.5 w-4.5 text-amber-600 dark:text-amber-400" />
                <span className="text-sm font-mono font-semibold text-slate-700 dark:text-slate-300">
                  {progressText}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                  {progressPercent}%
                </span>
                {simulationState === "finished" && (
                  <button
                    onClick={handleReset}
                    className="text-xs font-semibold text-amber-700 hover:text-amber-800 dark:text-amber-400 dark:hover:text-amber-300"
                  >
                    Select Another
                  </button>
                )}
              </div>
            </div>
            
            {/* Progress bar container */}
            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-amber-500 to-amber-600 transition-all duration-300 rounded-full"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Prompt card */}
          <div className="bg-slate-50 dark:bg-slate-950/30 border border-slate-200/60 dark:border-slate-800/80 rounded-2xl p-5">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">Debate Question</span>
            <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
              {selectedPreset?.prompt}
            </p>
          </div>

          {/* Active Run View */}
          {currentDebate && (
            <ArenaRunView
              debate={currentDebate as any}
              events={visibleEvents}
              profile={null}
            />
          )}

          {/* Post-Value Signup CTA Card */}
          {simulationState === "finished" && (
            <div className="relative mt-12 overflow-hidden rounded-3xl border border-amber-300 bg-gradient-to-br from-amber-50/50 via-white to-white p-8 text-center shadow-xl dark:border-amber-900/50 dark:from-slate-900 dark:via-slate-950 dark:to-slate-900 dark:shadow-none">
              <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-amber-400/10 blur-3xl" />
              <div className="absolute -left-10 -bottom-10 h-40 w-40 rounded-full bg-amber-500/10 blur-3xl" />

              <div className="relative z-10 max-w-xl mx-auto space-y-6">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-900/50">
                  <ShieldCheck className="h-6 w-6 text-amber-600 dark:text-amber-400" />
                </div>
                
                <h3 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white md:text-3xl">
                  Try Consultaion with Your Own Prompts
                </h3>
                
                <p className="text-sm sm:text-base text-slate-600 dark:text-slate-300 leading-relaxed">
                  Join strategic decisions teams using Multi-Agent debate. Get started for free today, or bring your own API keys for enterprise-grade sovereignty.
                </p>

                {!emailSubmitted ? (
                  <form onSubmit={handleEmailSubmit} className="flex flex-col sm:flex-row gap-3">
                    <div className="relative flex-1">
                      <Mail className="absolute left-3.5 top-1/2 h-4.5 w-4.5 -translate-y-1/2 text-slate-400" />
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="Enter your work email"
                        className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-4 text-sm text-slate-900 shadow-inner outline-none transition focus:border-amber-500 focus:ring-1 focus:ring-amber-500 dark:border-slate-800 dark:bg-slate-950 dark:text-white"
                      />
                    </div>
                    <Button
                      type="submit"
                      disabled={isSubmittingEmail}
                      className="bg-amber-600 hover:bg-amber-700 text-white font-semibold py-3 px-6 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-amber-600/15"
                    >
                      {isSubmittingEmail ? "Submitting..." : "Get Free Access"}
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </form>
                ) : (
                  <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200/50 dark:border-emerald-900/30 p-4 text-emerald-800 dark:text-emerald-300 flex items-center justify-center gap-2 font-semibold text-sm">
                    <CheckCircle className="h-5 w-5 text-emerald-500" />
                    Thank you! Your workspace registration has been initialized. Check your inbox.
                  </div>
                )}

                <div className="flex items-center justify-center gap-6 pt-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                  <Link href="/login?next=/live" className="hover:text-amber-700 dark:hover:text-amber-400 transition">
                    Sign In Directly
                  </Link>
                  <span>•</span>
                  <Link href="/pricing" className="hover:text-amber-700 dark:hover:text-amber-400 transition">
                    View Pricing Plans
                  </Link>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
