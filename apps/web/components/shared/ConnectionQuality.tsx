"use client";

import React, { useEffect, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Wifi, WifiOff, RefreshCw } from "lucide-react";

interface ConnectionQualityProps {
  sseStatus?: "idle" | "connecting" | "connected" | "reconnecting" | "closed";
  className?: string;
}

export default function ConnectionQuality({
  sseStatus = "idle",
  className,
}: ConnectionQualityProps) {
  const [latency, setLatency] = useState<number | null>(null);
  const [healthStatus, setHealthStatus] = useState<"healthy" | "degraded" | "offline">("healthy");
  const [isChecking, setIsChecking] = useState(false);

  const checkLatency = useCallback(async () => {
    if (isChecking) return;
    setIsChecking(true);
    const start = performance.now();
    try {
      const res = await fetch("/api/healthz", { cache: "no-store" });
      const end = performance.now();
      
      if (res.ok) {
        const rtt = Math.round(end - start);
        setLatency(rtt);
        if (rtt < 150) {
          setHealthStatus("healthy");
        } else {
          setHealthStatus("degraded");
        }
      } else {
        setHealthStatus("offline");
        setLatency(null);
      }
    } catch (err) {
      setHealthStatus("offline");
      setLatency(null);
    } finally {
      setIsChecking(false);
    }
  }, [isChecking]);

  useEffect(() => {
    // Initial check
    checkLatency();

    // Check periodically
    const interval = setInterval(() => {
      checkLatency();
    }, 15000);

    return () => clearInterval(interval);
  }, [checkLatency]);

  // Compute status colors
  let statusColor = "bg-rose-500 border-rose-500/30";
  let statusText = "Offline";

  if (sseStatus === "connected") {
    if (healthStatus === "healthy") {
      statusColor = "bg-emerald-500 border-emerald-500/30";
      statusText = "Excellent";
    } else if (healthStatus === "degraded") {
      statusColor = "bg-amber-500 border-amber-500/30";
      statusText = "Fair";
    }
  } else if (sseStatus === "connecting" || sseStatus === "reconnecting") {
    statusColor = "bg-amber-500 border-amber-500/30 animate-pulse";
    statusText = sseStatus === "reconnecting" ? "Reconnecting..." : "Connecting...";
  } else if (sseStatus === "closed") {
    statusColor = "bg-slate-500 border-slate-500/30";
    statusText = "Disconnected";
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2.5 px-3 py-1.5 rounded-full border text-xs font-semibold backdrop-blur-md transition-all duration-300",
        "bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700",
        className
      )}
      title={`SSE: ${sseStatus} | Latency: ${latency !== null ? `${latency}ms` : "N/A"}`}
    >
      <div className="relative flex h-2 w-2">
        {sseStatus === "connected" && healthStatus === "healthy" && (
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
        )}
        <span className={cn("relative inline-flex rounded-full h-2 w-2 border", statusColor)}></span>
      </div>

      <div className="flex items-center gap-1">
        <span>{statusText}</span>
        {latency !== null && (
          <span className="text-[10px] text-slate-500 font-mono">({latency}ms)</span>
        )}
      </div>

      {isChecking ? (
        <RefreshCw className="h-3 w-3 animate-spin text-slate-500" />
      ) : sseStatus === "connected" ? (
        <Wifi className="h-3 w-3 text-emerald-400" />
      ) : (
        <WifiOff className="h-3 w-3 text-rose-400" />
      )}
    </div>
  );
}
