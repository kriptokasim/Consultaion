"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { trackEvent } from "@/lib/analytics";
import { useToast } from "@/components/ui/toast";
import { API_ORIGIN } from "@/lib/config/runtime";
import { FileDown, Terminal, ShieldAlert, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";

interface AuditLog {
  id: string;
  user_id: string;
  debate_id: string | null;
  interaction_type: string;
  details: any;
  created_at: string;
}

export default function AuditLogsPage() {
  const { pushToast } = useToast();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const [isExportingCSV, setIsExportingCSV] = useState(false);
  const [isExportingJSON, setIsExportingJSON] = useState(false);

  const apiBase = API_ORIGIN;

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${apiBase}/audit-logs`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.error("Failed to fetch audit logs:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleExportCSV = async () => {
    setIsExportingCSV(true);
    trackEvent("audit_logs_csv_exported");
    try {
      const res = await fetch(`${apiBase}/audit-logs/export/csv`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to export");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `consultaion_audit_logs_${new Date().toISOString().slice(0,10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      pushToast({ title: "Export Failed", description: "Failed to export CSV. Please try again.", variant: "error" });
    } finally {
      setIsExportingCSV(false);
    }
  };

  const handleExportJSON = async () => {
    setIsExportingJSON(true);
    trackEvent("audit_logs_json_exported");
    try {
      const res = await fetch(`${apiBase}/audit-logs/export/json`, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to export");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `consultaion_audit_logs_${new Date().toISOString().slice(0,10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      pushToast({ title: "Export Failed", description: "Failed to export JSON. Please try again.", variant: "error" });
    } finally {
      setIsExportingJSON(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedLogId(expandedLogId === id ? null : id);
  };

  return (
    <main className="container mx-auto max-w-4xl p-6">
      <div className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-amber-900 dark:text-amber-50">
            System Audit Logs
          </h1>
          <p className="mt-2 text-sm text-stone-600 dark:text-stone-400 max-w-xl">
            Track user interactions, model queries, system actions, and administrative logins for compliance records.
          </p>
        </div>
        
        <div className="flex gap-2 shrink-0">
          <Button
            variant="outline"
            disabled={isExportingCSV}
            onClick={handleExportCSV}
            className="flex items-center gap-1.5 text-xs font-semibold"
          >
            <FileDown className="h-4 w-4" />
            {isExportingCSV ? "Exporting..." : "Export CSV"}
          </Button>
          <Button
            variant="outline"
            disabled={isExportingJSON}
            onClick={handleExportJSON}
            className="flex items-center gap-1.5 text-xs font-semibold"
          >
            <FileDown className="h-4 w-4" />
            {isExportingJSON ? "Exporting..." : "Export JSON"}
          </Button>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 overflow-hidden shadow-sm">
        <div className="p-4 bg-slate-50 dark:bg-slate-950/30 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">Activity Log (Last 100 entries)</span>
          <button
            onClick={() => { setLoading(true); fetchLogs(); }}
            className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 transition"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center p-12">
            <RefreshCw className="h-6 w-6 text-amber-600 animate-spin" />
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-slate-500 dark:text-slate-400 space-y-2">
            <Terminal className="h-8 w-8 mx-auto text-slate-350" />
            <p className="text-sm font-semibold">No audit logs found</p>
            <p className="text-xs">Logs will be generated as you query models and start debates.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200 dark:divide-slate-850">
            {logs.map((log) => {
              const isExpanded = expandedLogId === log.id;
              return (
                <div key={log.id} className="p-4 transition hover:bg-slate-50/50 dark:hover:bg-slate-900/20">
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 border border-amber-200/30 dark:border-amber-900/30">
                          {log.interaction_type}
                        </span>
                        <span className="text-[11px] text-slate-400 dark:text-slate-500">
                          {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>
                      
                      {log.debate_id && (
                        <p className="text-xs text-slate-500">
                          Debate ID: <span className="font-mono">{log.debate_id}</span>
                        </p>
                      )}
                    </div>

                    <button
                      onClick={() => toggleExpand(log.id)}
                      className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition"
                    >
                      {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 rounded-lg border border-slate-200/50 bg-slate-50 p-3 dark:border-slate-800/80 dark:bg-slate-950/40">
                      <div className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 mb-2 font-mono">
                        <ShieldAlert className="h-3.5 w-3.5" />
                        Log details (raw JSON payload)
                      </div>
                      <pre className="text-xs font-mono overflow-auto max-h-48 text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                        {JSON.stringify(log.details || {}, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}
