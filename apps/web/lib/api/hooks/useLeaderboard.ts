import { useQuery } from '@tanstack/react-query';
import { getLeaderboard } from '../../apiClient';

export function useLeaderboard(params?: Record<string, any>) {
    return useQuery({
        queryKey: ['leaderboard', params],
        queryFn: () => getLeaderboard(params),
    });
}
