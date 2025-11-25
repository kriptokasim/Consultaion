import { useQuery } from '@tanstack/react-query';
import { getDebatesList } from '../../apiClient';

export function useDebatesList(params?: Record<string, any>) {
    return useQuery({
        queryKey: ['debates', params],
        queryFn: () => getDebatesList(params),
    });
}
