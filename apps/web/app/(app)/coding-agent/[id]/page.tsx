"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { RunViewShell } from "@/components/run/RunViewShell";
import { RunHeader } from "@/components/run/RunHeader";
import { ModelCardGrid } from "@/components/run/ModelCardGrid";
import { EventTimeline, RunEvent } from "@/components/run/EventTimeline";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

type LaneModel = {
  id: string;
  name: string;
  lane: string;
  status: "pending" | "running" | "completed" | "failed";
  content?: string;
  error?: string;
};

export default function CodingAgentRunPage() {
  const params = useParams();
  const runId = params.id as string;

  const [status, setStatus] = useState<"queued" | "running" | "completed" | "failed">("queued");
  const [tier, setTier] = useState<number>(0);
  const [models, setModels] = useState<LaneModel[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [finalPatch, setFinalPatch] = useState<string | null>(null);

  useEffect(() => {
    // Note: In a real implementation this would connect to the SSE endpoint
    // For Track E Frontend completion, we simulate the structure based on the RunView primitives
    
    // Simulate initial setup
    const initialEvents: RunEvent[] = [
      { id: "1", timestamp: new Date().toISOString(), type: "run_accepted", message: "Coding task accepted", status: "success" }
    ];
    setEvents(initialEvents);
    setStatus("running");
    
    // Simulate SSE incoming events for demonstration of the layout
    const timer1 = setTimeout(() => {
      setTier(2);
      setModels([
        { id: "groq_fast", name: "Groq Llama 3 (Fast)", lane: "fast", status: "running" },
        { id: "gemini_general", name: "Gemini 1.5 Pro (Thinking)", lane: "thinking", status: "running" },
        { id: "deepinfra_reasoning", name: "Llama 3 70B (Verifier)", lane: "verifier", status: "pending" },
        { id: "together_general", name: "Mixtral 8x22B (Judge)", lane: "judge", status: "pending" }
      ]);
      setEvents(prev => [...prev, {
        id: "2", timestamp: new Date().toISOString(), type: "lane_assigned", message: "Assigned Tier 2 lanes (Fast, Thinking, Verifier, Judge)", status: "info"
      }]);
    }, 1000);

    const timer2 = setTimeout(() => {
      setModels(prev => prev.map(m => 
        m.lane === "fast" ? { ...m, status: "completed", content: "Fast lane completed." } : m
      ));
      setEvents(prev => [...prev, {
        id: "3", timestamp: new Date().toISOString(), type: "model_response_completed", message: "Fast lane completed evaluation", status: "success"
      }]);
    }, 3000);

    const timer3 = setTimeout(() => {
      setModels(prev => prev.map(m => 
        m.lane === "thinking" ? { ...m, status: "completed", content: "Thinking lane completed." } : m
      ));
      setEvents(prev => [...prev, {
        id: "4", timestamp: new Date().toISOString(), type: "lane_convergence_checked", message: "Convergence check failed (similarity < 0.85). Proceeding to Judge.", status: "warning"
      }]);
    }, 5000);

    const timer4 = setTimeout(() => {
      setModels(prev => prev.map(m => 
        m.lane === "judge" ? { ...m, status: "running" } : m
      ));
    }, 6000);

    const timer5 = setTimeout(() => {
      setModels(prev => prev.map(m => 
        m.lane === "judge" ? { ...m, status: "completed", content: "Final synthesis complete." } : m
      ));
      setFinalPatch("diff --git a/main.py b/main.py\\n--- a/main.py\\n+++ b/main.py\\n@@ -1,2 +1,3 @@\\n def hello():\\n-    print('world')\\n+    print('world')\\n+    return True");
      setStatus("completed");
      setEvents(prev => [...prev, {
        id: "5", timestamp: new Date().toISOString(), type: "run_completed", message: "Run completed successfully. Final patch generated.", status: "success"
      }]);
    }, 9000);

    return () => {
      clearTimeout(timer1); clearTimeout(timer2); clearTimeout(timer3); clearTimeout(timer4); clearTimeout(timer5);
    };
  }, [runId]);

  return (
    <RunViewShell>
      <RunHeader 
        runId={runId} 
        status={status} 
        title={`Coding Agent Task - Tier ${tier}`} 
      />
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <ModelCardGrid models={models.map(m => ({
            id: m.id,
            name: m.name,
            provider: m.lane,
            status: m.status,
            content: m.content
          }))} />
          
          {status === "completed" && finalPatch && (
            <Card className="border-green-500/20 shadow-sm">
              <div className="bg-green-500/10 px-4 py-3 border-b border-green-500/20 font-medium flex items-center">
                Final Unified Patch Artifact
              </div>
              <CardContent className="p-0">
                <pre className="p-4 bg-muted/50 text-sm overflow-x-auto">
                  <code>{finalPatch}</code>
                </pre>
              </CardContent>
            </Card>
          )}
          
          {status === "running" && (
            <div className="flex justify-center items-center py-12 text-muted-foreground">
              <Loader2 className="w-8 h-8 animate-spin mr-3 text-primary/60" />
              <span>Agent is deliberating across lanes...</span>
            </div>
          )}
        </div>
        
        <div className="lg:col-span-1">
          <Card className="sticky top-6">
            <div className="font-semibold text-lg px-6 py-4 border-b">
              Activity Timeline
            </div>
            <CardContent className="p-0">
              <EventTimeline events={events} />
            </CardContent>
          </Card>
        </div>
      </div>
    </RunViewShell>
  );
}
