"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AuditLogEntry } from "@/lib/api";

type UserSummary = {
  id: string;
  email: string;
  role: string;
  debate_count?: number;
  last_activity?: string | null;
  created_at?: string | null;
};

type AdminTabsProps = {
  users: UserSummary[];
  logs: AuditLogEntry[];
};

export default function AdminTabs({ users, logs }: AdminTabsProps) {
  const [tab, setTab] = useState<"users" | "logs">("users");

  return (
    <section className="rounded-3xl border border-stone-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 p-4">
        <div className="flex items-center gap-2 rounded-full bg-stone-100 p-1 text-sm font-medium text-stone-600">
          <button
            className={cn(
              "rounded-full px-4 py-1",
              tab === "users" ? "bg-amber-600 text-white" : "text-stone-600 hover:text-stone-900",
            )}
            onClick={() => setTab("users")}
          >
            Users
          </button>
          <button
            className={cn(
              "rounded-full px-4 py-1",
              tab === "logs" ? "bg-amber-600 text-white" : "text-stone-600 hover:text-stone-900",
            )}
            onClick={() => setTab("logs")}
          >
            Audit log
          </button>
        </div>
        <p className="text-xs text-stone-500">
          {tab === "users" ? "Track roles and debate counts" : "Recent administrative actions with metadata"}
        </p>
      </div>

      {tab === "users" ? <UserTable users={users} /> : <LogTable logs={logs} />}
    </section>
  );
}

function UserTable({ users }: { users: UserSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-stone-100 text-sm">
        <thead className="bg-stone-50 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">
          <tr>
            <th className="px-4 py-3">Email</th>
            <th className="px-4 py-3">Role</th>
            <th className="px-4 py-3">Debates</th>
            <th className="px-4 py-3">Last activity</th>
            <th className="px-4 py-3">Created</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 text-stone-700">
          {users.map((user) => (
            <tr key={user.id}>
              <td className="px-4 py-3 font-medium text-stone-900">{user.email}</td>
              <td className="px-4 py-3">
                <Badge className="bg-stone-900 text-stone-100">{user.role}</Badge>
              </td>
              <td className="px-4 py-3">{user.debate_count ?? 0}</td>
              <td className="px-4 py-3 text-sm text-stone-500">
                {user.last_activity ? new Date(user.last_activity).toLocaleString() : "—"}
              </td>
              <td className="px-4 py-3 text-sm text-stone-500">
                {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
              </td>
            </tr>
          ))}
          {users.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-sm text-stone-500">
                No users yet.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function LogTable({ logs }: { logs: AuditLogEntry[] }) {
  const formatMeta = (meta: Record<string, any> | null | undefined) => {
    if (!meta) return "—";
    const text = JSON.stringify(meta);
    return text.length > 60 ? `${text.slice(0, 60)}…` : text;
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-stone-100 text-sm">
        <thead className="bg-stone-50 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">
          <tr>
            <th className="px-4 py-3">Timestamp</th>
            <th className="px-4 py-3">User</th>
            <th className="px-4 py-3">Action</th>
            <th className="px-4 py-3">Target</th>
            <th className="px-4 py-3">Metadata</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100 text-stone-700">
          {logs.map((log) => (
            <tr key={log.id}>
              <td className="px-4 py-3 text-sm text-stone-500">
                {log.created_at ? new Date(log.created_at).toLocaleString() : "—"}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-stone-500">{log.user_id ?? "system"}</td>
              <td className="px-4 py-3 text-stone-900">{log.action}</td>
              <td className="px-4 py-3 text-sm text-stone-600">
                {log.target_type ? `${log.target_type} → ${log.target_id ?? "n/a"}` : "—"}
              </td>
              <td className="px-4 py-3 text-xs text-stone-500">{formatMeta(log.meta ?? null)}</td>
            </tr>
          ))}
          {logs.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-sm text-stone-500">
                No audit entries recorded yet.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
