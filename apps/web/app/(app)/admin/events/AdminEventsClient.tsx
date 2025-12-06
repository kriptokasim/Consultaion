"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getAdminEvents, sendTestAlert } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Info, AlertTriangle, Bell } from "lucide-react";
import { useToast } from "@/components/ui/toast";

export default function AdminEventsClient() {
    const [page, setPage] = useState(0);
    const [level, setLevel] = useState<string | undefined>(undefined);
    const limit = 50;
    const { pushToast } = useToast();

    const { data, isLoading, refetch } = useQuery({
        queryKey: ["admin-events", page, level],
        queryFn: () => getAdminEvents({ limit, offset: page * limit, level }),
    });

    const testAlertMutation = useMutation({
        mutationFn: sendTestAlert,
        onSuccess: () => {
            pushToast({ title: "Test alert sent", variant: "success" });
        },
        onError: () => {
            pushToast({ title: "Failed to send test alert", variant: "error" });
        },
    });

    const events = data?.items || [];
    const total = data?.total || 0;
    const totalPages = Math.ceil(total / limit);

    const getLevelBadge = (lvl: string) => {
        switch (lvl) {
            case "error":
                return <Badge className="bg-red-100 text-red-800 border-red-200">Error</Badge>;
            case "warning":
                return <Badge className="bg-amber-100 text-amber-800 border-amber-200">Warning</Badge>;
            case "info":
                return <Badge className="bg-blue-100 text-blue-800 border-blue-200">Info</Badge>;
            default:
                return <Badge variant="outline">{lvl}</Badge>;
        }
    };

    const getLevelIcon = (lvl: string) => {
        switch (lvl) {
            case "error":
                return <AlertCircle className="h-4 w-4 text-red-600" />;
            case "warning":
                return <AlertTriangle className="h-4 w-4 text-amber-600" />;
            case "info":
                return <Info className="h-4 w-4 text-blue-600" />;
            default:
                return <Info className="h-4 w-4 text-stone-400" />;
        }
    };

    return (
        <div className="space-y-6 p-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-stone-900 dark:text-stone-100">System Events</h1>
                    <p className="text-stone-500 dark:text-stone-400">Monitor system errors and warnings.</p>
                </div>
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        onClick={() => testAlertMutation.mutate()}
                        disabled={testAlertMutation.isPending}
                    >
                        <Bell className="mr-2 h-4 w-4" />
                        {testAlertMutation.isPending ? "Sending..." : "Send Test Alert"}
                    </Button>
                </div>
            </div>

            <div className="flex gap-2">
                <Button
                    variant={level === undefined ? "secondary" : "ghost"}
                    onClick={() => { setLevel(undefined); setPage(0); }}
                    size="sm"
                >
                    All
                </Button>
                <Button
                    variant={level === "error" ? "secondary" : "ghost"}
                    onClick={() => { setLevel("error"); setPage(0); }}
                    size="sm"
                    className="text-red-600"
                >
                    Errors
                </Button>
                <Button
                    variant={level === "warning" ? "secondary" : "ghost"}
                    onClick={() => { setLevel("warning"); setPage(0); }}
                    size="sm"
                    className="text-amber-600"
                >
                    Warnings
                </Button>
            </div>

            <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                        <thead className="bg-stone-50 text-stone-500 dark:bg-stone-900 dark:text-stone-400">
                            <tr>
                                <th className="px-4 py-3 font-medium">Level</th>
                                <th className="px-4 py-3 font-medium">Message</th>
                                <th className="px-4 py-3 font-medium">Trace ID</th>
                                <th className="px-4 py-3 font-medium">Time</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                            {isLoading ? (
                                <tr>
                                    <td colSpan={4} className="px-4 py-8 text-center text-stone-500">
                                        Loading events...
                                    </td>
                                </tr>
                            ) : events.length === 0 ? (
                                <tr>
                                    <td colSpan={4} className="px-4 py-8 text-center text-stone-500">
                                        No events found.
                                    </td>
                                </tr>
                            ) : (
                                events.map((event: any) => (
                                    <tr key={event.id} className="hover:bg-stone-50 dark:hover:bg-stone-900/50">
                                        <td className="px-4 py-3">
                                            <div className="flex items-center gap-2">
                                                {getLevelIcon(event.level)}
                                                <span className="capitalize">{event.level}</span>
                                            </div>
                                        </td>
                                        <td className="px-4 py-3 font-mono text-xs text-stone-600 dark:text-stone-300">
                                            {event.message}
                                            {event.debate_id && (
                                                <div className="mt-1 text-xs text-stone-400">
                                                    Debate: {event.debate_id}
                                                </div>
                                            )}
                                        </td>
                                        <td className="px-4 py-3 font-mono text-xs text-stone-500">
                                            {event.trace_id || "-"}
                                        </td>
                                        <td className="px-4 py-3 text-stone-500 whitespace-nowrap">
                                            {new Date(event.created_at).toLocaleString()}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
                <div className="flex items-center justify-between border-t border-stone-100 bg-stone-50 px-4 py-3 dark:border-stone-800 dark:bg-stone-900">
                    <div className="text-xs text-stone-500">
                        Showing {events.length} of {total} events
                    </div>
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage(p => Math.max(0, p - 1))}
                            disabled={page === 0}
                        >
                            Previous
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setPage(p => p + 1)}
                            disabled={(page + 1) * limit >= total}
                        >
                            Next
                        </Button>
                    </div>
                </div>
            </Card>
        </div>
    );
}
