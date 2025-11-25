'use client';

import { useDebate } from "@/lib/api/hooks/useDebate";
import { ReplayViewer } from "@/components/parliament/ReplayViewer";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

export default function ReplayPageClient({ id }: { id: string }) {
    const { data: debate, isLoading, error } = useDebate(id);

    if (isLoading) {
        return <div className="flex h-screen items-center justify-center">Loading...</div>;
    }

    if (error || !debate) {
        if (error) console.error(error);
        notFound();
    }

    return (
        <main className="flex flex-col h-full p-6 gap-6">
            <div className="flex items-center gap-4">
                <Button variant="outline" size="sm" asChild className="inline-flex items-center gap-2">
                    <Link href={`/runs/${id}`}>
                        <ArrowLeft className="h-4 w-4" />
                        <span>Back to Run</span>
                    </Link>
                </Button>
                <div>
                    <h1 className="text-2xl font-bold tracking-tight">Replay: {debate.prompt}</h1>
                    <p className="text-sm text-muted-foreground">
                        {new Date(debate.created_at).toLocaleString()}
                    </p>
                </div>
            </div>

            <ReplayViewer debateId={id} />
        </main>
    );
}
