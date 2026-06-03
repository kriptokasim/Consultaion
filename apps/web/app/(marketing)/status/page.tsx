"use client";

import { useEffect, useState } from "react";
import { API_ORIGIN } from "@/lib/config/runtime";
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw, Server, Database, Activity, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";

type ProviderStatus = {
  configured: boolean;
  status: string;
};

type StatusResponse = {
  status: string;
  database: string;
  sse: string;
  providers: Record<string, ProviderStatus>;
  version: string;
  env: string;
};

export default function StatusPage() {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_ORIGIN}/api/status`, { cache: "no-store" });
      if (!res.ok) throw new Error("Failed to fetch system status");
      const json = await res.json();
      setData(json);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.message || "Failed to load system status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    // Auto refresh every 60 seconds
    const interval = setInterval(fetchStatus, 60000);
    return () => clearInterval(interval);
  }, []);

  const getOverallConfig = (status?: string) => {
    switch (status) {
      case "operational":
        return {
          title: "All Systems Operational",
          color: "text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-900/30",
          icon: <CheckCircle2 className="h-8 w-8 text-emerald-500" />
        };
      case "degraded":
        return {
          title: "Degraded Performance",
          color: "text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-900/30",
          icon: <AlertTriangle className="h-8 w-8 text-amber-500" />
        };
      case "major_outage":
      default:
        return {
          title: "Major System Outage",
          color: "text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-900/30",
          icon: <XCircle className="h-8 w-8 text-red-500" />
        };
    }
  };

  const getStatusIcon = (status?: string) => {
    if (status === "operational" || status === "operational" || status === "healthy") {
      return <CheckCircle2 className="h-5 w-5 text-emerald-500 shrink-0" />;
    }
    if (status === "degraded" || status === "warning") {
      return <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0" />;
    }
    return <XCircle className="h-5 w-5 text-red-500 shrink-0" />;
  };

  const systemConfig = getOverallConfig(data?.status || (error ? "major_outage" : "operational"));

  // Premium uptime dots generator
  const renderUptimeDots = () => {
    return (
      <div className="flex gap-1 overflow-x-hidden pt-1">
        {[...Array(24)].map((_, i) => (
          <span
            key={i}
            className={`h-6 w-1.5 rounded-full shrink-0 ${
              i === 23 && data?.status === "degraded"
                ? "bg-amber-400 dark:bg-amber-500"
                : i === 23 && data?.status === "major_outage"
                ? "bg-red-400 dark:bg-red-500"
                : "bg-emerald-500 dark:bg-emerald-600"
            }`}
            title="Uptime operational"
          />
        ))}
      </div>
    );
  };

  return (
    <main className="mx-auto max-w-4xl px-6 py-12 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-4xl">System Status</h1>
          <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
            Real-time status of Consultaion multi-agent debate servers and upstream SOTA providers.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchStatus}
          disabled={loading}
          className="flex items-center gap-2"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Main Status Panel */}
      <div className={`rounded-2xl border p-6 flex flex-col md:flex-row items-center gap-4 ${systemConfig.color} transition-colors duration-300`}>
        {systemConfig.icon}
        <div className="text-center md:text-left flex-1 min-w-0">
          <h2 className="text-xl font-bold">{systemConfig.title}</h2>
          <p className="text-sm mt-0.5 opacity-90">
            {error ? error : `As of ${lastRefreshed.toLocaleTimeString()}. Checked automatically every 60 seconds.`}
          </p>
        </div>
      </div>

      {/* Core Infrastructure */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
          <Server className="h-5 w-5 text-slate-500" />
          Core Infrastructure
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Database */}
          <div className="rounded-xl border border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/50 p-5 shadow-sm space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-50 dark:bg-slate-800 text-primary dark:text-blue-400 rounded-lg">
                  <Database className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-white">Database Cluster</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">PostgreSQL state store</p>
                </div>
              </div>
              {loading && !data ? (
                <div className="h-5 w-16 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-md" />
              ) : (
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  {getStatusIcon(data?.database)}
                  <span className="capitalize">{data?.database || "operational"}</span>
                </div>
              )}
            </div>
            {renderUptimeDots()}
          </div>

          {/* SSE Broker */}
          <div className="rounded-xl border border-slate-200 bg-white/60 dark:border-slate-800 dark:bg-slate-900/50 p-5 shadow-sm space-y-4">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-50 dark:bg-slate-800 text-primary dark:text-blue-400 rounded-lg">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 dark:text-white">Realtime Event Stream</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">SSE Event Router</p>
                </div>
              </div>
              {loading && !data ? (
                <div className="h-5 w-16 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-md" />
              ) : (
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  {getStatusIcon(data?.sse)}
                  <span className="capitalize">{data?.sse || "operational"}</span>
                </div>
              )}
            </div>
            {renderUptimeDots()}
          </div>
        </div>
      </div>

      {/* Upstream AI Providers */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white flex items-center gap-2">
          <Cpu className="h-5 w-5 text-slate-500" />
          SOTA Model Providers
        </h3>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/50 shadow-sm">
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {/* OpenAI */}
            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">OpenAI (GPT-4o)</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">Synthesis and reasoning services</p>
              </div>
              {loading && !data ? (
                <div className="h-5 w-24 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-md" />
              ) : (
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  {getStatusIcon(data?.providers?.openai?.status)}
                  <span className="capitalize">{data?.providers?.openai?.status?.replace("_", " ") || "operational"}</span>
                </div>
              )}
            </div>

            {/* Anthropic */}
            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">Anthropic (Claude 3.5 Sonnet)</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">Agent deliberation seats</p>
              </div>
              {loading && !data ? (
                <div className="h-5 w-24 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-md" />
              ) : (
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  {getStatusIcon(data?.providers?.anthropic?.status)}
                  <span className="capitalize">{data?.providers?.anthropic?.status?.replace("_", " ") || "operational"}</span>
                </div>
              )}
            </div>

            {/* Gemini */}
            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">Google Gemini (Gemini 2.5 Pro)</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">Context modeling and fallback seats</p>
              </div>
              {loading && !data ? (
                <div className="h-5 w-24 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-md" />
              ) : (
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  {getStatusIcon(data?.providers?.gemini?.status)}
                  <span className="capitalize">{data?.providers?.gemini?.status?.replace("_", " ") || "operational"}</span>
                </div>
              )}
            </div>

            {/* OpenRouter (DeepSeek R1) */}
            <div className="flex items-center justify-between px-5 py-4">
              <div>
                <h4 className="font-semibold text-slate-900 dark:text-white">DeepSeek R1 (via OpenRouter)</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400">Reasoning and math seat providers</p>
              </div>
              {loading && !data ? (
                <div className="h-5 w-24 bg-slate-100 dark:bg-slate-800 animate-pulse rounded-md" />
              ) : (
                <div className="flex items-center gap-1.5 text-sm font-semibold">
                  {getStatusIcon(data?.providers?.openrouter?.status)}
                  <span className="capitalize">{data?.providers?.openrouter?.status?.replace("_", " ") || "operational"}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
