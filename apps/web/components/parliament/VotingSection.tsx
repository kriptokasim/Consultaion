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
  const maxScore = Math.max(...scores.map((s) => s.score), 1);
  const sortedScores = [...scores].sort((a, b) => b.score - a.score);
  const winner = sortedScores[0];
  const hasTie = sortedScores.length > 1 && sortedScores[1].score === winner?.score;

  return (
    <section className="space-y-6 rounded-3xl border border-stone-200 bg-white/90 p-6 shadow-sm" aria-labelledby="voting-title">
      <div className="container mx-auto px-4">
        <div className="mb-6 text-center">
          <h2 id="voting-title" className="text-2xl font-semibold text-stone-900">
            Voting Results
          </h2>
          <p className="text-sm text-stone-500">Judge aggregates and ranking summaries</p>
        </div>

        <div className="max-w-4xl mx-auto space-y-6">
          {/* Winner Banner */}
          {winner && (
            <Card className="border border-amber-200 bg-gradient-to-br from-amber-50 to-stone-50">
              <CardHeader>
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-500 text-white">
                      <Trophy className="h-6 w-6" aria-hidden="true" />
                    </div>
                    <div>
                      <CardTitle className="text-2xl text-stone-900">
                        {hasTie ? "Tied Leaders" : "Winner Selected"}
                      </CardTitle>
                      {vote && (
                        <p className="mt-1 text-sm text-stone-600">
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
                      className="rounded-full border-amber-200 bg-white text-amber-800 hover:bg-amber-50"
                      aria-label="Export results as markdown"
                    >
                      <Download className="mr-2 h-4 w-4" aria-hidden="true" />
                      Export
                    </Button>
                  )}
                </div>
              </CardHeader>
            </Card>
          )}

          {/* Scores visualization */}
          <Card className="border border-stone-100">
            <CardHeader>
              <CardTitle className="text-xl text-stone-900">Aggregate Scores</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {sortedScores.map((item, index) => {
                const percentage = (item.score / maxScore) * 100;
                const isWinner = index === 0;
                const isTied = item.score === winner?.score;

                return (
                  <div key={item.persona} className="space-y-2 rounded-xl border border-stone-100 bg-stone-50/60 p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-stone-900">{item.persona}</span>
                        {isWinner && (
                          <Trophy 
                            className="h-4 w-4 text-amber-500" 
                            aria-label="Winner"
                          />
                        )}
                        {isTied && index > 0 && (
                          <Badge className="border-amber-200 bg-amber-50 text-amber-700">
                            Tied
                          </Badge>
                        )}
                      </div>
                      <span className="font-semibold text-amber-700">{item.score.toFixed(2)}</span>
                    </div>

                    {/* Progress bar */}
                    <div className="relative h-2 w-full overflow-hidden rounded-full bg-white">
                      <div
                        className={`h-full transition-all duration-500 ${
                          isWinner 
                            ? "bg-gradient-to-r from-amber-500 to-amber-300" 
                            : "bg-gradient-to-r from-stone-300 to-stone-200"
                        }`}
                        style={{ width: `${percentage}%` }}
                        role="progressbar"
                        aria-valuenow={item.score}
                        aria-valuemin={0}
                        aria-valuemax={maxScore}
                        aria-label={`${item.persona} score: ${item.score}`}
                      />
                    </div>

                    {item.rationale ? (
                      <p className="mt-1 text-xs text-stone-600 italic">{item.rationale}</p>
                    ) : null}
                  </div>
                );
              })}
            </CardContent>
          </Card>

          {/* Ranking display */}
          {vote && vote.ranking.length > 0 && (
            <Card className="border border-stone-100">
              <CardHeader>
                <CardTitle className="text-xl text-stone-900">Final Ranking</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2" aria-label="Final ranking of participants">
                  {vote.ranking.map((persona, index) => (
                    <li 
                      key={index}
                      className="flex items-center gap-3 rounded-xl border border-stone-100 bg-stone-50/70 p-3 text-sm text-stone-700"
                    >
                      <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
                        index === 0 
                          ? "bg-amber-500 text-white" 
                          : "bg-white text-stone-600 border border-stone-200"
                      }`}>
                        {index + 1}
                      </div>
                      <span className="font-medium text-stone-900">{persona}</span>
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
