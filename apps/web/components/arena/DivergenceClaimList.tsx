import React from "react";
import { CheckCircle2, AlertTriangle, ThumbsUp, Loader2, Check } from "lucide-react";
import { getColors } from "./ModelCard";

interface Claim {
  claim: string;
  models?: string[]; // for consensus
  model?: string;    // for contested
}

interface DivergenceClaimListProps {
  title: string;
  type: "consensus" | "contested";
  claims: Claim[];
  emptyMessage: string;
  votedClaim: string | null;
  votingFor: string | null;
  onVote: (claimText: string, modelName: string, isConsensus: boolean) => void;
}

export function DivergenceClaimList({
  title,
  type,
  claims,
  emptyMessage,
  votedClaim,
  votingFor,
  onVote,
}: DivergenceClaimListProps) {
  const isConsensus = type === "consensus";

  return (
    <div className="space-y-4">
      <div className={`flex items-center gap-2 ${isConsensus ? "text-emerald-500" : "text-rose-500"}`}>
        {isConsensus ? <CheckCircle2 className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
        <h3 className="text-sm font-bold uppercase tracking-wider">{title}</h3>
      </div>
      
      {claims.length === 0 ? (
        <p className="text-xs text-muted-foreground italic bg-muted/20 rounded-xl p-4 border border-dashed border-border">
          {emptyMessage}
        </p>
      ) : (
        <div className="space-y-3">
          {claims.map((item, idx) => {
            const isSelected = votedClaim === item.claim;
            const isAnySelected = votedClaim !== null;
            const isVotingThis = votingFor === item.claim;
            const borderColor = isConsensus ? "border-emerald-500" : "border-rose-500";
            const bgColor = isConsensus ? "bg-emerald-500/5 shadow-emerald-500/10" : "bg-rose-500/5 shadow-rose-500/10";
            const btnBg = isConsensus ? "bg-emerald-500" : "bg-rose-500";
            const btnHoverBg = isConsensus ? "hover:bg-emerald-500" : "hover:bg-rose-500";
            const btnTextHover = isConsensus ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400";
            const btnBorderColor = isConsensus ? "border-emerald-500" : "border-rose-500";
            const btnHoverBorder = isConsensus ? "border-emerald-500/30" : "border-rose-500/30";
            const btnBgLight = isConsensus ? "bg-emerald-500/10" : "bg-rose-500/10";

            return (
              <div 
                key={idx} 
                className={`group relative flex flex-col justify-between gap-3 p-4 rounded-xl border transition-all ${
                  isSelected
                    ? `${borderColor} ${bgColor} shadow-sm`
                    : "border-border bg-card/50 hover:bg-card hover:shadow-sm"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-foreground/90 leading-relaxed font-medium">
                    {item.claim}
                  </p>
                  
                  {/* Vote Button */}
                  <button
                    onClick={() => onVote(item.claim, item.models?.[0] || item.model || "Model", isConsensus)}
                    disabled={isAnySelected || isVotingThis}
                    className={`shrink-0 flex items-center justify-center h-8 px-3 rounded-lg text-xs font-semibold border transition-all ${
                      isSelected
                        ? `${btnBg} text-white ${btnBorderColor}`
                        : isAnySelected
                        ? "opacity-40 cursor-not-allowed bg-muted text-muted-foreground border-border"
                        : `${btnBgLight} ${btnHoverBg} hover:text-white ${btnHoverBorder} ${btnTextHover}`
                    }`}
                    title={isSelected ? "You voted for this claim" : `Upvote this ${isConsensus ? "consensus point" : "unique claim"}`}
                  >
                    {isVotingThis ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : isSelected ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <span className="flex items-center gap-1">
                        <ThumbsUp className="h-3 w-3" /> Agree
                      </span>
                    )}
                  </button>
                </div>

                {/* Model identity pills */}
                <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-border/40">
                  <span className="text-[10px] text-muted-foreground uppercase font-bold tracking-wide mr-1">
                    {isConsensus ? "Supported by:" : "Proposed by:"}
                  </span>
                  {(item.models || (item.model ? [item.model] : [])).map((model) => {
                    const colors = getColors(model);
                    return (
                      <span 
                        key={model}
                        className={`inline-flex items-center gap-1 text-[10px] font-semibold rounded-full px-2 py-0.5 border ${colors.border} ${colors.bg} ${colors.text}`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${colors.accent}`} />
                        {model}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
