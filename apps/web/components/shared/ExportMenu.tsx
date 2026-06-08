"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Download, FileText, Code, Printer, ChevronDown } from "lucide-react";

interface ExportMenuProps {
  debateId: string;
  title?: string;
  events: any[];
  config?: any;
  className?: string;
}

export default function ExportMenu({
  debateId,
  title = "Consultation Run",
  events,
  config,
  className,
}: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleExportJSON = () => {
    const data = {
      debateId,
      title,
      config,
      exportedAt: new Date().toISOString(),
      events: events.map((e) => ({
        id: e.id,
        sequence: e.sequence,
        timestamp: e.timestamp || e.ts,
        type: e.type,
        round: e.round,
        seat: e.seat || e.seat_name,
        payload: e.payload,
      })),
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `consultaion-run-${debateId}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  const handleExportMarkdown = () => {
    let md = `# ${title}\n\n`;
    md += `**Debate Session ID:** \`${debateId}\`\n`;
    md += `**Exported At:** ${new Date().toLocaleString()}\n\n`;

    if (config) {
      md += `## Configuration\n`;
      md += `\`\`\`json\n${JSON.stringify(config, null, 2)}\n\`\`\`\n\n`;
    }

    md += `## Timeline Events\n\n`;
    events.forEach((e) => {
      const ts = new Date(e.timestamp || e.ts).toLocaleTimeString();
      const type = e.type || "notice";
      const actor = e.payload?.actor || e.payload?.seat_name || "System";
      
      md += `### [${ts}] ${actor} (${type})\n`;
      if (e.payload?.text || e.payload?.content) {
        md += `${e.payload.text || e.payload.content}\n\n`;
      } else {
        md += `\`\`\`json\n${JSON.stringify(e.payload, null, 2)}\n\`\`\`\n\n`;
      }
      md += `---\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `consultaion-run-${debateId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  const handlePrint = () => {
    window.print();
    setIsOpen(false);
  };

  return (
    <div className={cn("relative inline-block text-left", className)}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "inline-flex items-center gap-2 px-4 py-2.5 rounded-xl border text-sm font-semibold transition-all duration-300",
          "bg-slate-900/80 border-slate-800 text-slate-300 hover:text-white hover:border-slate-700",
          "focus:outline-none focus:ring-2 focus:ring-amber-500/50"
        )}
      >
        <Download className="h-4 w-4" />
        <span>Export Session</span>
        <ChevronDown className={cn("h-4 w-4 transition-transform duration-300", isOpen && "rotate-180")} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-30"
            onClick={() => setIsOpen(false)}
          />
          <div
            className={cn(
              "absolute right-0 mt-2 w-56 rounded-2xl border shadow-xl z-40 overflow-hidden backdrop-blur-lg",
              "bg-slate-950/90 border-slate-800/80"
            )}
          >
            <div className="py-1.5 divide-y divide-slate-800/60">
              <button
                onClick={handleExportMarkdown}
                className="flex items-center gap-3 w-full px-4 py-3 text-sm text-slate-300 hover:bg-slate-900 hover:text-white transition-colors text-left"
              >
                <FileText className="h-4 w-4 text-emerald-400" />
                <div>
                  <div className="font-semibold">Markdown Document</div>
                  <div className="text-xs text-slate-500">Perfect for clean documentation</div>
                </div>
              </button>

              <button
                onClick={handleExportJSON}
                className="flex items-center gap-3 w-full px-4 py-3 text-sm text-slate-300 hover:bg-slate-900 hover:text-white transition-colors text-left"
              >
                <Code className="h-4 w-4 text-blue-400" />
                <div>
                  <div className="font-semibold">JSON Raw Log</div>
                  <div className="text-xs text-slate-500">Full structured payload events</div>
                </div>
              </button>

              <button
                onClick={handlePrint}
                className="flex items-center gap-3 w-full px-4 py-3 text-sm text-slate-300 hover:bg-slate-900 hover:text-white transition-colors text-left"
              >
                <Printer className="h-4 w-4 text-amber-400" />
                <div>
                  <div className="font-semibold">Print / PDF</div>
                  <div className="text-xs text-slate-500">Save to PDF or hard copy</div>
                </div>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
