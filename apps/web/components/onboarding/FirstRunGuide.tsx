import { useState, useEffect } from "react";
import { Search, Zap, FileText, ArrowRight, X } from "lucide-react";

interface FirstRunGuideProps {
  onPrefill: (prompt: string) => void;
}

export function FirstRunGuide({ onPrefill }: FirstRunGuideProps) {
  // Use null as initial state to distinguish "not yet checked" from "dismissed"
  const [dismissed, setDismissed] = useState<boolean | null>(null);

  useEffect(() => {
    const isDismissed = !!localStorage.getItem("first_run_guide_dismissed");
    setDismissed(isDismissed);
  }, []);

  const handleDismiss = () => {
    localStorage.setItem("first_run_guide_dismissed", "true");
    setDismissed(true);
  };

  if (dismissed === null || dismissed) return null;  // null = SSR / not yet checked

  const examplePrompt = "Should our startup migrate from AWS to GCP given our focus on machine learning?";

  return (
    <div className="relative mb-6 rounded-2xl border border-amber-200/60 bg-gradient-to-br from-amber-50 to-white p-6 shadow-sm dark:border-amber-900/30 dark:from-amber-950/20 dark:to-slate-900">
      <button 
        onClick={handleDismiss}
        className="absolute right-4 top-4 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
      >
        <X className="h-4 w-4" />
      </button>
      
      <div className="mb-4">
        <h3 className="text-lg font-bold text-amber-900 dark:text-amber-50">Welcome to Consultaion!</h3>
        <p className="text-sm text-amber-800/80 dark:text-amber-200/70 mt-1 max-w-xl">
          Get started with your first multi-model debate in three simple steps.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="flex flex-col gap-2 p-4 rounded-xl bg-white/60 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-800">
          <div className="h-8 w-8 rounded-full bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 flex items-center justify-center font-bold">1</div>
          <h4 className="font-semibold text-sm">Ask a Question</h4>
          <p className="text-xs text-slate-600 dark:text-slate-400">Pose a strategic, technical, or creative problem you need help deciding on.</p>
        </div>
        <div className="flex flex-col gap-2 p-4 rounded-xl bg-white/60 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-800">
          <div className="h-8 w-8 rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400 flex items-center justify-center font-bold">2</div>
          <h4 className="font-semibold text-sm">Models Debate</h4>
          <p className="text-xs text-slate-600 dark:text-slate-400">Watch top AI models (GPT-4, Claude, Gemini) explore different perspectives.</p>
        </div>
        <div className="flex flex-col gap-2 p-4 rounded-xl bg-white/60 dark:bg-slate-900/50 border border-slate-100 dark:border-slate-800">
          <div className="h-8 w-8 rounded-full bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400 flex items-center justify-center font-bold">3</div>
          <h4 className="font-semibold text-sm">Get the Report</h4>
          <p className="text-xs text-slate-600 dark:text-slate-400">Receive a structured decision report with a final verdict and key findings.</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold text-amber-900 dark:text-amber-100">Try it out:</span>
        <button
          onClick={() => onPrefill(examplePrompt)}
          className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-200/80 transition-colors dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/60"
        >
          {examplePrompt}
          <ArrowRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
