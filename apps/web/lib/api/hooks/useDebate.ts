import { useQuery } from '@tanstack/react-query';
import { getDebate, getDebatesList, getLeaderboard } from '../../apiClient';

export function useDebate(id: string) {
    return useQuery({
        queryKey: ['debate', id],
        queryFn: () => getDebate(id),
        enabled: !!id,
    });
}
