import { fetchWithAuth } from "@/lib/auth";
import { ReplayViewer } from "@/components/parliament/ReplayViewer";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export const dynamic = "force-dynamic";

type ReplayPageProps = {
    params: { id: string };
};

export default async function ReplayPage({ params }: ReplayPageProps) {
    const { id } = params;

    let debate: any;

    try {
        const res = await fetchWithAuth(`/debates/${id}`);
        if (!res.ok) throw new Error("unauthorized");
        debate = await res.json();
    } catch (error) {
        return (
            <main className="flex h-full items-center justify-center p-6">
                <div className="rounded-lg border border-border bg-card p-6 text-center">
                    <p className="text-sm text-muted-foreground">
                        This replay is unavailable or you do not have access.
                    </p>
                    <Link
                        href="/runs"
                        className="mt-3 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90"
                    >
                        Back to runs
                    </Link>
                </div>
            </main>
        );
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
