import type { DebateEvent, Member } from "@/components/parliament/types";
import { fetchWithAuth } from "@/lib/auth";
import RunDetailClient from "./RunDetailClient";

export const dynamic = "force-dynamic";

type RunDetailProps = {
  params?: Promise<{ id: string }>;
};

export default async function RunDetailPage({ params }: RunDetailProps) {
  const { id } = await (params ?? Promise.resolve({ id: "" }));

  let debate: any;
  let report: any;
  let eventPayload: any;
  let memberPayload: any;

  try {
    const [debateRes, reportRes, eventsRes, membersRes] = await Promise.all([
      fetchWithAuth(`/debates/${id}`),
      fetchWithAuth(`/debates/${id}/report`),
      fetchWithAuth(`/debates/${id}/events`),
      fetchWithAuth(`/debates/${id}/members`),
    ]);

    if ([debateRes, reportRes, eventsRes, membersRes].some((res) => !res.ok)) {
      throw new Error("unauthorized");
    }

    [debate, report, eventPayload, memberPayload] = await Promise.all([
      debateRes.json(),
      reportRes.json(),
      eventsRes.json(),
      membersRes.json(),
    ]);
  } catch (error) {
    return (
      <main id="main" className="flex h-full items-center justify-center p-6">
        <div className="rounded-lg border border-border bg-card p-6 text-center">
          <p className="text-sm text-muted-foreground">
            This run is unavailable or you do not have access.
          </p>
          <a
            href="/runs"
            className="mt-3 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm hover:bg-primary/90"
          >
            Back to runs
          </a>
        </div>
      </main>
    );
  }

  const events: DebateEvent[] = Array.isArray(eventPayload?.items)
    ? eventPayload.items
    : [];

  if (debate?.final_content) {
    events.push({
      type: "final",
      actor: "Synthesizer",
      role: "synthesizer",
      text: debate.final_content,
      at: typeof debate.updated_at === "string" ? debate.updated_at : undefined,
    });
  }

  const memberList: Member[] = Array.isArray(memberPayload?.members)
    ? memberPayload.members.map((member: any) => ({
        id: member.id ?? member.name,
        name: member.name ?? member.id,
        role: member.role ?? "agent",
        party: member.party,
      }))
    : [];

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const threshold = Number(process.env.NEXT_PUBLIC_VOTE_THRESHOLD ?? "7");

  return (
    <RunDetailClient
      id={id}
      initialDebate={debate}
      initialReport={report}
      initialEvents={events}
      initialMembers={memberList}
      threshold={threshold}
      apiBase={apiBase}
    />
  );
}
