import { RunViewShell } from "@/components/run/RunViewShell";
import { Loader2 } from "lucide-react";

export default function LoadingRunView() {
  return (
    <RunViewShell>
      <div className="flex flex-col items-center justify-center min-h-[50vh] text-muted-foreground animate-pulse">
        <Loader2 className="w-10 h-10 animate-spin mb-4 text-primary/40" />
        <h3 className="text-lg font-medium">Loading Run Details</h3>
        <p className="text-sm">Fetching agent timeline and patches...</p>
      </div>
    </RunViewShell>
  );
}
