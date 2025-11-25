import type { DebateEvent, Member } from "@/components/parliament/types";
import { fetchWithAuth } from "@/lib/auth";
import { notFound, redirect } from "next/navigation";
import RunDetailClient from "./RunDetailClient";

export const dynamic = "force-dynamic";

type RunDetailProps = {
  params: { id: string };
};

export default async function RunDetailPage({ params }: RunDetailProps) {
  const { id } = params;
  if (!id) {
    notFound();
  }

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

    const responses = [debateRes, reportRes, eventsRes, membersRes];
    const isUnauthorized = responses.some((res) => res.status === 401 || res.status === 403);
    if (isUnauthorized) {
      redirect(`/login?next=/runs/${encodeURIComponent(id)}`);
    }
    if (responses.some((res) => !res.ok)) {
      notFound();
    }

    [debate, report, eventPayload, memberPayload] = await Promise.all([
      debateRes.json(),
      reportRes.json(),
      eventsRes.json(),
      membersRes.json(),
    ]);
  } catch (error) {
    notFound();
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
