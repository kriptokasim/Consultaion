import { useQuery } from '@tanstack/react-query';
import { getDebate } from '../../apiClient';
import { useRef } from 'react';
import { ApiClientError } from '../../apiClient';

export function useDebate(id: string) {
    const provisioningStart = useRef<number | null>(null);

    const queryInfo = useQuery({
        queryKey: ['debate', id],
        queryFn: async () => {
            try {
                return await getDebate(id);
            } catch (error) {
                if (error instanceof ApiClientError && error.status === 404) {
                    if (!provisioningStart.current) {
                        provisioningStart.current = Date.now();
                    }
                    throw error;
                }
                throw error;
            }
        },
        enabled: !!id,
        retry: (failureCount, error) => {
            if (error instanceof ApiClientError && error.status === 404) {
                const elapsed = Date.now() - (provisioningStart.current || Date.now());
                if (elapsed < 15000) return true;
                return false;
            }
            return failureCount < 3;
        },
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 2000),
    });

    const isProvisioning = queryInfo.error instanceof ApiClientError && queryInfo.error.status === 404 && !!provisioningStart.current;

    return { ...queryInfo, isProvisioning };
}
