"use client";

import { useState, useEffect } from "react";
import { apiRequest } from "@/lib/apiClient";
import { sanitizeMarkdown } from "@/lib/sanitize";
import { MessageSquareCode, ShieldAlert, Sparkles, Send, RefreshCw, CheckCircle, HelpCircle } from "lucide-react";

interface Round {
  id: string;
  round_number: number;
  pushback_text: string;
  decision: "defend" | "concede" | "revise";
  response_reasoning: string;
  revised_synthesis: string;
  created_at: string;
}

interface SynthesisChallengeProps {
  debateId: string;
  initialSynthesis: string;
  onSynthesisRevised: (newText: string) => void;
}

export default function SynthesisChallenge({
  debateId,
  initialSynthesis,
  onSynthesisRevised,
}: SynthesisChallengeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [pushbackText, setPushbackText] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Initialize or fetch existing session (linked to this debate)
  // To keep it clean, we can try to start a session on toggle if not already present.
  const handleToggle = async () => {
    if (!isOpen) {
      setIsOpen(true);
      if (!sessionId) {
        await startOrFetchSession();
      }
    } else {
      setIsOpen(false);
    }
  };

  const startOrFetchSession = async () => {
    setIsStarting(true);
    setError(null);
    try {
      // Create a new challenge session or fetch. Since debate_id is unique per run,
      // let's try to start it.
      const res = await apiRequest<{ id: string }>({
        path: "/challenge",
        method: "POST",
        body: { debate_id: debateId },
      }).catch(async (err: any) => {
        // If it already exists or fails, handle it gracefully.
        // In our endpoint, POST /challenge always creates a new session.
        // We can just use the new session ID.
        throw err;
      });

      if (res && res.id) {
        setSessionId(res.id);
        // Load details
        await loadSessionDetails(res.id);
      }
    } catch (err: any) {
      console.error("Failed to start challenge session", err);
      setError(err.message || "Failed to initialize Synthesis Challenge.");
    } finally {
      setIsStarting(false);
    }
  };

  const loadSessionDetails = async (id: string) => {
    try {
      const res = await apiRequest<{ rounds: Round[] }>({
        path: `/challenge/${id}`,
        method: "GET",
      });
      if (res && res.rounds) {
        setRounds(res.rounds);
        if (res.rounds.length > 0) {
          const latestRound = res.rounds[res.rounds.length - 1];
          if (latestRound.revised_synthesis) {
            onSynthesisRevised(latestRound.revised_synthesis);
          }
        }
      }
    } catch (err: any) {
      console.error("Failed to load session details", err);
    }
  };

  const handleSubmitPushback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pushbackText.trim() || !sessionId || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);
    const originalText = pushbackText;
    setPushbackText("");

    try {
      const res = await apiRequest<Round>({
        path: `/challenge/${sessionId}/round`,
        method: "POST",
        body: { pushback_text: originalText },
      });

      if (res) {
        setRounds((prev) => [...prev, res]);
        if (res.revised_synthesis) {
          onSynthesisRevised(res.revised_synthesis);
        }
      }
    } catch (err: any) {
      console.error("Failed to submit pushback", err);
      setPushbackText(originalText);
      setError(err.message || "Failed to process pushback. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-4 border-t border-amber-200/40 pt-4">
      <button
        type="button"
        onClick={handleToggle}
        className="inline-flex items-center gap-2 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-800 shadow-sm transition hover:bg-amber-100/80 active:scale-[0.98]"
      >
        <MessageSquareCode className="h-4 w-4 text-amber-700" />
        {isOpen ? "Close Challenge Panel" : "Challenge Synthesis"}
      </button>

      {isOpen && (
        <div className="mt-4 rounded-3xl border border-stone-200 bg-white/95 p-6 shadow-lg transition-all">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-amber-600" />
              <h3 className="text-lg font-semibold text-stone-900">Synthesis Challenge Mode</h3>
            </div>
            <span className="text-xs text-stone-400">Interactive Deliberation</span>
          </div>

          <p className="mb-6 text-sm leading-relaxed text-stone-600">
            Do you spot a flaw, missing detail, or bias in the winning synthesis? 
            Submit your pushback. The AI debate coordinator will evaluate your critique 
            against the debate transcript and either defend the synthesis, concede the point, 
            or revise it to integrate your feedback.
          </p>

          {isStarting ? (
            <div className="flex flex-col items-center justify-center py-8">
              <RefreshCw className="h-8 w-8 animate-spin text-amber-600" />
              <span className="mt-2 text-sm text-stone-500">Initializing challenge coordinator...</span>
            </div>
          ) : error ? (
            <div className="mb-4 rounded-2xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
              {error}
            </div>
          ) : (
            <div className="space-y-6">
              {/* Timeline of Rounds */}
              {rounds.length > 0 && (
                <div className="space-y-4 border-l-2 border-stone-100 pl-4">
                  {rounds.map((round, idx) => (
                    <div key={round.id || idx} className="relative space-y-2">
                      <div className="absolute -left-[25px] top-1 flex h-4 w-4 items-center justify-center rounded-full bg-white ring-2 ring-stone-200">
                        <div className="h-2 w-2 rounded-full bg-amber-500" />
                      </div>
                      
                      <div className="text-xs font-semibold uppercase tracking-wider text-stone-400">
                        Round #{round.round_number}
                      </div>

                      <div className="rounded-2xl bg-stone-50 p-3 text-sm text-stone-700">
                        <span className="font-semibold text-stone-900">Your pushback:</span>{" "}
                        {round.pushback_text}
                      </div>

                      <div className="rounded-2xl border border-amber-100 bg-amber-50/40 p-4">
                        <div className="mb-2 flex items-center gap-2">
                          {round.decision === "defend" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800">
                              <ShieldAlert className="h-3. w-3" />
                              Defended
                            </span>
                          )}
                          {round.decision === "concede" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
                              <CheckCircle className="h-3 w-3" />
                              Conceded
                            </span>
                          )}
                          {round.decision === "revise" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                              <Sparkles className="h-3 w-3" />
                              Revised
                            </span>
                          )}
                          <span className="text-xs font-medium text-stone-500">Refined Decision</span>
                        </div>

                        <div 
                          className="prose prose-sm max-w-none text-sm leading-relaxed text-stone-800"
                          dangerouslySetInnerHTML={{ __html: sanitizeMarkdown(round.response_reasoning) }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Submit Input */}
              {sessionId && (
                <form onSubmit={handleSubmitPushback} className="space-y-3">
                  <label htmlFor="pushback-input" className="block text-xs font-semibold uppercase tracking-wider text-stone-500">
                    Critique / Pushback Text
                  </label>
                  <div className="relative">
                    <textarea
                      id="pushback-input"
                      rows={3}
                      required
                      placeholder="e.g. 'The synthesis recommends SQLite, but the models highlighted scaling issues under write-heavy loads. Why is this not addressed?'"
                      value={pushbackText}
                      onChange={(e) => setPushbackText(e.target.value)}
                      disabled={isSubmitting}
                      className="w-full rounded-2xl border border-stone-200 bg-stone-50/50 p-4 pr-12 text-sm leading-relaxed text-stone-800 placeholder-stone-400 focus:border-amber-300 focus:bg-white focus:outline-none focus:ring-1 focus:ring-amber-300 disabled:opacity-50"
                    />
                    <button
                      type="submit"
                      disabled={!pushbackText.trim() || isSubmitting}
                      className="absolute bottom-4 right-4 flex h-8 w-8 items-center justify-center rounded-xl bg-amber-600 text-white transition hover:bg-amber-700 disabled:bg-stone-200 disabled:text-stone-400"
                      aria-label="Send pushback"
                    >
                      {isSubmitting ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  {isSubmitting && (
                    <p className="text-xs text-amber-700 animate-pulse">
                      Coordinator is evaluating pushback against debate transcript...
                    </p>
                  )}
                </form>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
