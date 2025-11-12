import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Trophy, Download } from "lucide-react";
import type { ScoreItem, VotePayload } from "./types";

export interface VotingSectionProps {
  scores: ScoreItem[];
  vote?: VotePayload;
  onExportMarkdown?: () => void;
}

const getMethodLabel = (method: string) => {
  const labels = {
    borda: "Borda Count",
    condorcet: "Condorcet Method",
    plurality: "Plurality Vote",
    approval: "Approval Voting",
  };
  return labels[method as keyof typeof labels] || method;
};

export default function VotingSection({ scores, vote, onExportMarkdown }: VotingSectionProps) {
  const maxScore = Math.max(...scores.map(s => s.score), 1);
  const sortedScores = [...scores].sort((a, b) => b.score - a.score);
  const winner = sortedScores[0];
  const hasTie = sortedScores.length > 1 && sortedScores[1].score === winner?.score;

  return (
    <section 
      className="py-12 [--parl-blue:#0B1D3A] [--parl-gold:#D4AF37] [--muted:#101827]"
      aria-labelledby="voting-title"
    >
      <div className="container mx-auto px-4">
        <div className="text-center mb-8">
          <h2 id="voting-title" className="text-3xl md:text-4xl font-bold text-[--parl-gold] mb-2">
            Voting Results
          </h2>
          <p className="text-base text-white/70">
            Democratic decision through judicial scoring and ranking
          </p>
        </div>

        <div className="max-w-4xl mx-auto space-y-6">
          {/* Winner Banner */}
          {winner && (
            <Card className="bg-gradient-to-br from-[--parl-gold]/10 to-[--parl-blue]/20 border-2 border-[--parl-gold]/30">
              <CardHeader>
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-full bg-[--parl-gold] flex items-center justify-center">
                      <Trophy className="w-6 h-6 text-black" aria-hidden="true" />
                    </div>
                    <div>
                      <CardTitle className="text-2xl text-white">
                        {hasTie ? "Tied Leaders" : "Winner Selected"}
                      </CardTitle>
                      {vote && (
                        <p className="text-sm text-white/70 mt-1">
                          Method: {getMethodLabel(vote.method)}
                        </p>
                      )}
                    </div>
                  </div>
                  {onExportMarkdown && (
                    <Button
                      onClick={onExportMarkdown}
                      variant="outline"
                      size="sm"
                      className="bg-white/5 border-white/20 text-white hover:bg-white/10"
                      aria-label="Export results as markdown"
                    >
                      <Download className="w-4 h-4 mr-2" aria-hidden="true" />
                      Export
                    </Button>
                  )}
                </div>
              </CardHeader>
            </Card>
          )}

          {/* Scores visualization */}
          <Card className="bg-[--muted] border-white/10">
            <CardHeader>
              <CardTitle className="text-xl text-white">Aggregate Scores</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {sortedScores.map((item, index) => {
                const percentage = (item.score / maxScore) * 100;
                const isWinner = index === 0;
                const isTied = item.score === winner?.score;

                return (
                  <div key={item.persona} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-white text-sm">{item.persona}</span>
                        {isWinner && (
                          <Trophy 
                            className="w-4 h-4 text-[--parl-gold] fill-[--parl-gold]" 
                            aria-label="Winner"
                          />
                        )}
                        {isTied && index > 0 && (
                          <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-xs">
                            Tied
                          </Badge>
                        )}
                      </div>
                      <span className="font-bold text-[--parl-gold]">{item.score.toFixed(2)}</span>
                    </div>

                    {/* Progress bar */}
                    <div className="relative h-3 w-full overflow-hidden rounded-full bg-white/10">
                      <div
                        className={`h-full transition-all duration-500 ${
                          isWinner 
                            ? "bg-gradient-to-r from-[--parl-gold] to-amber-500" 
                            : "bg-white/30"
                        }`}
                        style={{ width: `${percentage}%` }}
                        role="progressbar"
                        aria-valuenow={item.score}
                        aria-valuemin={0}
                        aria-valuemax={maxScore}
                        aria-label={`${item.persona} score: ${item.score}`}
                      />
                    </div>

                    {item.rationale && (
                      <p className="text-xs text-white/60 mt-1 italic">
                        {item.rationale}
                      </p>
                    )}
                  </div>
                );
              })}
            </CardContent>
          </Card>

          {/* Ranking display */}
          {vote && vote.ranking.length > 0 && (
            <Card className="bg-[--muted] border-white/10">
              <CardHeader>
                <CardTitle className="text-xl text-white">Final Ranking</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2" aria-label="Final ranking of participants">
                  {vote.ranking.map((persona, index) => (
                    <li 
                      key={index}
                      className="flex items-center gap-3 p-3 rounded bg-white/5 hover:bg-white/10 transition-colors"
                    >
                      <div className={`flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm ${
                        index === 0 
                          ? "bg-[--parl-gold] text-black" 
                          : "bg-white/10 text-white/70"
                      }`}>
                        {index + 1}
                      </div>
                      <span className="text-white font-medium">{persona}</span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </section>
  );
}
