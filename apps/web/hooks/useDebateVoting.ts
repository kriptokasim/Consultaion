import { useMemo } from "react";
import type { DebateEvent, JudgeScoreEvent, PairwiseEvent, JudgeVoteFlow } from "@/components/parliament/types";
import type { ArenaVoteStats } from "@/components/debate/DebateArena";
import { DEFAULT_VOTE_THRESHOLD } from "@/config/debateDefaults";

interface UseDebateVotingProps {
    events: DebateEvent[];
    threshold?: number;
}

export function useDebateVoting({ events, threshold = DEFAULT_VOTE_THRESHOLD }: UseDebateVotingProps) {
    const eventScores = useMemo(
        () => events.filter((event): event is JudgeScoreEvent => event.type === 'score'),
        [events]
    );

    const pairwiseEvents = useMemo(
        () => events.filter((event): event is PairwiseEvent => event.type === 'pairwise'),
        [events]
    );

    const judgeVotes: JudgeVoteFlow[] = useMemo(() => {
        if (pairwiseEvents.length) {
            return pairwiseEvents.map((entry) => ({
                persona: entry.winner,
                judge: entry.judge ?? 'division',
                score: 1,
                at: entry.at,
                vote: 'aye' as const,
            }));
        }
        return eventScores.map((entry) => ({
            persona: entry.persona,
            judge: entry.judge,
            score: entry.score,
            at: entry.at,
            vote: entry.score >= threshold ? ('aye' as const) : ('nay' as const),
        }));
    }, [eventScores, pairwiseEvents, threshold]);

    const voteBasis: 'pairwise' | 'threshold' = pairwiseEvents.length ? 'pairwise' : 'threshold';

    const voteStats: ArenaVoteStats = useMemo(
        () => ({
            aye: judgeVotes.filter((entry) => entry.vote === 'aye').length,
            nay: judgeVotes.filter((entry) => entry.vote === 'nay').length,
            threshold: threshold,
        }),
        [judgeVotes, threshold]
    );

    return {
        eventScores,
        pairwiseEvents,
        judgeVotes,
        voteBasis,
        voteStats
    };
}
