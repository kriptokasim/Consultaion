"use client";

import { useEffect, useState } from 'react';
import { apiRequest } from '@/lib/apiClient';

export function MilestoneCelebration({ debateCount }: { debateCount: number }) {
    const [gifUrl, setGifUrl] = useState<string | null>(null);

    useEffect(() => {
        if (debateCount < 50) return;

        let cancelled = false;
        (async () => {
            try {
                const res = await apiRequest<{ url: string | null }>({ path: '/gifs/celebration' });
                if (!cancelled) setGifUrl(res.url);
            } catch {
                // ignore
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [debateCount]);

    if (debateCount < 50 || !gifUrl) return null;

    return (
        <div className="mt-4 flex items-center gap-3 rounded-2xl border border-brand-border/60 bg-brand-bg/80 p-3 text-sm text-brand-primary">
            <div className="h-10 w-10 overflow-hidden rounded-xl bg-brand-primary/5">
                {gifUrl.endsWith('.mp4') ? (
                    <video src={gifUrl} autoPlay loop muted playsInline className="h-full w-full object-cover" />
                ) : (
                    <img src={gifUrl} alt="Milestone" className="h-full w-full object-cover" />
                )}
            </div>
            <div>
                <p className="font-medium">Milestone reached!</p>
                <p className="text-xs text-brand-primary/70">
                    You have run over 50 debates. Thanks for putting the AI parliament to work.
                </p>
            </div>
        </div>
    );
}
