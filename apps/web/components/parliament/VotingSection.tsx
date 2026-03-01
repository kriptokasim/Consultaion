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
    <section className="space-y-6 rounded-3xl border border-border bg-card p-6 shadow-sm" aria-labelledby="voting-title">
      <div className="container mx-auto px-4">
        <div className="mb-6 text-center">
          <h2 id="voting-title" className="text-2xl font-semibold text-foreground">
            Voting Results
          </h2>
          <p className="text-sm text-muted-foreground">Judge aggregates and ranking summaries</p>
        </div>

        <div className="max-w-4xl mx-auto space-y-6">
          {/* Winner Banner */}
          {winner && (
            <Card className="border border-accent-secondary/30 bg-gradient-to-br from-accent-secondary/10 to-secondary">
              <CardHeader>
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent-secondary text-white">
                      <Trophy className="h-6 w-6" aria-hidden="true" />
                    </div>
                    <div>
                      <CardTitle className="text-2xl">
                        {hasTie ? "Tied Leaders" : "Winner Selected"}
                      </CardTitle>
                      {vote && (
                        <p className="mt-1 text-sm text-muted-foreground">
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
                      className="rounded-full"
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
          <Card className="border border-border">
            <CardHeader>
              <CardTitle className="text-xl">Aggregate Scores</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {sortedScores.map((item, index) => {
                const percentage = (item.score / maxScore) * 100;
                const isWinner = index === 0;
                const isTied = item.score === winner?.score;

                return (
                  <div key={item.persona} className="space-y-2 rounded-xl border border-border bg-secondary/50 p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-foreground">{item.persona}</span>
                        {isWinner && (
                          <Trophy
                            className="h-4 w-4 text-accent-secondary"
                            aria-label="Winner"
                          />
                        )}
                        {isTied && index > 0 && (
                          <Badge className="border-accent-secondary/20 bg-accent-secondary/10 text-accent-secondary">
                            Tied
                          </Badge>
                        )}
                      </div>
                      <span className="font-semibold text-accent-secondary">{item.score.toFixed(2)}</span>
                    </div>

                    {/* Progress bar */}
                    <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className={`h-full transition-all duration-500 ${isWinner
                            ? "bg-gradient-to-r from-amber-500 to-amber-300"
                            : "bg-gradient-to-r from-muted-foreground/30 to-muted-foreground/15"
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
                      <p className="mt-1 text-xs text-muted-foreground italic">{item.rationale}</p>
                    ) : null}
                  </div>
                );
              })}
            </CardContent>
          </Card>

          {/* Ranking display */}
          {vote && vote.ranking.length > 0 && (
            <Card className="border border-border">
              <CardHeader>
                <CardTitle className="text-xl">Final Ranking</CardTitle>
              </CardHeader>
              <CardContent>
                <ol className="space-y-2" aria-label="Final ranking of participants">
                  {vote.ranking.map((persona, index) => (
                    <li
                      key={index}
                      className="flex items-center gap-3 rounded-xl border border-border bg-secondary/50 p-3 text-sm text-muted-foreground"
                    >
                      <div className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${index === 0
                          ? "bg-accent-secondary text-white"
                          : "bg-card text-muted-foreground border border-border"
                        }`}>
                        {index + 1}
                      </div>
                      <span className="font-medium text-foreground">{persona}</span>
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
