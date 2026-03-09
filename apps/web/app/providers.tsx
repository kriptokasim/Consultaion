'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
    // Patchset 112: Tuned React Query defaults
    const [queryClient] = useState(() => new QueryClient({
        defaultOptions: {
            queries: {
                staleTime: 60 * 1000, // 1 minute
                gcTime: 10 * 60 * 1000, // 10 minutes
                retry: (failureCount, error: unknown) => {
                    if (failureCount >= 3) return false;
                    // Don't retry auth/permission/not-found errors
                    const status = (error as { status?: number })?.status
                        || (error as { response?: { status?: number } })?.response?.status;
                    if (status === 401 || status === 403 || status === 404) return false;
                    // Don't retry rate limit errors
                    if (status === 429) return false;
                    return true;
                },
                retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
                refetchOnWindowFocus: false,
                // Removed global refetchOnReconnect: 'always' (leave as default 'true' which safely refetches stale queries only instead of 'always' force fetching everything)
            },
            mutations: {
                // Global mutation error handling hook point
                onError: (error: unknown) => {
                    const status = (error as { status?: number })?.status;
                    if (status === 429) {
                        console.warn('[QueryClient] Rate limit exceeded');
                    }
                },
            },
        },
    }));

    return (
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
            <QueryClientProvider client={queryClient}>
                {children}
            </QueryClientProvider>
        </ThemeProvider>
    );
}
