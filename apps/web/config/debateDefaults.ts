import type { Member } from "@/components/parliament/types";
import { API_ORIGIN } from "@/lib/config/runtime";

export const DEFAULT_RUN_MEMBERS: Member[] = [
    { id: "Analyst", name: "Analyst", role: "agent" },
    { id: "Critic", name: "Critic", role: "critic" },
    { id: "Builder", name: "Builder", role: "agent" },
];

export const DEFAULT_VOTE_THRESHOLD = Number(process.env.NEXT_PUBLIC_VOTE_THRESHOLD ?? "7");
export const DEFAULT_API_URL = API_ORIGIN;
