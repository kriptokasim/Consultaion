import React from 'react';

export interface RunViewShellProps {
  header: React.ReactNode;
  content: React.ReactNode;
  timeline?: React.ReactNode;
  footer?: React.ReactNode;
  error?: string | null;
}

/**
 * Shared shell for run-oriented views (Debate, Arena, Coding Agent).
 * Provides standard layout, grid system, and error boundaries.
 */
export function RunViewShell({
  header,
  content,
  timeline,
  footer,
  error,
}: RunViewShellProps) {
  return (
    <div className="flex flex-col h-full bg-background min-h-screen">
      {/* Header Slot */}
      <div className="border-b bg-card/50 px-6 py-4 sticky top-0 z-10 backdrop-blur-md">
        {header}
      </div>

      {/* Error Boundary / Banner */}
      {error && (
        <div className="bg-destructive/10 text-destructive px-6 py-3 border-b border-destructive/20 text-sm font-medium">
          {error}
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 overflow-auto">
        <div className="container mx-auto p-6 max-w-7xl flex flex-col lg:flex-row gap-6 h-full">
          {/* Primary Content (Cards/Results) */}
          <div className="flex-1 flex flex-col gap-6 min-w-0">
            {content}
            {footer && <div className="mt-auto pt-6">{footer}</div>}
          </div>

          {/* Optional Sidebar (Timeline/Trace) */}
          {timeline && (
            <div className="w-full lg:w-[400px] xl:w-[450px] shrink-0 border-l pl-6 overflow-y-auto">
              {timeline}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
