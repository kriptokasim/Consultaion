"use client";

import { Button } from "@/components/ui/button";
import { trackEvent } from "@/lib/analytics";
import { useToast } from "@/components/ui/toast";
import { Users, ShieldCheck, Mail, Sparkles, Building2, UserPlus } from "lucide-react";

export default function TeamPage() {
  const { pushToast } = useToast();
  const mockMembers = [
    { name: "Kasim", email: "kasim@kripto.com", role: "Owner", status: "Active" }
  ];

  return (
    <main className="container mx-auto max-w-4xl p-6">
      <div className="mb-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-amber-900 dark:text-amber-50">
            Team & Roles
          </h1>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400 max-w-xl">
            Manage members, delegate administrative roles, and coordinate shared credits for model evaluations.
          </p>
        </div>
        
        <Button
          variant="outline"
          onClick={() => {
            trackEvent("team_invite_clicked_blocked");
            pushToast({ title: "Upgrade Required", description: "Team invitations require a team license. Please upgrade to a Team or Enterprise plan.", variant: "info" });
          }}
          className="flex items-center gap-1.5 text-xs font-semibold shrink-0"
        >
          <UserPlus className="h-4 w-4" />
          Invite Member
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_0.9fr]">
        {/* Members list */}
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden shadow-sm">
            <div className="p-4 bg-slate-50 dark:bg-slate-950/30 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Active Membership</span>
            </div>

            <div className="divide-y divide-slate-200 dark:divide-slate-850">
              {mockMembers.map((m, idx) => (
                <div key={idx} className="p-4 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-full bg-amber-100 dark:bg-amber-950/40 flex items-center justify-center text-amber-700 font-bold text-sm">
                      {m.name.charAt(0)}
                    </div>
                    <div>
                      <span className="block text-sm font-bold text-slate-900 dark:text-white">{m.name}</span>
                      <span className="block text-xs text-slate-500 dark:text-slate-400 font-mono mt-0.5">{m.email}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 dark:bg-amber-950/30 px-2.5 py-0.5 text-xs font-semibold text-amber-800 dark:text-amber-300 border border-amber-200/30 dark:border-amber-900/30">
                      <ShieldCheck className="h-3 w-3" />
                      {m.role}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Upgrade card */}
        <div className="space-y-6">
          <div className="relative overflow-hidden rounded-2xl border border-amber-300 bg-gradient-to-br from-amber-50/25 via-white to-white p-6 shadow-md dark:border-amber-900/50 dark:from-slate-900 dark:via-slate-950 dark:to-slate-900 dark:shadow-none">
            <div className="absolute right-0 top-0 translate-x-1/3 -translate-y-1/3 w-32 h-32 rounded-full bg-amber-400/10 blur-2xl" />
            
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-950/50 border border-amber-200 dark:border-amber-900/50 mb-4">
              <Building2 className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>

            <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
              Collaboration Upgrades
              <Sparkles className="h-4 w-4 text-amber-500 animate-pulse" />
            </h3>
            
            <p className="mt-2 text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
              Unlock multi-user capabilities, collaborative review spaces, and enterprise access governance:
            </p>

            <ul className="mt-4 space-y-2.5 text-[11px] font-medium text-slate-700 dark:text-slate-200">
              <li className="flex items-center gap-2">
                <Users className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Shared billing & seat pooling
              </li>
              <li className="flex items-center gap-2">
                <Users className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Collaborative model debate reviews
              </li>
              <li className="flex items-center gap-2">
                <Users className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Role-Based Access Control (RBAC)
              </li>
              <li className="flex items-center gap-2">
                <Users className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                Audit Trail attribution tagging
              </li>
            </ul>

            <button
              onClick={() => {
                trackEvent("team_enterprise_cta_clicked");
                window.location.href = "mailto:enterprise@consultaion.com?subject=Team%20Collaboration%20Inquiry";
              }}
              className="mt-6 w-full rounded-xl bg-slate-900 py-2.5 text-xs font-semibold text-white shadow transition hover:bg-slate-800 dark:bg-slate-850 dark:hover:bg-slate-700"
            >
              Contact Sales for Team Plan
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
